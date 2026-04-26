"""
YAML 加载验证测试

验证 architecture_to_yaml 生成的 yaml 能被 ultralytics YOLO 正常加载并跑通 forward。
"""
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import torch

# Guard import: skip all tests if ultralytics is not installed
ultralytics = pytest.importorskip("ultralytics")
from ultralytics import YOLO  # noqa: E402
import ultralytics.nn.tasks as tasks  # noqa: E402

from app.ml.runtime.yaml_generator import architecture_to_yaml
from app.ml.runtime.codegen import generate_module_code


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _make_arch(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], nc: int = 80) -> Dict[str, Any]:
    """构造最小 architecture_json，自动补 section/repeats 默认值。"""
    for n in nodes:
        data = n.setdefault("data", {})
        data.setdefault("moduleType", n.get("type", "Unknown"))
        data.setdefault("repeats", 1)
        if "section" not in data:
            raise ValueError(f"节点 {n.get('id')} 必须显式指定 section")
    return {"nodes": nodes, "edges": edges, "num_classes": nc}


def _yaml_to_model(yaml_str: str, tmp_path: Path, extra_module_globals: Optional[Dict[str, Any]] = None):
    """写临时文件 → YOLO 加载 → 返回 model。"""
    yaml_path = tmp_path / "model.yaml"
    yaml_path.write_text(yaml_str, encoding="utf-8")

    # 注册自定义模块到 ultralytics tasks 全局命名空间
    if extra_module_globals:
        for name, cls in extra_module_globals.items():
            setattr(tasks, name, cls)

    model = YOLO(str(yaml_path))
    return model


def _builtin_resolver(module_type: str) -> Optional[Dict[str, Any]]:
    """为常见 builtin 模块提供 params_schema，保证 args 顺序与 ultralytics 期望一致。"""
    schemas = {
        "Conv": {
            "params_schema": [
                {"name": "out_channels", "type": "int"},
                {"name": "kernel_size", "type": "int"},
                {"name": "stride", "type": "int"},
            ]
        },
        "C2f": {
            "params_schema": [
                {"name": "out_channels", "type": "int"},
                {"name": "shortcut", "type": "bool"},
            ]
        },
        "Concat": {
            "params_schema": [
                {"name": "dim", "type": "int"},
            ]
        },
        "Detect": {
            "params_schema": [
                {"name": "nc", "type": "int"},
            ]
        },
        "Classify": {
            "params_schema": [
                {"name": "c2", "type": "int"},
            ]
        },
    }
    return schemas.get(module_type)


# ---------------------------------------------------------------------------
# 测试场景
# ---------------------------------------------------------------------------

class TestLoadBuiltinOnly:
    """只含 builtin 模块（Conv + C2f + Detect）的 yaml 加载与 forward。"""

    def test_load_builtin_only(self, tmp_path: Path):
        arch = _make_arch(
            nodes=[
                {
                    "id": "n1",
                    "type": "Conv",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 64, "kernel_size": 3, "stride": 2},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n2",
                    "type": "Conv",
                    "position": {"x": 0, "y": 100},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 128, "kernel_size": 3, "stride": 2},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n3",
                    "type": "C2f",
                    "position": {"x": 0, "y": 200},
                    "data": {
                        "moduleType": "C2f",
                        "params": {"out_channels": 256, "shortcut": True},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n4",
                    "type": "Detect",
                    "position": {"x": 0, "y": 300},
                    "data": {
                        "moduleType": "Detect",
                        "params": {"nc": 80},
                        "section": "head",
                    },
                },
            ],
            edges=[
                {"source": "n1", "target": "n4"},
                {"source": "n2", "target": "n4"},
                {"source": "n3", "target": "n4"},
            ],
            nc=80,
        )
        yaml_str = architecture_to_yaml(arch, resolver=_builtin_resolver)
        model = _yaml_to_model(yaml_str, tmp_path)

        dummy = torch.randn(1, 3, 640, 640)
        out = model.model(dummy)
        assert isinstance(out, list)
        assert all(isinstance(t, torch.Tensor) for t in out)


