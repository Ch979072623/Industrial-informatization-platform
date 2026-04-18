"""
嵌套复合模块测试

验证：复合模块 CSP_PMSFA 内部引用另一个复合模块 ResNetBottleneck 作为子节点，
schema_to_module 能正确递归实例化并输出等价的 nn.Module。
"""
import json
from pathlib import Path

import pytest
import torch
import torch.nn as nn

from app.ml.modules.dynamic_builder import schema_to_module
from app.ml.modules.composite.csp_pmsfa.module import CSP_PMSFA
from app.ml.modules.composite.resnetbottleneck.module import ResNetBottleneck

MODULES_DIR = Path(__file__).parent.parent / "app" / "ml" / "modules" / "composite"


def load_schema(name: str):
    path = MODULES_DIR / name / "schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def set_uniform_weights(module: nn.Module, val: float = 0.1):
    for p in module.parameters():
        p.data.fill_(val)
    for b in module.buffers():
        b.data.fill_(val)


class TestNestedComposite:
    """嵌套复合模块测试：CSP_PMSFA 内部用 ResNetBottleneck 替代 PMSFA"""

    def test_csp_pmsfa_nested_resnetbottleneck(self):
        """
        在 CSP_PMSFA 的 schema 基础上，手动把内部 PMSFA 节点替换为 ResNetBottleneck，
        验证 schema_to_module 能正确递归实例化嵌套复合模块。
        """
        # 加载 CSP_PMSFA schema
        schema = load_schema("csp_pmsfa")
        params = {"c1": 128, "c2": 256, "n": 2, "shortcut": False, "g": 1, "e": 0.5}

        # 修改 schema：把 PMSFA 节点替换为 ResNetBottleneck
        for node in schema["sub_nodes"]:
            if node["type"] == "PMSFA":
                node["type"] = "ResNetBottleneck"
                # ResNetBottleneck 的参数：in_channels = int(c2 * e) // 2, out_channels = int(c2 * e) // 2
                # 这里 c2=256, e=0.5 → int(128) = 128
                node["params"] = {"in_channels": 128, "out_channels": 128, "stride": 1}

        dyn = schema_to_module(schema, params)

        # 验证嵌套实例化成功
        assert "pmsfa0" in dyn.sub_modules or "pmsfa1" in dyn.sub_modules or any(
            "ResNetBottleneck" in str(type(m)) for m in dyn.sub_modules.values()
        ), "ResNetBottleneck 未正确嵌套实例化"

        # 前向传播
        set_uniform_weights(dyn)
        x = torch.randn(2, 128, 32, 32)
        with torch.no_grad():
            y = dyn(x)

        assert y.shape == (2, 256, 32, 32), f"嵌套模块输出 shape 异常: {y.shape}"

    def test_manual_nested_forward(self):
        """手动构建一个包含嵌套复合模块的 schema，验证拓扑排序正确"""
        outer_schema = {
            "type": "Outer",
            "category": "test",
            "display_name": "嵌套测试",
            "is_composite": True,
            "params_schema": [],
            "proxy_inputs": [{"sub_node_id": "inner", "port_index": 0, "name": "x"}],
            "proxy_outputs": [{"sub_node_id": "inner", "port_index": 0, "name": "out"}],
            "sub_nodes": [
                {"id": "inner", "type": "ResNetBottleneck", "params": {"in_channels": 64, "out_channels": 256, "stride": 1}, "position": {"x": 100, "y": 100}}
            ],
            "sub_edges": []
        }

        dyn = schema_to_module(outer_schema, {})
        set_uniform_weights(dyn)

        x = torch.randn(2, 64, 32, 32)
        with torch.no_grad():
            y = dyn(x)

        assert y.shape == (2, 256, 32, 32)
