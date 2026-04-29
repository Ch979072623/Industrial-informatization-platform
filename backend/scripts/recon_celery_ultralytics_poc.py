"""
P5-S3-Recon: Celery worker + ultralytics setattr 注入可行性 PoC

验证场景:
1. eager 模式 - task 内 setattr, YOLO 构造成功
2. eager 模式 - 多 task 顺序执行, setattr 不冲突
3. 真 worker 模式 - 投递 task, YOLO 构造成功
4. 真 worker 模式 - 连续投递 2 个 task, 第二个不被第一个污染
5. forward 1 步 - 实例化模型 + forward 随机输入

用法:
    cd backend && conda activate defect-detection
    # 场景 1-2 + 5(eager):
    python scripts/recon_celery_ultralytics_poc.py --mode eager
    # 场景 3-4(真 worker):
    # 终端 1: celery -A scripts.recon_celery_ultralytics_poc:app worker --pool=solo --concurrency=1 --loglevel=INFO
    # 终端 2: python scripts/recon_celery_ultralytics_poc.py --mode worker
"""
import sys
import argparse
import tempfile
import traceback
from pathlib import Path

import torch
import torch.nn as nn
from celery import Celery

# === 1. 定义最简自定义 nn.Module 类 ===
class MyTestBlock(nn.Module):
    """最简化测试类: Conv 包装, 验证 ultralytics parse_model 能找到注入的类

    注意: ultralytics parse_model 对 custom module 不自动 prepend c1,
    也不按 width 系数缩放 args[0]。因此本类采用 lazy init，
    在第一次 forward 时根据实际输入通道数创建 conv，避免签名不匹配。
    """
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._args = args
        self._kwargs = kwargs
        self._inited = False

    def forward(self, x):
        if not self._inited:
            c = x.size(1)
            self.conv = nn.Conv2d(c, c, 3, padding=1, bias=False).to(x.device)
            self.bn = nn.BatchNorm2d(c).to(x.device)
            self.act = nn.SiLU()
            self._inited = True
        return self.act(self.bn(self.conv(x)))


# === 2. Celery app (独立 app, 不污染项目主 app) ===
app = Celery(
    'scripts.recon_celery_ultralytics_poc',
    broker='redis://localhost:6379/3',
    backend='redis://localhost:6379/4'
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# === 3. yaml 字符串 (用 MyTestBlock) ===
SAMPLE_YAML = """nc: 1
scales:
  n: [0.33, 0.25, 1024]

backbone:
  - [-1, 1, Conv, [16, 3, 2]]
  - [-1, 1, MyTestBlock, [16]]
  - [-1, 1, Conv, [32, 3, 2]]

head:
  - [-1, 1, Classify, [nc]]
"""


# === 4. 注入 + 构造任务 ===
@app.task(bind=True)
def construct_yolo_task(self, scenario: str):
    """task 内执行 setattr 注入 + YOLO 构造 + forward"""
    import ultralytics.nn.tasks as tasks
    from ultralytics import YOLO

    yaml_path = None
    try:
        # 注入 (故意不检查是否已存在, 验证多 task 场景)
        already_present = hasattr(tasks, 'MyTestBlock')
        setattr(tasks, 'MyTestBlock', MyTestBlock)

        # 写临时 yaml
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(SAMPLE_YAML)
            yaml_path = f.name

        # 构造
        model = YOLO(yaml_path)

        # forward 1 步
        dummy = torch.randn(1, 3, 640, 640)
        with torch.no_grad():
            output = model.model(dummy)

        # 提取输出 shape
        if isinstance(output, (list, tuple)):
            out_shape = str(output[0].shape)
        else:
            out_shape = str(output.shape)

        return {
            "scenario": scenario,
            "model_constructed": True,
            "already_present_before_inject": already_present,
            "output_shape": out_shape,
            "error": None,
        }
    except Exception as e:
        return {
            "scenario": scenario,
            "model_constructed": False,
            "already_present_before_inject": None,
            "output_shape": None,
            "error": f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}",
        }
    finally:
        if yaml_path:
            try:
                Path(yaml_path).unlink(missing_ok=True)
            except Exception:
                pass


# === 5. 测试场景调度 ===
def run_eager(scenarios=("scenario_1_first", "scenario_2_second")):
    """eager 模式: 同步执行 task"""
    app.conf.task_always_eager = True
    results = []
    for s in scenarios:
        print(f"[eager] Running {s} ...")
        result = construct_yolo_task.apply(args=[s])
        val = result.get()
        results.append(val)
        print(f"[eager] {s} result: {val}")
    return results


def run_worker(scenarios=("scenario_3_first", "scenario_4_second")):
    """worker 模式: 投递到真 worker"""
    results = []
    for s in scenarios:
        print(f"[worker] Sending {s} ...")
        result = construct_yolo_task.delay(s)
        val = result.get(timeout=60)
        results.append(val)
        print(f"[worker] {s} result: {val}")
    return results


def run_forward_only():
    """场景 5: 单独验证 forward (已在 task 内嵌入, 此函数仅用于显式测试)"""
    import ultralytics.nn.tasks as tasks
    from ultralytics import YOLO

    setattr(tasks, 'MyTestBlock', MyTestBlock)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(SAMPLE_YAML)
        yaml_path = f.name

    try:
        model = YOLO(yaml_path)
        dummy = torch.randn(1, 3, 640, 640)
        with torch.no_grad():
            output = model.model(dummy)

        if isinstance(output, (list, tuple)):
            out_shape = str(output[0].shape)
        else:
            out_shape = str(output.shape)

        print(f"[forward_only] output shape: {out_shape}")
        return True
    except Exception as e:
        print(f"[forward_only] FAILED: {traceback.format_exc()}")
        return False
    finally:
        Path(yaml_path).unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["eager", "worker", "forward"], required=True)
    args = parser.parse_args()

    if args.mode == "eager":
        results = run_eager()
    elif args.mode == "worker":
        results = run_worker()
    else:  # forward
        ok = run_forward_only()
        results = [{"forward_ok": ok}]

    print("=" * 60)
    print(f"Mode: {args.mode}")
    print("Results:")
    for r in results:
        print(f"  - {r}")
    print("=" * 60)
