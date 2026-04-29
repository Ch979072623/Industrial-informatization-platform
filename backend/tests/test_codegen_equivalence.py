"""
B-4: 验证 generate_module_code 生成的静态代码与 schema_to_module 动态构图的
forward() 输出数值等价。

覆盖：PMSFA / FocusFeature / Detect_SASD + 3 个其他 builtin composite。
关键约束：使用位置参数实例化生成类，模拟 ultralytics parse_model 生产调用模式。
"""

import inspect
import json
from pathlib import Path
from typing import Any, Dict

import torch
import torch.nn as nn

from app.ml.runtime.codegen import generate_module_code
from app.ml.modules.dynamic_builder import schema_to_module, _default_schema_resolver


# 测试内对已知 codegen 生成缺陷做补丁，不修改生产代码。
# C-1.1 修复后 Conv_GN 默认值已对齐，保留空列表以兼容历史机制。
_KNOWN_CODE_PATCHES = []


def _patch_generated_code(code_str: str) -> str:
    """对生成代码字符串做测试侧补丁，修复已知参数默认值缺失问题。"""
    for old, new in _KNOWN_CODE_PATCHES:
        code_str = code_str.replace(old, new)
    return code_str


def _set_uniform_weights(module: nn.Module, value: float = 0.1) -> None:
    """将模块所有可训练参数填充为同一常量，保证两路径权重一致。"""
    with torch.no_grad():
        for param in module.parameters():
            param.fill_(value)


def _default_params(schema: Dict[str, Any]) -> Dict[str, Any]:
    """从 params_schema 提取默认值构造实例化参数。"""
    params: Dict[str, Any] = {}
    for spec in schema.get("params_schema", []):
        params[spec["name"]] = spec.get("default")
    return params


def _exec_generated_positional(schema: Dict[str, Any]) -> nn.Module:
    """路径 A：generate_module_code → exec → 用位置参数实例化（模拟 ultralytics parse_model）。"""
    code_str = generate_module_code(schema, expand_composites=True, _resolver=_default_schema_resolver)
    code_str = _patch_generated_code(code_str)
    namespace: Dict[str, Any] = {}
    exec(compile(code_str, "<generated>", "exec"), namespace)
    class_name = schema.get("type", "GeneratedModule")
    params = _default_params(schema)
    # 按 params_schema 顺序构造位置参数 args，模拟 ultralytics parse_model 的 *args 调用
    param_order = [p["name"] for p in schema.get("params_schema", [])]
    args = [params[k] for k in param_order]
    return namespace[class_name](*args)


def _build_dynamic(schema: Dict[str, Any]) -> nn.Module:
    """路径 B：schema_to_module 动态构图。"""
    params = _default_params(schema)
    return schema_to_module(schema, parent_params=params)


def _assert_close(out_a, out_b):
    """统一比较单输出或多输出（tuple）的情况。"""
    if isinstance(out_a, tuple):
        assert isinstance(out_b, tuple)
        assert len(out_a) == len(out_b)
        for a, b in zip(out_a, out_b):
            assert torch.allclose(a, b, atol=1e-4, rtol=1e-4)
    else:
        assert torch.allclose(out_a, out_b, atol=1e-4, rtol=1e-4)


# ---------------------------------------------------------------------------
# 论文模块（3个）— 使用位置参数调用模拟 parse_model 生产场景
# ---------------------------------------------------------------------------

def test_parse_model_positional_call_compat_pmsfa():
    schema = json.load(open("app/ml/modules/composite/pmsfa/schema.json", encoding="utf-8"))
    module_a = _exec_generated_positional(schema)
    module_b = _build_dynamic(schema)

    _set_uniform_weights(module_a, 0.1)
    _set_uniform_weights(module_b, 0.1)

    torch.manual_seed(42)
    x = torch.randn(1, 64, 32, 32)

    out_a = module_a(x)
    out_b = module_b(x)

    _assert_close(out_a, out_b)


def test_parse_model_positional_call_compat_focusfeature():
    schema = json.load(open("app/ml/modules/composite/focusfeature/schema.json", encoding="utf-8"))
    module_a = _exec_generated_positional(schema)
    module_b = _build_dynamic(schema)

    _set_uniform_weights(module_a, 0.1)
    _set_uniform_weights(module_b, 0.1)

    torch.manual_seed(42)
    p5_in = torch.randn(1, 512, 8, 8)
    p4_in = torch.randn(1, 256, 16, 16)
    p3_in = torch.randn(1, 128, 32, 32)

    inputs = [p5_in, p4_in, p3_in]
    out_a = module_a(inputs)
    out_b = module_b(inputs)

    _assert_close(out_a, out_b)


