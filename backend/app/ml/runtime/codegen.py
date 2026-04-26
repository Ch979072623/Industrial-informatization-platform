"""
Module 代码生成器

将 composite 模块的 schema_json 转换为可运行的 PyTorch nn.Module Python 代码。
"""
import ast
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class CodegenError(Exception):
    """代码生成错误"""
    pass


_TORCH_NN_MODULES: Set[str] = {
    "Conv2d", "Conv1d", "BatchNorm2d", "ReLU", "SiLU", "Linear",
    "Dropout", "MaxPool2d", "AdaptiveAvgPool2d", "AdaptiveMaxPool2d",
    "AvgPool2d", "Upsample", "Flatten", "GroupNorm", "Sigmoid",
    "Identity", "ConvTranspose2d", "Tanh", "Softmax", "LayerNorm", "Embedding",
}

_INLINE_ATOMIC_MODULES: Dict[str, str] = {
    "Concat": "class _Concat(nn.Module):\n    def __init__(self, dim=1):\n        super().__init__()\n        self.dim = dim\n    def forward(self, *tensors):\n        return torch.cat(tensors, dim=self.dim)",
    "Add": "class _Add(nn.Module):\n    def forward(self, *xs):\n        return sum(xs)",
    "Chunk": "class _Chunk(nn.Module):\n    def __init__(self, chunks=2, dim=1):\n        super().__init__()\n        self.chunks = chunks\n        self.dim = dim\n    def forward(self, x):\n        return torch.chunk(x, self.chunks, self.dim)",
    "Scale": "class _Scale(nn.Module):\n    def __init__(self, init_value=1.0):\n        super().__init__()\n        self.scale = nn.Parameter(torch.tensor(init_value, dtype=torch.float32))\n    def forward(self, x):\n        return x * self.scale",
    "Mul": "class _Mul(nn.Module):\n    def forward(self, *xs):\n        result = xs[0]\n        for x in xs[1:]:\n            result = result * x\n        return result",
    "Split": "class _Split(nn.Module):\n    def __init__(self, split_size, dim=1):\n        super().__init__()\n        self.split_size = split_size\n        self.dim = dim\n    def forward(self, x):\n        return torch.split(x, self.split_size, self.dim)",
    "ChannelMean": "class _ChannelMean(nn.Module):\n    def forward(self, x):\n        return torch.mean(x, dim=1, keepdim=True)",
    "ChannelMax": "class _ChannelMax(nn.Module):\n    def forward(self, x):\n        return torch.max(x, dim=1, keepdim=True)[0]",
}

_MULTI_OUTPUT_TYPES: Set[str] = {"Chunk", "Split"}
_MAX_DEPTH = 10


def convert_expr(expr_str: str) -> str:
    if not isinstance(expr_str, str):
        return repr(expr_str)
    expr_str = expr_str.strip()
    if not (expr_str.startswith("${") and expr_str.endswith("}")):
        return expr_str
    inner = expr_str[2:-1].strip()
    if not inner:
        raise CodegenError("Empty expression: ${}")
    try:
        tree = ast.parse(inner, mode="eval")
    except SyntaxError as exc:
        raise CodegenError(f"Expression syntax error: {inner}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in ("int", "float"):
                    raise CodegenError(f"Unsupported function call: {node.func.id}")
            else:
                raise CodegenError("Unsupported function call (attribute/method)")
    return inner


def _get_class_name(schema_json: Dict[str, Any]) -> str:
    return schema_json.get("type", "GeneratedModule")


def _get_module_ref(type_name: str) -> str:
    if type_name in _TORCH_NN_MODULES:
        return f"nn.{type_name}"
    if type_name in _INLINE_ATOMIC_MODULES:
        return f"_{type_name}"
    return type_name


def _format_param_value(value: Any) -> str:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return convert_expr(value)
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    return repr(value)


def _extract_vars_from_expr(expr: str) -> List[str]:
    builtin_names = {
        "int", "float", "abs", "min", "max", "len", "sum", "round",
        "True", "False", "None", "and", "or", "not", "in", "is",
        "if", "else", "for", "while", "def", "class", "return",
        "import", "from", "as", "with", "try", "except", "finally",
        "raise", "pass", "break", "continue", "lambda", "yield",
        "assert", "del", "global", "nonlocal",
    }
    found = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr)
    return [v for v in found if v not in builtin_names]


