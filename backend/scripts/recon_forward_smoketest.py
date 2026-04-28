"""
recon_forward_smoketest.py — 验证 patch 后论文模块在 ultralytics 真实前向路径下能跑通

不同于 recon_codegen_signature_poc.py(只验证 model load),本脚本验证完整 forward 路径,
即模拟 ultralytics 内部的 _predict_once 调用链(m(x) 其中 x 是 list for multi-input modules)。
"""
import json
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict

import torch
import torch.nn as nn

from app.ml.runtime.codegen import generate_module_code
from app.ml.runtime.ultralytics_patch import apply_ultralytics_patches
from app.ml.modules.dynamic_builder import _default_schema_resolver


def _exec_generated(schema: Dict[str, Any]) -> nn.Module:
    code_str = generate_module_code(schema, expand_composites=True, _resolver=_default_schema_resolver)
    namespace: Dict[str, Any] = {}
    exec(compile(code_str, "<generated>", "exec"), namespace)
    class_name = schema.get("type", "GeneratedModule")
    params = {p["name"]: p.get("default") for p in schema.get("params_schema", [])}
    param_order = [p["name"] for p in schema.get("params_schema", [])]
    args = [params[k] for k in param_order]
    return namespace[class_name](*args)


def _predict_once(model, save, x):
    """精确模拟 ultralytics BaseModel._predict_once 的多输入调用链。"""
    y = []
    for i, m in enumerate(model):
        if m.f != -1:
            x = y[m.f] if isinstance(m.f, int) else [x if j == -1 else y[j] for j in m.f]
        x = m(x)
        y.append(x if i in save else None)
    return x


def _write_yaml(yaml_dict: dict) -> str:
    import yaml
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        yaml.dump(yaml_dict, f, default_flow_style=False, allow_unicode=True)
        return f.name


def run_all():
    apply_ultralytics_patches()
    import ultralytics.nn.tasks as tasks

    results = []

    # ========================================================================
    # Test 1: 标准 yolo 前向(对照组,验证 patch 不破坏官方)
    # ========================================================================
    print("[Test 1] standard yolo forward ...")
    try:
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
        print(f"[Test 1] standard yolo forward: PASS (out shape={out.shape})")
        results.append(("Test 1", True, None))
    except Exception as e:
        print(f"[Test 1] standard yolo forward: FAIL ({e})")
        traceback.print_exc()
        results.append(("Test 1", False, str(e)))

    # ========================================================================
    # Test 2: FocusFeature 在完整链路中的 forward
    # ========================================================================
    print("\n[Test 2] yolo + FocusFeature forward ...")
    try:
        schema = json.load(open("app/ml/modules/composite/focusfeature/schema.json", encoding="utf-8"))
        module = _exec_generated(schema)
        tasks.FocusFeature = module.__class__

        yaml_dict = {
            "nc": 1,
            "scales": {"n": [1.0, 1.0, 1024]},
            "backbone": [
                [-1, 1, "Conv", [128, 3, 2]],   # 0: 320x320
                [-1, 1, "Conv", [256, 3, 2]],   # 1: 160x160
                [-1, 1, "Conv", [512, 3, 2]],   # 2: 80x80
            ],
            "head": [
                [[2, 1, 0], 1, "FocusFeature", []],   # P5, P4, P3
                [-1, 1, "Classify", [1]],
            ],
        }
        model, save = tasks.parse_model(yaml_dict, ch=3, verbose=False)
        x = torch.randn(1, 3, 640, 640)
        out = _predict_once(model, save, x)
        assert isinstance(out, torch.Tensor), f"expected Tensor, got {type(out)}"
        print(f"[Test 2] yolo + FocusFeature forward: PASS (out shape={out.shape})")
        results.append(("Test 2", True, None))
    except Exception as e:
        print(f"[Test 2] yolo + FocusFeature forward: FAIL ({e})")
        traceback.print_exc()
        results.append(("Test 2", False, str(e)))

    # ========================================================================
    # Test 3: Detect_SASD 在完整链路中的 forward
    # ========================================================================
    print("\n[Test 3] yolo + Detect_SASD forward ...")
    try:
        schema = json.load(open("app/ml/modules/composite/detect_sasd/schema.json", encoding="utf-8"))
        module = _exec_generated(schema)
        tasks.Detect_SASD = module.__class__

        yaml_dict = {
            "nc": 1,
            "scales": {"n": [1.0, 1.0, 1024]},
            "backbone": [
                [-1, 1, "Conv", [256, 3, 2]],   # 0: 320x320
                [-1, 1, "Conv", [512, 3, 2]],   # 1: 160x160
                [-1, 1, "Conv", [1024, 3, 2]],  # 2: 80x80
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
        print(f"[Test 3] yolo + Detect_SASD forward: PASS (out shapes={[o.shape for o in out]})")
        results.append(("Test 3", True, None))
    except Exception as e:
        print(f"[Test 3] yolo + Detect_SASD forward: FAIL ({e})")
        traceback.print_exc()
        results.append(("Test 3", False, str(e)))

    # ========================================================================
    # Summary
    # ========================================================================
    print("\n" + "=" * 60)
    print("SMOKE TEST SUMMARY")
    print("=" * 60)
    for name, ok, err in results:
        status = "PASS" if ok else "FAIL"
        detail = "" if ok else f" ({err})"
        print(f"  [{name}] {status}{detail}")
    all_pass = all(ok for _, ok, _ in results)
    print("=" * 60)
    print(f"OVERALL: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return all_pass


if __name__ == "__main__":
    run_all()