def test_parse_model_positional_call_compat_detect_sasd():
    schema = json.load(open("app/ml/modules/composite/detect_sasd/schema.json", encoding="utf-8"))
    module_a = _exec_generated_positional(schema)
    module_b = _build_dynamic(schema)

    _set_uniform_weights(module_a, 0.1)
    _set_uniform_weights(module_b, 0.1)

    torch.manual_seed(42)
    n3_in = torch.randn(1, 256, 32, 32)
    n4_in = torch.randn(1, 512, 32, 32)
    n5_in = torch.randn(1, 1024, 32, 32)

    inputs = [n3_in, n4_in, n5_in]
    out_a = module_a(inputs)
    out_b = module_b(inputs)

    _assert_close(out_a, out_b)


# ---------------------------------------------------------------------------
# 其他 builtin composite（3个）— 同样使用位置参数
# ---------------------------------------------------------------------------

def test_parse_model_positional_call_compat_adown():
    schema = json.load(open("app/ml/modules/composite/adown/schema.json", encoding="utf-8"))
    module_a = _exec_generated_positional(schema)
    module_b = _build_dynamic(schema)

    _set_uniform_weights(module_a, 0.1)
    _set_uniform_weights(module_b, 0.1)

    torch.manual_seed(42)
    x = torch.randn(1, 128, 32, 32)

    out_a = module_a(x)
    out_b = module_b(x)

    _assert_close(out_a, out_b)


def test_parse_model_positional_call_compat_resblock():
    schema = json.load(open("app/ml/modules/composite/resblock/schema.json", encoding="utf-8"))
    module_a = _exec_generated_positional(schema)
    module_b = _build_dynamic(schema)

    _set_uniform_weights(module_a, 0.1)
    _set_uniform_weights(module_b, 0.1)

    torch.manual_seed(42)
    x = torch.randn(1, 64, 32, 32)

    out_a = module_a(x)
    out_b = module_b(x)

    _assert_close(out_a, out_b)


def test_parse_model_positional_call_compat_fpn():
    schema = json.load(open("app/ml/modules/composite/fpn/schema.json", encoding="utf-8"))
    module_a = _exec_generated_positional(schema)
    module_b = _build_dynamic(schema)

    _set_uniform_weights(module_a, 0.1)
    _set_uniform_weights(module_b, 0.1)

    torch.manual_seed(42)
    p5 = torch.randn(1, 512, 8, 8)
    p4 = torch.randn(1, 256, 16, 16)
    p3 = torch.randn(1, 128, 32, 32)

    inputs = [p5, p4, p3]
    out_a = module_a(inputs)
    out_b = module_b(inputs)

    _assert_close(out_a, out_b)


# ---------------------------------------------------------------------------
# Forward 列表调用协议测试（D12）— 验证 codegen 生成代码在 ultralytics m(x) 调用下正常
# ---------------------------------------------------------------------------

def test_forward_list_call_compat_focusfeature():
    """验证 codegen 生成的 FocusFeature 在 ultralytics m(x) 列表调用下 forward 正常。"""
    schema = json.load(open("app/ml/modules/composite/focusfeature/schema.json", encoding="utf-8"))
    module = _exec_generated_positional(schema)
    _set_uniform_weights(module, 0.1)

    torch.manual_seed(42)
    x = [
        torch.randn(1, 512, 8, 8),
        torch.randn(1, 256, 16, 16),
        torch.randn(1, 128, 32, 32),
    ]
    out = module(x)

    assert isinstance(out, torch.Tensor)
    # 输出通道数 = int(inc[1] * e) * 3 = int(256 * 0.5) * 3 = 384
    assert out.shape[1] == 384


def test_forward_list_call_compat_detect_sasd():
    """验证 codegen 生成的 Detect_SASD 在 ultralytics m(x) 列表调用下 forward 正常。"""
    schema = json.load(open("app/ml/modules/composite/detect_sasd/schema.json", encoding="utf-8"))
    module = _exec_generated_positional(schema)
    _set_uniform_weights(module, 0.1)

    torch.manual_seed(42)
    x = [
        torch.randn(1, 256, 32, 32),
        torch.randn(1, 512, 32, 32),
        torch.randn(1, 1024, 32, 32),
    ]
    out = module(x)

    assert isinstance(out, tuple)
    assert len(out) == 3
    for o in out:
        assert isinstance(o, torch.Tensor)


def test_forward_list_call_compat_fpn():
    """验证 codegen 生成的 FPN 在 ultralytics m(x) 列表调用下 forward 正常。"""
    schema = json.load(open("app/ml/modules/composite/fpn/schema.json", encoding="utf-8"))
    module = _exec_generated_positional(schema)
    _set_uniform_weights(module, 0.1)

    torch.manual_seed(42)
    x = [
        torch.randn(1, 512, 8, 8),
        torch.randn(1, 256, 16, 16),
        torch.randn(1, 128, 32, 32),
    ]
    out = module(x)

    assert isinstance(out, tuple)
    assert len(out) == 3
    for o in out:
        assert isinstance(o, torch.Tensor)
