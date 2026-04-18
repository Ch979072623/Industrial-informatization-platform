"""
schema → 动态构图

输入：复合模块的 schema_json + 对外参数取值
输出：一个等价的 nn.Module 实例

内部机制：
1. 递归实例化所有子节点（原子模块直接映射到 torch.nn，复合模块递归）
2. 用 nn.ModuleDict 持有子模块
3. forward 方法按 sub_edges 做拓扑排序执行，通过 proxy_inputs/outputs 与外部交互
"""
import json
import inspect
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Tuple

import torch
import torch.nn as nn

from app.ml.modules.expression_evaluator import resolve_params

# ============ 原子模块映射 ============
_ATOMIC_CTOR: Dict[str, Any] = {
    "Conv2d": nn.Conv2d,
    "BatchNorm2d": nn.BatchNorm2d,
    "ReLU": nn.ReLU,
    "SiLU": nn.SiLU,
    "Linear": nn.Linear,
    "Dropout": nn.Dropout,
    "MaxPool2d": nn.MaxPool2d,
    "AdaptiveAvgPool2d": nn.AdaptiveAvgPool2d,
    "AdaptiveMaxPool2d": nn.AdaptiveMaxPool2d,
    "AvgPool2d": nn.AvgPool2d,
    "Upsample": nn.Upsample,
    "Flatten": nn.Flatten,
    "GroupNorm": nn.GroupNorm,
    "Sigmoid": nn.Sigmoid,
    "Conv1d": nn.Conv1d,
}


class _Concat(nn.Module):
    """原子模块：Concat / torch.cat"""
    def __init__(self, dim: int = 1):
        super().__init__()
        self.dim = dim

    def forward(self, *tensors: torch.Tensor) -> torch.Tensor:
        return torch.cat(tensors, dim=self.dim)


class _Add(nn.Module):
    """原子模块：张量逐元素相加（支持任意数量输入）"""
    def forward(self, *xs: torch.Tensor) -> torch.Tensor:
        return sum(xs)


class _Chunk(nn.Module):
    """原子模块：Chunk / torch.chunk

    forward 返回 tuple，下游通过 source_port 取下标。
    论文使用 chunk（按份数分），与 split（按大小分）区分。
    """
    def __init__(self, chunks: int = 2, dim: int = 1):
        super().__init__()
        self.chunks = chunks
        self.dim = dim

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, ...]:
        return torch.chunk(x, chunks=self.chunks, dim=self.dim)


class _Scale(nn.Module):
    """原子模块：可学习标量缩放（Detect_SASD 用）"""
    def __init__(self, init_value: float = 1.0):
        super().__init__()
        self.scale = nn.Parameter(torch.tensor(init_value, dtype=torch.float32))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * self.scale


class _Identity(nn.Module):
    """原子模块：恒等映射（用于残差连接的分发）"""
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x


class _Mul(nn.Module):
    """原子模块：张量逐元素相乘（支持任意数量输入）"""
    def forward(self, *xs: torch.Tensor) -> torch.Tensor:
        result = xs[0]
        for x in xs[1:]:
            result = result * x
        return result


class _ChannelMean(nn.Module):
    """原子模块：沿通道维度求均值，keepdim=True"""
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.mean(x, dim=1, keepdim=True)


class _ChannelMax(nn.Module):
    """原子模块：沿通道维度求最大值，keepdim=True"""
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.max(x, dim=1, keepdim=True)[0]


