"""
Codegen 单元测试

覆盖 generate_module_code 和 convert_expr 的核心逻辑。
不访问数据库、不写文件、不 mock 内部逻辑。
"""
import json
from pathlib import Path

import pytest

from app.ml.runtime.codegen import generate_module_code, convert_expr, CodegenError


# ============ 辅助：加载 builtin schema ============

def _load_schema(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "app" / "ml" / "modules" / "composite" / name / "schema.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ============ convert_expr 测试 ============

def test_convert_expr_variable():
    assert convert_expr("${c}") == "c"


def test_convert_expr_arithmetic():
    assert convert_expr("${c * 2}") == "c * 2"
    assert convert_expr("${inc // 2}") == "inc // 2"
    assert convert_expr("${a + b - 1}") == "a + b - 1"


def test_convert_expr_literal_passthrough():
    assert convert_expr("64") == "64"
    assert convert_expr("hello") == "hello"
    assert convert_expr("True") == "True"


def test_convert_expr_int_float_allowed():
    assert convert_expr("${int(x * 2)}") == "int(x * 2)"
    assert convert_expr("${float(y)}") == "float(y)"


def test_convert_expr_unsupported_function_raises():
    with pytest.raises(CodegenError):
        convert_expr("${max(a, b)}")


def test_convert_expr_attribute_call_raises():
    with pytest.raises(CodegenError):
        convert_expr("${x.chunk(2)}")


# ============ generate_module_code 测试 ============

def test_codegen_pmsfa():
    schema = _load_schema("pmsfa")
    code = generate_module_code(schema, expand_composites=False)
    assert "class PMSFA(nn.Module):" in code


def test_codegen_focusfeature():
    schema = _load_schema("focusfeature")
    code = generate_module_code(schema, expand_composites=False)
    assert "class FocusFeature(nn.Module):" in code


def test_codegen_detect_sasd():
    schema = _load_schema("detect_sasd")
    code = generate_module_code(schema, expand_composites=False)
    assert "class Detect_SASD(nn.Module):" in code


def test_codegen_valid_python():
    for name in ("pmsfa", "focusfeature", "detect_sasd"):
        schema = _load_schema(name)
        code = generate_module_code(schema, expand_composites=False)
        compile(code, "<string>", "exec")


def test_codegen_init_has_params():
    schema = _load_schema("pmsfa")
    code = generate_module_code(schema, expand_composites=False)
    assert "def __init__(self, inc):" in code


def test_codegen_cycle_raises():
    schema = {
        "type": "CycleTest",
        "sub_nodes": [
            {"id": "a", "type": "Conv2d", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "b", "type": "Conv2d", "params": {}, "position": {"x": 0, "y": 0}},
        ],
        "sub_edges": [
            {"source": "a", "source_port": 0, "target": "b", "target_port": 0},
            {"source": "b", "source_port": 0, "target": "a", "target_port": 0},
        ],
        "proxy_inputs": [{"sub_node_id": "a", "port_index": 0, "name": "x"}],
        "proxy_outputs": [{"sub_node_id": "b", "port_index": 0, "name": "out"}],
    }
    with pytest.raises(CodegenError):
        generate_module_code(schema, expand_composites=False)


def test_codegen_forward_params_from_proxy_inputs():
    schema = _load_schema("focusfeature")
    code = generate_module_code(schema, expand_composites=False)
    assert "def forward(self, p5_in, p4_in, p3_in):" in code


def test_codegen_multi_output_indexing():
    schema = _load_schema("pmsfa")
    code = generate_module_code(schema, expand_composites=False)
    # Chunk 下游应使用索引访问
    assert "chunk_0[0]" in code or "chunk_0[1]" in code


def test_codegen_expand_composites_false_adds_note():
    schema = _load_schema("focusfeature")
    code = generate_module_code(schema, expand_composites=False)
    assert "# NOTE: ADown must be importable" in code