class TestLoadWithRepeats:
    """repeats > 1 时 yaml 正确生成第二列，加载后 forward 正常。"""

    def test_load_with_repeats(self, tmp_path: Path):
        arch = _make_arch(
            nodes=[
                {
                    "id": "n1",
                    "type": "Conv",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 64, "kernel_size": 3, "stride": 2},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n2",
                    "type": "C2f",
                    "position": {"x": 0, "y": 100},
                    "data": {
                        "moduleType": "C2f",
                        "params": {"out_channels": 128, "shortcut": True},
                        "repeats": 3,
                        "section": "backbone",
                    },
                },
                {
                    "id": "n3",
                    "type": "Classify",
                    "position": {"x": 0, "y": 200},
                    "data": {
                        "moduleType": "Classify",
                        "params": {"c2": 80},
                        "section": "head",
                    },
                },
            ],
            edges=[
                {"source": "n1", "target": "n2"},
                {"source": "n2", "target": "n3"},
            ],
            nc=80,
        )
        yaml_str = architecture_to_yaml(arch, resolver=_builtin_resolver)
        assert "[-1, 3, C2f" in yaml_str

        model = _yaml_to_model(yaml_str, tmp_path)
        dummy = torch.randn(1, 3, 640, 640)
        out = model.model(dummy)
        assert isinstance(out, torch.Tensor)
        assert out.shape[0] == 1  # batch size


class TestLoadMultiInput:
    """含 Concat 节点（from 为列表）的架构能正常加载与 forward。"""

    def test_load_multi_input(self, tmp_path: Path):
        arch = _make_arch(
            nodes=[
                {
                    "id": "n1",
                    "type": "Conv",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 64, "kernel_size": 3, "stride": 2},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n2",
                    "type": "Conv",
                    "position": {"x": 0, "y": 100},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 64, "kernel_size": 3, "stride": 1},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n3",
                    "type": "Concat",
                    "position": {"x": 0, "y": 200},
                    "data": {
                        "moduleType": "Concat",
                        "params": {"dim": 1},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n4",
                    "type": "Classify",
                    "position": {"x": 0, "y": 300},
                    "data": {
                        "moduleType": "Classify",
                        "params": {"c2": 80},
                        "section": "head",
                    },
                },
            ],
            edges=[
                {"source": "n1", "target": "n3"},
                {"source": "n2", "target": "n3"},
                {"source": "n3", "target": "n4"},
            ],
            nc=80,
        )
        yaml_str = architecture_to_yaml(arch, resolver=_builtin_resolver)
        # Concat 的 from 应为列表
        assert "Concat" in yaml_str
        assert "[" in yaml_str.split("Concat")[0].split("]")[0] or "[[" in yaml_str

        model = _yaml_to_model(yaml_str, tmp_path)
        dummy = torch.randn(1, 3, 640, 640)
        out = model.model(dummy)
        assert isinstance(out, torch.Tensor)


class TestLoadCustomComposite:
    """custom composite 模块通过 generate_module_code + exec 注册后，可被 YOLO 加载。"""

    def test_load_custom_composite(self, tmp_path: Path):
        schema = {
            "type": "TestCustomBlock",
            "category": "custom",
            "display_name": "Test Custom Block",
            "is_composite": True,
            "params_schema": [],
            "proxy_inputs": [
                {"name": "x", "sub_node_id": "ident", "port_index": 0}
            ],
            "proxy_outputs": [
                {"name": "out", "sub_node_id": "ident", "port_index": 0}
            ],
            "sub_nodes": [
                {"id": "ident", "type": "Identity", "params": {}},
            ],
            "sub_edges": [],
        }
        code = generate_module_code(schema, expand_composites=False)

        # exec 注册到当前全局命名空间，再注入 ultralytics tasks
        exec_globals = {"torch": torch, "nn": torch.nn}
        exec(code, exec_globals)
        custom_cls = exec_globals["TestCustomBlock"]

        arch = _make_arch(
            nodes=[
                {
                    "id": "n1",
                    "type": "Conv",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 64, "kernel_size": 3, "stride": 2},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n2",
                    "type": "TestCustomBlock",
                    "position": {"x": 0, "y": 100},
                    "data": {
                        "moduleType": "TestCustomBlock",
                        "params": {},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n3",
                    "type": "Conv",
                    "position": {"x": 0, "y": 200},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 128, "kernel_size": 3, "stride": 2},
                        "section": "backbone",
                    },
                },
                {
                    "id": "n4",
                    "type": "Classify",
                    "position": {"x": 0, "y": 300},
                    "data": {
                        "moduleType": "Classify",
                        "params": {"c2": 80},
                        "section": "head",
                    },
                },
            ],
            edges=[
                {"source": "n1", "target": "n2"},
                {"source": "n2", "target": "n3"},
                {"source": "n3", "target": "n4"},
            ],
            nc=80,
        )
        yaml_str = architecture_to_yaml(arch, resolver=_builtin_resolver)
        assert "TestCustomBlock" in yaml_str

        model = _yaml_to_model(
            yaml_str,
            tmp_path,
            extra_module_globals={"TestCustomBlock": custom_cls},
        )
        dummy = torch.randn(1, 3, 640, 640)
        out = model.model(dummy)
        assert isinstance(out, torch.Tensor)
        assert out.shape == (1, 80)