class _ECAConv1d(nn.Module):
    """
    原子模块：ECA 的 1D 卷积包装

    内部包含 squeeze + Conv1d + transpose + unsqueeze 序列，
    将输入 (B, C, 1, 1) 变换后做 1D 卷积再恢复形状。
    """
    def __init__(self, in_channels: int, gamma: float = 2.0, b: float = 1.0):
        super().__init__()
        kernel_size = int(abs((math.log(in_channels, 2) + b) / gamma))
        kernel_size = kernel_size if kernel_size % 2 else kernel_size + 1
        self.conv = nn.Conv1d(1, 1, kernel_size, padding=(kernel_size - 1) // 2, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, C, 1, 1)
        y = x.squeeze(-1).transpose(-1, -2)  # (B, 1, C)
        y = self.conv(y)  # (B, 1, C)
        y = y.transpose(-1, -2).unsqueeze(-1)  # (B, C, 1, 1)
        return y


_SPECIAL_CTOR: Dict[str, Any] = {
    "Concat": _Concat,
    "Add": _Add,
    "Mul": _Mul,
    "Chunk": _Chunk,
    "Scale": _Scale,
    "Identity": _Identity,
    "ChannelMean": _ChannelMean,
    "ChannelMax": _ChannelMax,
    "ECA_Conv1d": _ECAConv1d,
}


def _build_atomic_module(type_name: str, params: Dict[str, Any]) -> nn.Module:
    """根据类型和参数构建一个原子 nn.Module"""
    if type_name in _SPECIAL_CTOR:
        cls = _SPECIAL_CTOR[type_name]
        sig = inspect.signature(cls.__init__)
        valid = {k: v for k, v in params.items() if k in sig.parameters}
        return cls(**valid)

    if type_name in _ATOMIC_CTOR:
        cls = _ATOMIC_CTOR[type_name]
        sig = inspect.signature(cls.__init__)
        valid = {k: v for k, v in params.items() if k in sig.parameters}
        return cls(**valid)

    raise ValueError(f"未知原子模块类型: {type_name}")


# ============ 默认 schema 解析器（基于文件系统） ============
def _default_schema_resolver(type_name: str) -> Optional[Dict[str, Any]]:
    """从 composite/ 和 custom/ 目录查找 schema.json"""
    base = Path(__file__).parent
    for subdir in (base / "composite", base / "custom"):
        if not subdir.exists():
            continue
        for child in subdir.iterdir():
            if not child.is_dir():
                continue
            path = child / "schema.json"
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    schema = json.load(f)
                if schema.get("type") == type_name:
                    return schema
            except Exception:
                continue
    return None


# ============ 复合模块动态类 ============
class _CompositeModule(nn.Module):
    """由 schema 动态构建的复合模块"""

    def __init__(
        self,
        schema: Dict[str, Any],
        parent_params: Dict[str, Any],
        schema_resolver: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ):
        super().__init__()
        self.schema = schema
        self.proxy_inputs = schema.get("proxy_inputs", [])
        self.proxy_outputs = schema.get("proxy_outputs", [])
        self.sub_edges = schema.get("sub_edges", [])

        if schema_resolver is None:
            schema_resolver = _default_schema_resolver

        # 实例化所有子节点
        self.sub_modules = nn.ModuleDict()
        for node in schema.get("sub_nodes", []):
            node_id = node["id"]
            node_type = node["type"]
            node_params = resolve_params(node.get("params", {}), parent_params)

            child_schema = schema_resolver(node_type)
            if child_schema and child_schema.get("is_composite", False):
                module = schema_to_module(child_schema, node_params, schema_resolver)
            else:
                module = _build_atomic_module(node_type, node_params)

            self.sub_modules[node_id] = module

        # 预计算拓扑排序和邻接关系
        self._execution_order = self._topological_sort()
        self._out_edges: Dict[str, List[Dict[str, Any]]] = {nid: [] for nid in self.sub_modules}
        for e in self.sub_edges:
            self._out_edges[e["source"]].append(e)

    def _topological_sort(self) -> List[str]:
        """Kahn 算法拓扑排序"""
        in_degree = {nid: 0 for nid in self.sub_modules}
        for e in self.sub_edges:
            in_degree[e["target"]] += 1

        # 入度为 0 的节点（只可能是 proxy input 指向的节点，或者孤立节点）
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for e in self.sub_edges:
                if e["source"] == nid:
                    in_degree[e["target"]] -= 1
                    if in_degree[e["target"]] == 0:
                        queue.append(e["target"])

        if len(order) != len(self.sub_modules):
            missing = set(self.sub_modules) - set(order)
            raise RuntimeError(f"子图中存在环路或不可达节点: {missing}")
        return order

    def forward(self, *inputs: torch.Tensor) -> torch.Tensor:
        """
        执行前向传播

        inputs 的顺序与 proxy_inputs 一致。
        输出如果是单值直接返回张量；如果是多值返回 tuple。
        """
        # node_inputs[node_id][port_index] = tensor
        node_inputs: Dict[str, Dict[int, torch.Tensor]] = {
            nid: {} for nid in self.sub_modules
        }

        # 注入外部输入
        for ext_idx, proxy in enumerate(self.proxy_inputs):
            sub_id = proxy["sub_node_id"]
            port_idx = proxy["port_index"]
            node_inputs[sub_id][port_idx] = inputs[ext_idx]

        # 按拓扑顺序执行
        node_outputs: Dict[str, Any] = {}

        for nid in self._execution_order:
            module = self.sub_modules[nid]
            in_ports = node_inputs[nid]
            # 按端口索引排序后组装参数
            sorted_ports = sorted(in_ports.keys())
            args = [in_ports[p] for p in sorted_ports]

            if len(args) == 0:
                raise RuntimeError(f"节点 {nid} 没有输入")
            if len(args) == 1:
                output = module(args[0])
            else:
                output = module(*args)

            node_outputs[nid] = output

            # 分发到下游
            for e in self._out_edges[nid]:
                src_port = e["source_port"]
                tgt_id = e["target"]
                tgt_port = e["target_port"]

                if isinstance(output, tuple):
                    out_tensor = output[src_port]
                else:
                    out_tensor = output

                node_inputs[tgt_id][tgt_port] = out_tensor

        # 收集输出
        results = []
        for proxy in self.proxy_outputs:
            sub_id = proxy["sub_node_id"]
            port_idx = proxy["port_index"]
            out = node_outputs[sub_id]
            if isinstance(out, tuple):
                results.append(out[port_idx])
            else:
                results.append(out)

        if len(results) == 1:
            return results[0]
        return tuple(results)


def schema_to_module(
    schema: Dict[str, Any],
    parent_params: Dict[str, Any],
    schema_resolver: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
) -> nn.Module:
    """
    将模块 schema 转换为可执行的 nn.Module

    Args:
        schema: 模块的 schema_json（含 sub_nodes/sub_edges）
        parent_params: 对外参数的实际取值
        schema_resolver: 根据 type 查找子模块 schema 的函数；默认从文件系统加载

    Returns:
        nn.Module 实例（原子模块或 _CompositeModule）
    """
    # 用 schema 默认值补充 parent_params，确保表达式能访问到未显式传入的参数（包括 None）
    full_params: Dict[str, Any] = dict(parent_params)
    for spec in schema.get("params_schema", []):
        if spec["name"] not in full_params:
            full_params[spec["name"]] = spec.get("default")

    if schema.get("is_composite", False):
        return _CompositeModule(schema, full_params, schema_resolver)

    type_name = schema["type"]
    resolved = resolve_params(schema.get("params", {}), full_params, schema.get("params_schema"))
    return _build_atomic_module(type_name, resolved)
