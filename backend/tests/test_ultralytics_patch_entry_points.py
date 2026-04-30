"""
验证 ultralytics patch 在生产入口点的嵌入

覆盖:
- celery_worker.py 模块导入时触发 patch
- FastAPI lifespan startup 阶段触发 patch
- patch 幂等性（多次入口调用不抛异常）

生产路径模拟(教训 26):
- Celery: 干净 Python 进程 → import celery_worker → 模块级代码执行 → patch 触发
- FastAPI: uvicorn 启动 → lifespan startup → patch 触发
"""

import os
import subprocess
import sys

import pytest
import ultralytics.nn.tasks as tasks

from app.ml.runtime.ultralytics_patch import _PATCHED, apply_ultralytics_patches
from app.main import app


def _assert_patched() -> None:
    """断言 parse_model 与 guess_model_task 已是 patched 版本。"""
    assert tasks.parse_model.__code__.co_filename == "<patched_parse_model>", (
        "parse_model is not patched"
    )
    assert tasks.guess_model_task.__code__.co_filename == "<patched_guess_model_task>", (
        "guess_model_task is not patched"
    )


def test_celery_worker_import_applies_patches() -> None:
    """
    生产路径: celery worker 启动时全新导入 celery_worker 模块，
    顶部的 apply_ultralytics_patches() 被触发。

    用子进程模拟干净进程，避免 pytest 主进程中已有模块状态干扰。
    """
    backend_dir = os.path.join(os.path.dirname(__file__), "..")
    code = (
        "import sys; sys.path.insert(0, '.');"
        "import app.ml.runtime.ultralytics_patch as _p; _p._PATCHED = False;"
        "import celery_worker;"
        "import ultralytics.nn.tasks as t;"
        "assert _p._PATCHED is True, 'PATCHED flag not set after celery_worker import';"
        "assert t.parse_model.__code__.co_filename == '<patched_parse_model>', 'parse_model not patched';"
        "assert t.guess_model_task.__code__.co_filename == '<patched_guess_model_task>', 'guess_model_task not patched';"
        "print('OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=backend_dir,
    )
    assert result.returncode == 0, (
        f"celery_worker import did not apply patches.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK" in result.stdout


@pytest.mark.asyncio
async def test_lifespan_startup_applies_patches() -> None:
    """
    生产路径: FastAPI lifespan startup 阶段调用 apply_ultralytics_patches()。

    直接驱动 lifespan async contextmanager，验证 startup 后 patch 已生效。
    即使之前其他测试已触发 patch，本测试至少验证 lifespan 执行路径可用且 patch 状态正确。
    """
    from app.core.events import lifespan

    async with lifespan(app):
        _assert_patched()


def test_patch_idempotent_across_entry_points() -> None:
    """
    幂等性: 多次调用 apply_ultralytics_patches() 不抛异常且状态稳定。

    对应场景: worker 重启、lifespan 重入、热重载等多次触发入口。
    """
    apply_ultralytics_patches()
    apply_ultralytics_patches()
    apply_ultralytics_patches()
    _assert_patched()
