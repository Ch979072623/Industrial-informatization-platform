"""
test_paper_module_forward_compat.py — 论文模块在 ultralytics 生产路径下的 forward 兼容性回归测试

升级自 backend/scripts/recon_forward_smoketest.py（D17 决策保留备查）。
本测试覆盖 codegen 生成的多输入模块在 ultralytics 真实前向路径下能正常 load + forward。
"""
import json
from typing import Any, Dict

import pytest
import torch
import torch.nn as nn

from app.ml.runtime.codegen import generate_module_code
from app.ml.runtime.ultralytics_patch import apply_ultralytics_patches
from app.ml.modules.dynamic_builder import _default_schema_resolver


@pytest.fixture(scope="session", autouse=True)
def apply_patches_once():
    """session-scoped patch fixture, 全局应用一次"""
    apply_ultralytics_patches()


def _exec_generated(schema: Dict[str, Any]) -> nn.Module:
    """codegen 生成代码 → exec → 返回模块实例"""
    code_str = generate_module_code(schema, expand_composites=True, _resolver=_default_schema_resolver)
    namespace: Dict[str, Any] = {}
    exec(compile(code_str, "<generated>", "exec"), namespace)
    class_name = schema.get("type", "GeneratedModule")
    params = {p["name"]: p.get("default") for p in schema.get("params_schema", [])}
    param_order = [p["name"] for p in schema.get("params_schema", [])]
    args = [params[k] for k in param_order]
    return namespace[class_name](*args)


def _predict_once(model, save, x):
    """模拟 ultralytics BaseModel._predict_once 的多输入调用链"""
    y = []
    for i, m in enumerate(model):
        if m.f != -1:
            x = y[m.f] if isinstance(m.f, int) else [x if j == -1 else y[j] for j in m.f]
        x = m(x)
        y.append(x if i in save else None)
    return x


def test_standard_yolo_forward():
    """patch 不破坏官方标准 yolo 前向路径"""
    import ultralytics.nn.tasks as tasks

    yaml_dict = {
        "nc": 1,
        "scales": {"n": [1.0, 1.0, 1024]},
        "backbone": [
            [-1, 1, "Conv", [64, 3, 2]],
            [-1, 1, "Conv", [128, 3, 2]],
        ],
        "head": [
            [-1, 1, "Classify", [1]],
        ],
    }
    model, save = tasks.parse_model(yaml_dict, ch=3, verbose=False)
    x = torch.randn(1, 3, 640, 640)
    out = _predict_once(model, save, x)

    assert isinstance(out, torch.Tensor), f"expected Tensor, got {type(out)}"
    assert out.shape == torch.Size([1, 1])


def test_yolo_with_focus_feature_forward():
    """codegen 生成的 FocusFeature 在 ultralytics 多输入前向路径下通过"""
    import ultralytics.nn.tasks as tasks

    schema = json.load(open("app/ml/modules/composite/focusfeature/schema.json", encoding="utf-8"))
    module = _exec_generated(schema)
    tasks.FocusFeature = module.__class__

    yaml_dict = {
        "nc": 1,
        "scales": {"n": [1.0, 1.0, 1024]},
        "backbone": [
            [-1, 1, "Conv", [128, 3, 2]],
            [-1, 1, "Conv", [256, 3, 2]],
            [-1, 1, "Conv", [512, 3, 2]],
        ],
        "head": [
            [[2, 1, 0], 1, "FocusFeature", []],
            [-1, 1, "Classify", [1]],
        ],
    }
    model, save = tasks.parse_model(yaml_dict, ch=3, verbose=False)
    x = torch.randn(1, 3, 640, 640)
    out = _predict_once(model, save, x)

    assert isinstance(out, torch.Tensor), f"expected Tensor, got {type(out)}"


def test_yolo_with_detect_sasd_forward():
    """codegen 生成的 Detect_SASD 在 ultralytics 多输入前向路径下通过"""
    import ultralytics.nn.tasks as tasks

    schema = json.load(open("app/ml/modules/composite/detect_sasd/schema.json", encoding="utf-8"))
    module = _exec_generated(schema)
    tasks.Detect_SASD = module.__class__

    yaml_dict = {
        "nc": 1,
        "scales": {"n": [1.0, 1.0, 1024]},
        "backbone": [
            [-1, 1, "Conv", [256, 3, 2]],
            [-1, 1, "Conv", [512, 3, 2]],
            [-1, 1, "Conv", [1024, 3, 2]],
        ],
        "head": [
            [[0, 1, 2], 1, "Detect_SASD", [1, 256]],
        ],
    }
    model, save = tasks.parse_model(yaml_dict, ch=3, verbose=False)
    x = torch.randn(1, 3, 640, 640)
    out = _predict_once(model, save, x)

    assert isinstance(out, (tuple, list)), f"expected tuple/list, got {type(out)}"
    assert len(out) == 3, f"expected 3 outputs, got {len(out)}"
