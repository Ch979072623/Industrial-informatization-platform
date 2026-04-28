"""
P5-S3-Recon-2: B-2 codegen 生成类 vs ultralytics parse_model 兼容性 PoC

验证 4 个论文代表类:
1. PMSFA - 单输入, 简单签名
2. FocusFeature - 多输入, 空 args
3. CSP_PMSFA - 派生 C2f, 继承内置处理
4. Detect_SASD - head 模块, 带 nc

每个类的验证分 2 个维度:
- A. 直接实例化: 用 YAML  args(按 params_schema 顺序) 直接调用生成类的 __init__
- B. ultralytics 加载: setattr 注入 → 写最小 yaml → YOLO(yaml_path) 构造

用法:
    cd backend && conda activate defect-detection
    python scripts/recon_codegen_signature_poc.py
"""
import sys
import json
import tempfile
import traceback
from pathlib import Path

import torch
import torch.nn as nn

from app.ml.runtime.codegen import generate_module_code
from app.ml.modules.dynamic_builder import _default_schema_resolver


def _load_schema(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "app" / "ml" / "modules" / "composite" / name / "schema.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _exec_generated_code(schema: dict) -> type:
    """codegen 生成代码 → exec → 返回类对象"""
    code = generate_module_code(schema, expand_composites=True, _resolver=_default_schema_resolver)
    namespace = {"torch": torch, "nn": nn}
    exec(compile(code, "<generated>", "exec"), namespace)
    class_name = schema.get("type", "GeneratedModule")
    return namespace[class_name], code


# === 4 个待验证类配置 ===
TARGETS = [
    {
        "name": "PMSFA",
        "schema": _load_schema("pmsfa"),
        # YAML args 按 params_schema 顺序: inc
        "yaml_args": [64],
        "yaml_template": """nc: 1
scales:
  n: [1.0, 1.0, 1024]
backbone:
  - [-1, 1, Conv, [64, 3, 2]]
  - [-1, 1, PMSFA, [64]]
head:
  - [-1, 1, Classify, [nc]]
""",
        "input_shape": (1, 3, 64, 64),
    },
    {
        "name": "FocusFeature",
        "schema": _load_schema("focusfeature"),
        # params_schema 顺序: inc, kernel_sizes, e
        "yaml_args": [[512, 256, 128], [5, 7, 9, 11], 0.5],
        "yaml_template": """nc: 1
scales:
  n: [1.0, 1.0, 1024]
backbone:
  - [-1, 1, Conv, [128, 3, 2]]
  - [-1, 1, Conv, [256, 3, 2]]
  - [-1, 1, Conv, [512, 3, 2]]
head:
  - [[2, 1, 0], 1, FocusFeature, []]
  - [-1, 1, Classify, [nc]]
""",
        "input_shape": (1, 3, 64, 64),
    },
    {
        "name": "CSP_PMSFA",
        "schema": _load_schema("csp_pmsfa"),
        # params_schema 顺序: c1, c2, n, shortcut, g, e
        "yaml_args": [128, 128, 2, False, 1, 0.5],
        "yaml_template": """nc: 1
scales:
  n: [1.0, 1.0, 1024]
backbone:
  - [-1, 1, Conv, [128, 3, 2]]
  - [-1, 2, CSP_PMSFA, [128, 128]]
head:
  - [-1, 1, Classify, [nc]]
""",
        "input_shape": (1, 3, 64, 64),
    },
    {
        "name": "Detect_SASD",
        "schema": _load_schema("detect_sasd"),
        # params_schema 顺序: nc, hidc, ch, reg_max
        "yaml_args": [1, 256, [256, 512, 1024], 16],
        "yaml_template": """nc: 1
scales:
  n: [1.0, 1.0, 1024]
backbone:
  - [-1, 1, Conv, [256, 3, 2]]
  - [-1, 1, Conv, [512, 3, 2]]
  - [-1, 1, Conv, [1024, 3, 2]]
head:
  - [[2, 1, 0], 1, Detect_SASD, [nc, 256]]
""",
        "input_shape": (1, 3, 64, 64),
    },
]


def verify_direct_instantiation(target: dict) -> dict:
    """维度 A: 直接用 YAML args(按 params_schema 顺序) 实例化生成类"""
    result = {
        "step": "A.direct_instantiation",
        "status": "untested",
        "error": None,
    }
    try:
        cls, code = _exec_generated_code(target["schema"])
        args = target["yaml_args"]
        instance = cls(*args)
        result["status"] = "pass"
        result["init_signature"] = str(instance.__init__)
    except Exception as e:
        result["status"] = "fail"
        result["error"] = traceback.format_exc()
    return result


def verify_yolo_load(target: dict) -> dict:
    """维度 B: setattr 注入 → YOLO(yaml_path) 构造"""
    result = {
        "step": "B.yolo_load",
        "status": "untested",
        "error": None,
    }
    yaml_path = None
    try:
        cls, code = _exec_generated_code(target["schema"])
        import ultralytics.nn.tasks as tasks
        setattr(tasks, target["name"], cls)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(target["yaml_template"])
            yaml_path = f.name

        from ultralytics import YOLO
        model = YOLO(yaml_path)
        result["status"] = "construct_ok"

        # forward 1 步
        dummy = torch.randn(*target["input_shape"])
        with torch.no_grad():
            output = model.model(dummy)
        result["status"] = "forward_ok"
        result["output_type"] = str(type(output))
    except Exception as e:
        result["status"] = "fail"
        result["error"] = traceback.format_exc()
    finally:
        if yaml_path:
            try:
                Path(yaml_path).unlink(missing_ok=True)
            except Exception:
                pass
    return result


def verify_class(target: dict) -> dict:
    """综合验证一个类"""
    print(f"\n{'='*60}")
    print(f"[{target['name']}] 开始验证")
    print(f"{'='*60}")

    # 先生成代码并打印签名
    cls, code = _exec_generated_code(target["schema"])
    import inspect
    sig = inspect.signature(cls.__init__)
    print(f"  codegen 生成签名: {sig}")
    print(f"  params_schema 顺序: {[p['name'] for p in target['schema'].get('params_schema', [])]}")
    print(f"  YAML args(按 params_schema): {target['yaml_args']}")

    # A. 直接实例化
    r_a = verify_direct_instantiation(target)
    print(f"  A. 直接实例化: {r_a['status']}")
    if r_a["error"]:
        print(f"      失败详情:\n{r_a['error']}")

    # B. ultralytics 加载
    r_b = verify_yolo_load(target)
    print(f"  B. ultralytics 加载: {r_b['status']}")
    if r_b["error"]:
        print(f"      失败详情:\n{r_b['error']}")

    return {
        "name": target["name"],
        "signature": str(sig),
        "direct": r_a,
        "yolo": r_b,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("P5-S3-Recon-2: Codegen Signature Compatibility PoC")
    print("=" * 60)

    results = []
    for target in TARGETS:
        results.append(verify_class(target))

    print("\n" + "=" * 60)
    print("汇总表")
    print("=" * 60)
    print(f"{'类':<15} {'codegen 签名':<35} {'直接实例化':<12} {'YOLO 加载':<12}")
    print("-" * 80)
    for r in results:
        sig_short = r["signature"].replace("<bound method ", "").replace(" of ...>", "")
        direct = r["direct"]["status"]
        yolo = r["yolo"]["status"]
        print(f"{r['name']:<15} {sig_short:<35} {direct:<12} {yolo:<12}")

    # 退出码
    all_pass = all(r["direct"]["status"] == "pass" and r["yolo"]["status"] == "forward_ok" for r in results)
    sys.exit(0 if all_pass else 1)
