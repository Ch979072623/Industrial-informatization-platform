"""
验证 ultralytics_patch 的行为:
- patch 幂等性
- FocusFeature / Detect_SASD 在官方 ultralytics 下能加载 + forward
- patch 不影响官方内置模块(Conv / Concat / Detect)的加载行为
"""

import json
from typing import Any, Dict

import torch
import torch.nn as nn

from app.ml.runtime.codegen import generate_module_code
from app.ml.runtime.ultralytics_patch import apply_ultralytics_patches
from app.ml.modules.dynamic_builder import _default_schema_resolver


def _exec_generated(schema: Dict[str, Any]) -> nn.Module:
    """generate_module_code → exec → 返回模块实例(用位置参数调用)。"""
    code_str = generate_module_code(schema, expand_composites=True, _resolver=_default_schema_resolver)
    namespace: Dict[str, Any] = {}
    exec(compile(code_str, "<generated>", "exec"), namespace)
    class_name = schema.get("type", "GeneratedModule")
    params = {p["name"]: p.get("default") for p in schema.get("params_schema", [])}
    param_order = [p["name"] for p in schema.get("params_schema", [])]
    args = [params[k] for k in param_order]
    return namespace[class_name](*args)


def test_apply_patches_idempotent():
    """patch 多次调用安全,不抛异常。"""
    apply_ultralytics_patches()
    apply_ultralytics_patches()
    apply_ultralytics_patches()


def test_focus_feature_loads_in_official_ultralytics():
    """FocusFeature 在官方 ultralytics 下能加载 + forward。"""
    apply_ultralytics_patches()

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
        ],
    }

    model, save = tasks.parse_model(yaml_dict, ch=3, verbose=False)
    assert len(model) == 4

    p5 = torch.randn(1, 512, 8, 8)
    p4 = torch.randn(1, 256, 16, 16)
    p3 = torch.randn(1, 128, 32, 32)
    out = model[-1]([p5, p4, p3])
    assert isinstance(out, torch.Tensor)


def test_detect_sasd_loads_in_official_ultralytics():
    """Detect_SASD 在官方 ultralytics 下能加载 + forward。"""
    apply_ultralytics_patches()

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
    assert len(model) == 4

    n3 = torch.randn(1, 256, 32, 32)
    n4 = torch.randn(1, 512, 32, 32)
    n5 = torch.randn(1, 1024, 32, 32)
    out = model[-1]([n3, n4, n5])
    assert isinstance(out, tuple)
    assert len(out) == 3


def test_patch_does_not_break_concat():
    """patch 不影响官方 Concat 加载行为。"""
    apply_ultralytics_patches()

    import ultralytics.nn.tasks as tasks

    yaml_dict = {
        "nc": 1,
        "scales": {"n": [1.0, 1.0, 1024]},
        "backbone": [
            [-1, 1, "Conv", [64, 3, 2]],
            [-1, 1, "Conv", [128, 3, 2]],
        ],
        "head": [
            [[-1, 0], 1, "Concat", [1]],
        ],
    }

    model, save = tasks.parse_model(yaml_dict, ch=3, verbose=False)
    assert len(model) == 3
    from ultralytics.nn.modules import Concat
    assert isinstance(model[-1], Concat)


def test_patch_does_not_break_detect():
    """patch 不影响官方 Detect 加载行为。"""
    apply_ultralytics_patches()

    import ultralytics.nn.tasks as tasks

    # 官方 Detect 需要多输入 f 列表(如 yolov8 的 [[15,18,21], 1, Detect, [nc]])
    yaml_dict = {
        "nc": 80,
        "scales": {"n": [1.0, 1.0, 1024]},
        "backbone": [
            [-1, 1, "Conv", [64, 3, 2]],
            [-1, 1, "Conv", [128, 3, 2]],
            [-1, 1, "Conv", [256, 3, 2]],
            [-1, 1, "Conv", [512, 3, 2]],
            [-1, 1, "Conv", [1024, 3, 2]],
            [-1, 1, "Conv", [512, 3, 2]],
            [-1, 1, "Conv", [256, 3, 2]],
            [-1, 1, "Conv", [128, 3, 2]],
            [-1, 1, "Conv", [64, 3, 2]],
            [-1, 1, "Conv", [128, 3, 2]],
            [-1, 1, "Conv", [256, 3, 2]],
            [-1, 1, "Conv", [512, 3, 2]],
            [-1, 1, "Conv", [1024, 3, 2]],
            [-1, 1, "Conv", [512, 3, 2]],
            [-1, 1, "Conv", [256, 3, 2]],
            [-1, 1, "Conv", [128, 3, 2]],
            [-1, 1, "Conv", [64, 3, 2]],
            [-1, 1, "Conv", [128, 3, 2]],
            [-1, 1, "Conv", [256, 3, 2]],
            [-1, 1, "Conv", [512, 3, 2]],
            [-1, 1, "Conv", [1024, 3, 2]],
        ],
        "head": [
            [[15, 18, 20], 1, "Detect", [80]],
        ],
    }

    model, save = tasks.parse_model(yaml_dict, ch=3, verbose=False)
    assert len(model) == 22
    from ultralytics.nn.modules import Detect
    assert isinstance(model[-1], Detect)


def test_patch_does_not_break_conv():
    """patch 不影响官方 Conv 加载行为。"""
    apply_ultralytics_patches()

    import ultralytics.nn.tasks as tasks

    yaml_dict = {
        "nc": 1,
        "scales": {"n": [1.0, 1.0, 1024]},
        "backbone": [
            [-1, 1, "Conv", [64, 3, 2]],
            [-1, 1, "Conv", [128, 3, 2]],
        ],
        "head": [],
    }

    model, save = tasks.parse_model(yaml_dict, ch=3, verbose=False)
    assert len(model) == 2
    from ultralytics.nn.modules import Conv
    assert isinstance(model[0], Conv)
    assert isinstance(model[1], Conv)