def _get_init_params(sub_nodes: List[Dict[str, Any]], topo_order: List[str]) -> List[str]:
    node_map = {n["id"]: n for n in sub_nodes}
    vars_found: List[str] = []
    vars_set: Set[str] = set()
    for node_id in topo_order:
        node = node_map[node_id]
        for v in node.get("params", {}).values():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                expr = v[2:-1]
                for var in _extract_vars_from_expr(expr):
                    if var not in vars_set:
                        vars_set.add(var)
                        vars_found.append(var)
    return vars_found


def _topological_sort(sub_nodes: List[Dict[str, Any]], sub_edges: List[Dict[str, Any]]) -> List[str]:
    node_ids = {n["id"] for n in sub_nodes}
    adj: Dict[str, List[str]] = {n: [] for n in node_ids}
    in_degree: Dict[str, int] = {n: 0 for n in node_ids}
    for edge in sub_edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in node_ids and tgt in node_ids:
            adj[src].append(tgt)
            in_degree[tgt] += 1
    queue = sorted([n for n in node_ids if in_degree[n] == 0])
    result: List[str] = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in sorted(adj[node]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                queue.sort()
    if len(result) != len(node_ids):
        raise CodegenError("Cycle detected in sub_edges")
    return result


def _assign_names(sub_nodes: List[Dict[str, Any]], topo_order: List[str]) -> Dict[str, Tuple[str, str]]:
    node_map = {n["id"]: n for n in sub_nodes}
    type_counters: Dict[str, int] = {}
    result: Dict[str, Tuple[str, str]] = {}
    for node_id in topo_order:
        node_type = node_map[node_id]["type"]
        idx = type_counters.get(node_type, 0)
        type_counters[node_type] = idx + 1
        name = f"{node_type.lower()}_{idx}"
        result[node_id] = (name, name)
    return result


def _get_node_inputs(
    node_id: str,
    sub_edges: List[Dict[str, Any]],
    proxy_inputs: List[Dict[str, Any]],
    name_map: Dict[str, Tuple[str, str]],
    node_map: Dict[str, Dict[str, Any]],
) -> List[str]:
    inputs_by_port: Dict[int, str] = {}
    for edge in sub_edges:
        if edge.get("target") == node_id:
            port = edge.get("target_port", 0)
            src_id = edge["source"]
            src_port = edge.get("source_port", 0)
            src_var = name_map[src_id][1]
            src_type = node_map[src_id]["type"]
            if src_port > 0 or src_type in _MULTI_OUTPUT_TYPES:
                src_var = f"{src_var}[{src_port}]"
            inputs_by_port[port] = src_var
    for pi in proxy_inputs:
        if pi.get("sub_node_id") == node_id:
            port = pi.get("port_index", 0)
            inputs_by_port[port] = pi["name"]
    if not inputs_by_port:
        return []
    max_port = max(inputs_by_port.keys())
    result = []
    for i in range(max_port + 1):
        if i in inputs_by_port:
            result.append(inputs_by_port[i])
        else:
            result.append("None")
    return result

def generate_module_code(
    schema_json: Dict[str, Any],
    expand_composites: bool = True,
    **kwargs: Any,
) -> str:
    resolver: Optional[Callable[[str], Optional[Dict[str, Any]]]] = kwargs.get("_resolver")
    depth: int = kwargs.get("_depth", 0)
    seen: Optional[Set[str]] = kwargs.get("_seen")

    if depth > _MAX_DEPTH:
        raise CodegenError(f"Recursion depth exceeds {_MAX_DEPTH}")
    if seen is None:
        seen = set()

    sub_nodes = schema_json.get("sub_nodes", [])
    sub_edges = schema_json.get("sub_edges", [])
    proxy_inputs = schema_json.get("proxy_inputs", [])
    proxy_outputs = schema_json.get("proxy_outputs", [])
    class_name = _get_class_name(schema_json)

    topo_order = _topological_sort(sub_nodes, sub_edges)
    name_map = _assign_names(sub_nodes, topo_order)
    node_map = {n["id"]: n for n in sub_nodes}

    inline_classes: List[str] = []
    inline_set: Set[str] = set()
    composite_schemas: List[Tuple[str, Dict[str, Any]]] = []
    composite_set: Set[str] = set()

    for node in sub_nodes:
        t = node["type"]
        if t in _TORCH_NN_MODULES or t in _INLINE_ATOMIC_MODULES:
            if t in _INLINE_ATOMIC_MODULES and t not in inline_set:
                inline_classes.append(t)
                inline_set.add(t)
            continue
        if resolver and expand_composites:
            sub_schema = resolver(t)
            if sub_schema and sub_schema.get("is_composite"):
                if t in seen:
                    raise CodegenError(f"Cycle detected: {' -> '.join(seen)} -> {t}")
                if t not in composite_set:
                    composite_schemas.append((t, sub_schema))
                    composite_set.add(t)
                continue

    init_params = _get_init_params(sub_nodes, topo_order)

    lines: List[str] = []

    if depth == 0:
        lines.append("import torch")
        lines.append("import torch.nn as nn")
        lines.append("")

    if expand_composites and resolver:
        for _type_name, sub_schema in composite_schemas:
            sub_code = generate_module_code(
                sub_schema,
                expand_composites=True,
                _resolver=resolver,
                _depth=depth + 1,
                _seen=seen | {class_name},
            )
            lines.append(sub_code)
            lines.append("")

    for t in inline_classes:
        lines.append(_INLINE_ATOMIC_MODULES[t])
        lines.append("")

    if not expand_composites:
        for node in sub_nodes:
            t = node["type"]
            if t not in _TORCH_NN_MODULES and t not in _INLINE_ATOMIC_MODULES:
                lines.append(f"# NOTE: {t} must be importable from ultralytics or extra_modules")
        if any(
            node["type"] not in _TORCH_NN_MODULES and node["type"] not in _INLINE_ATOMIC_MODULES
            for node in sub_nodes
        ):
            lines.append("")

    lines.append(f"class {class_name}(nn.Module):")
    lines.append(f'    """Auto-generated module: {class_name}"""')
    lines.append("")

    if init_params:
        params_str = ", ".join(init_params)
        lines.append(f"    def __init__(self, {params_str}):")
    else:
        lines.append("    def __init__(self):")
    lines.append("        super().__init__()")
    lines.append("")

    for node_id in topo_order:
        node = node_map[node_id]
        node_type = node["type"]
        params = node.get("params", {})
        attr_name = name_map[node_id][0]
        param_strs = [f"{k}={_format_param_value(v)}" for k, v in params.items()]
        module_ref = _get_module_ref(node_type)
        params_code = ", ".join(param_strs)
        lines.append(f"        self.{attr_name} = {module_ref}({params_code})")

    lines.append("")

    forward_params = [pi["name"] for pi in proxy_inputs]
    if forward_params:
        fp_str = ", ".join(forward_params)
        lines.append(f"    def forward(self, {fp_str}):")
    else:
        lines.append("    def forward(self):")

    for node_id in topo_order:
        var_name = name_map[node_id][1]
        attr_name = name_map[node_id][0]
        inputs = _get_node_inputs(node_id, sub_edges, proxy_inputs, name_map, node_map)
        inputs_str = ", ".join(inputs)
        lines.append(f"        {var_name} = self.{attr_name}({inputs_str})")

    if proxy_outputs:
        return_vars = []
        for po in proxy_outputs:
            src_id = po["sub_node_id"]
            src_port = po.get("port_index", 0)
            var = name_map[src_id][1]
            src_type = node_map[src_id]["type"]
            if src_port > 0 or src_type in _MULTI_OUTPUT_TYPES:
                var = f"{var}[{src_port}]"
            return_vars.append(var)
        if len(return_vars) == 1:
            lines.append(f"        return {return_vars[0]}")
        else:
            lines.append(f"        return {', '.join(return_vars)}")

    return "\n".join(lines) + "\n"


def write_module_file(
    schema_json: Dict[str, Any],
    expand_composites: bool,
    output_dir: Path,
    resolver: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
) -> Path:
    code = generate_module_code(schema_json, expand_composites=expand_composites, _resolver=resolver)
    class_name = _get_class_name(schema_json)
    output_path = output_dir / f"{class_name}.py"
    output_path.write_text(code, encoding="utf-8")
    return output_path
