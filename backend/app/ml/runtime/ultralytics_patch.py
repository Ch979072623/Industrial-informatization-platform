"""
ultralytics_patch.py — 让论文多输入模块在官方 pip ultralytics 下可加载

为什么需要 patch:
  官方 ultralytics 的 parse_model 在 else 分支用 ``c2 = ch[f]`` 处理 args/c2，
  当 ``f`` 是 list（多输入模块如 FocusFeature / Detect_SASD）时报 TypeError。
  本 patch 给这两个论文模块各加一个 elif 分支，处理方式对齐官方对 Detect 的写法。

  此外，官方 ``guess_model_task`` 通过 YAML head 最后一层的模块名推断 task，
  ``Detect_SASD`` 不在其白名单中，导致返回 None 进而触发
  ``NotImplementedError: 'YOLO' model does not support '_new' mode for 'None' task yet``。
  本 patch 同时扩展 ``cfg2task``，将 ``detect_sasd`` 识别为 ``detect`` task。

幂等性:
  ``apply_ultralytics_patches()`` 多次调用安全 — 通过模块级 ``_PATCHED`` 标志实现。

使用:
  在 ultralytics 实际被使用前（如 Celery worker 启动 / FastAPI app 初始化 /
  PoC 脚本顶部）调用一次 ``apply_ultralytics_patches()`` 即可。
"""

import inspect
import types
from typing import Any

import ultralytics.nn.tasks as _ult_tasks

_PATCHED = False


def apply_ultralytics_patches() -> None:
    """幂等 patch 入口。多次调用不重复 patch。"""
    global _PATCHED
    if _PATCHED:
        return
    _patch_parse_model()
    _patch_guess_model_task()
    _PATCHED = True


def _patch_parse_model() -> None:
    """
    重写 ``parse_model`` 以支持 FocusFeature / Detect_SASD 多输入。

    在官方 ``elif m is RTDETRDecoder`` 之后、``else`` 之前插入两个新分支：
    - FocusFeature: 计算多输入通道列表 ``c1`` 和输出通道 ``c2``，将 ``c1`` prepend 到 args。
    - Detect_SASD: 将多输入通道列表 append 到 args（与官方 Detect 分支一致）。
    """
    orig_func = _ult_tasks.parse_model
    source = inspect.getsource(orig_func)

    new_branches = """        elif m is globals().get("FocusFeature"):
            c1 = [ch[x] for x in f]
            e = args[1] if len(args) > 1 else 0.5
            c2 = int(c1[1] * e) * 3
            args = [c1, *args]
        elif m is globals().get("Detect_SASD"):
            args.append([ch[x] for x in f])
            c2 = args[0] if args else 80
"""

    source = source.replace(
        "        else:\n            c2 = ch[f]",
        new_branches + "        else:\n            c2 = ch[f]",
    )

    # 使用虚拟文件名避免 traceback 行号映射到原始文件错误位置
    code_obj = compile(source, "<patched_parse_model>", "exec")
    new_func_code = None
    for const in code_obj.co_consts:
        if isinstance(const, types.CodeType) and const.co_name == "parse_model":
            new_func_code = const
            break

    if new_func_code is None:
        raise RuntimeError("Could not find parse_model code object after patching")

    patched_func = types.FunctionType(new_func_code, orig_func.__globals__, "parse_model")
    _ult_tasks.parse_model = patched_func


def _patch_guess_model_task() -> None:
    """
    扩展 ``guess_model_task`` 的 ``cfg2task`` 子函数，将 ``detect_sasd`` 识别为 ``detect`` task。

    官方 ``cfg2task`` 只识别 ``classify`` / ``detect`` / ``segment`` / ``pose`` 四种 head 模块名。
    论文模块 ``Detect_SASD`` 不在白名单中，导致 ``guess_model_task`` 返回 None，
    进而使 ``YOLO()`` 构造时 ``self.task = None``，触发 ``NotImplementedError``。
    """
    orig_func = _ult_tasks.guess_model_task
    source = inspect.getsource(orig_func)

    source = source.replace(
        "    if m == 'detect':\n            return 'detect'",
        "    if m == 'detect':\n            return 'detect'\n        if m == 'detect_sasd':\n            return 'detect'",
    )

    code_obj = compile(source, "<patched_guess_model_task>", "exec")
    new_func_code = None
    for const in code_obj.co_consts:
        if isinstance(const, types.CodeType) and const.co_name == "guess_model_task":
            new_func_code = const
            break

    if new_func_code is None:
        raise RuntimeError("Could not find guess_model_task code object after patching")

    patched_func = types.FunctionType(new_func_code, orig_func.__globals__, "guess_model_task")
    _ult_tasks.guess_model_task = patched_func
