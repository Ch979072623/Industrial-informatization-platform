"""
YAML 生成器单元测试

覆盖场景：
1. 单输入链
2. 多输入（Concat）
3. repeats > 1
4. 拓扑排序 + y 坐标打破平级
5. 有环图抛异常
6. 节点无 section 抛异常
7. nc 默认值
8. custom composite 触发 codegen
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from app.ml.runtime.yaml_generator import (
    architecture_to_yaml,
    collect_custom_modules,
    YamlGeneratorError,
    _topological_sort,
    _derive_from,
    _build_incoming,
)


class TestTopologicalSort:
    """拓扑排序子测试"""

    def test_linear_chain(self):
        nodes = [
            {"id": "a", "position": {"x": 0, "y": 0}},
            {"id": "b", "position": {"x": 0, "y": 100}},
            {"id": "c", "position": {"x": 0, "y": 200}},
        ]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "c"},
        ]
        order = _topological_sort(nodes, edges)
        assert order == ["a", "b", "c"]

    def test_y_tiebreak(self):
        """同层两节点 y 值不同，y 小的排前面"""
        nodes = [
            {"id": "a", "position": {"x": 0, "y": 0}},
            {"id": "b", "position": {"x": 0, "y": 150}},
            {"id": "c", "position": {"x": 0, "y": 50}},
        ]
        edges = []
        order = _topological_sort(nodes, edges)
        # a 的 y=0 最小，c 的 y=50 次之，b 的 y=150 最大
        assert order == ["a", "c", "b"]

    def test_cycle_raises(self):
        nodes = [
            {"id": "a", "position": {"x": 0, "y": 0}},
            {"id": "b", "position": {"x": 0, "y": 100}},
        ]
        edges = [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},
        ]
        with pytest.raises(YamlGeneratorError, match="环"):
            _topological_sort(nodes, edges)


class TestDeriveFrom:
    """from 字段推导子测试"""

    def test_single_predecessor_adjacent(self):
        topo = ["a", "b", "c"]
        incoming = {"b": ["a"], "c": ["b"]}
        assert _derive_from("b", topo, incoming) == -1
        assert _derive_from("c", topo, incoming) == -1

    def test_single_predecessor_non_adjacent(self):
        topo = ["a", "b", "c"]
        incoming = {"c": ["a"]}
        assert _derive_from("c", topo, incoming) == 0

    def test_multi_input(self):
        topo = ["a", "b", "c"]
        incoming = {"c": ["a", "b"]}
        assert _derive_from("c", topo, incoming) == [0, 1]

    def test_no_predecessor(self):
        topo = ["a"]
        incoming = {}
        assert _derive_from("a", topo, incoming) == -1


class TestArchitectureToYaml:
    """architecture_to_yaml 主测试"""

    def test_single_chain(self):
        """A→B→C 线性链，from 全是 -1"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Conv",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 64, "kernel_size": 3},
                        "repeats": 1,
                        "section": "backbone",
                    },
                },
                {
                    "id": "n2",
                    "type": "C2f",
                    "position": {"x": 0, "y": 100},
                    "data": {
                        "moduleType": "C2f",
                        "params": {"out_channels": 128},
                        "repeats": 1,
                        "section": "backbone",
                    },
                },
                {
                    "id": "n3",
                    "type": "Conv",
                    "position": {"x": 0, "y": 200},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 256},
                        "repeats": 1,
                        "section": "head",
                    },
                },
            ],
            "edges": [
                {"source": "n1", "target": "n2"},
                {"source": "n2", "target": "n3"},
            ],
        }
        yaml_str = architecture_to_yaml(arch)
        lines = yaml_str.splitlines()
        # 找到 backbone 和 head 中的行
        backbone_lines = [l for l in lines if l.strip().startswith("-") and "backbone" not in l and "head" not in l]
        # n1 和 n2 在 backbone
        assert any("Conv" in l and "[-1, 1, Conv" in l for l in lines)
        assert any("C2f" in l and "[-1, 1, C2f" in l for l in lines)
        # n3 在 head
        assert any("Conv" in l and "head:" in yaml_str[:yaml_str.index(l)] for l in lines if "Conv" in l)

    def test_multi_input(self):
        """Concat 节点有两条入边，from 是 [idx1, idx2]"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Conv",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 64},
                        "repeats": 1,
                        "section": "backbone",
                    },
                },
                {
                    "id": "n2",
                    "type": "Conv",
                    "position": {"x": 0, "y": 100},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"out_channels": 128},
                        "repeats": 1,
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
                        "repeats": 1,
                        "section": "backbone",
                    },
                },
            ],
            "edges": [
                {"source": "n1", "target": "n3"},
                {"source": "n2", "target": "n3"},
            ],
        }
        yaml_str = architecture_to_yaml(arch)
        assert "[[0, 1], 1, Concat" in yaml_str or "[[1, 0], 1, Concat" in yaml_str

    def test_repeats(self):
        """节点 repeats=3，yaml 里该行第二列是 3"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "C2f",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "C2f",
                        "params": {"out_channels": 256},
                        "repeats": 3,
                        "section": "backbone",
                    },
                },
            ],
            "edges": [],
        }
        yaml_str = architecture_to_yaml(arch)
        assert "[-1, 3, C2f" in yaml_str

    def test_no_section_raises(self):
        """节点无分区信息 → 抛出 YamlGeneratorError"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Conv",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Conv",
                        "params": {},
                    },
                },
            ],
            "edges": [],
        }
        with pytest.raises(YamlGeneratorError, match="section"):
            architecture_to_yaml(arch)

    def test_nc_default(self):
        """没有 nc 字段时默认 80"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Detect",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Detect",
                        "params": {},
                        "repeats": 1,
                        "section": "head",
                    },
                },
            ],
            "edges": [],
        }
        yaml_str = architecture_to_yaml(arch)
        assert yaml_str.startswith("nc: 80")

    def test_nc_from_metadata(self):
        """metadata 中有 num_classes"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Detect",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Detect",
                        "params": {},
                        "repeats": 1,
                        "section": "head",
                    },
                },
            ],
            "edges": [],
            "metadata": {"num_classes": 10},
        }
        yaml_str = architecture_to_yaml(arch)
        assert yaml_str.startswith("nc: 10")

    def test_nc_from_top_level(self):
        """architecture_json 顶层有 num_classes"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Detect",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Detect",
                        "params": {},
                        "repeats": 1,
                        "section": "head",
                    },
                },
            ],
            "edges": [],
            "num_classes": 20,
        }
        yaml_str = architecture_to_yaml(arch)
        assert yaml_str.startswith("nc: 20")

    def test_empty_nodes_raises(self):
        """空节点列表抛异常"""
        with pytest.raises(YamlGeneratorError, match="没有任何节点"):
            architecture_to_yaml({"nodes": [], "edges": []})

    def test_resolver_params_schema(self):
        """resolver 返回 params_schema，args 按顺序排列"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Conv",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Conv",
                        "params": {"kernel_size": 3, "out_channels": 64},
                        "repeats": 1,
                        "section": "backbone",
                    },
                },
            ],
            "edges": [],
        }

        def resolver(module_type: str) -> Optional[Dict[str, Any]]:
            return {
                "params_schema": [
                    {"name": "out_channels", "type": "int"},
                    {"name": "kernel_size", "type": "int"},
                ]
            }

        yaml_str = architecture_to_yaml(arch, resolver=resolver)
        assert "[64, 3]" in yaml_str


class TestCollectCustomModules:
    """custom composite 触发代码生成测试"""

    def test_custom_composite_triggers_codegen(self, tmp_path: Path):
        """mock db_resolver 返回 custom composite schema，确认 collect_custom_modules 返回结果含 path"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "MyBlock",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "MyBlock",
                        "params": {},
                        "repeats": 1,
                        "section": "backbone",
                    },
                },
            ],
            "edges": [],
        }

        def db_resolver(module_type: str) -> Optional[Dict[str, Any]]:
            if module_type == "MyBlock":
                return {
                    "type": "MyBlock",
                    "source": "custom",
                    "is_composite": True,
                    "schema_json": {
                        "type": "MyBlock",
                        "category": "custom",
                        "display_name": "My Block",
                        "is_composite": True,
                        "params_schema": [],
                        "proxy_inputs": [],
                        "proxy_outputs": [],
                        "sub_nodes": [],
                        "sub_edges": [],
                    },
                }
            return None

        output_dir = tmp_path / "extra_modules"
        output_dir.mkdir()

        with patch("app.ml.runtime.yaml_generator.generate_module_code") as mock_gen, \
             patch("app.ml.runtime.yaml_generator.write_module_file") as mock_write:
            mock_gen.return_value = "class MyBlock:\n    pass\n"
            mock_write.return_value = output_dir / "MyBlock.py"

            results = collect_custom_modules(arch, db_resolver, output_dir)

        assert len(results) == 1
        assert results[0]["type"] == "MyBlock"
        assert results[0]["path"] is not None
        assert results[0]["error"] is None
        mock_gen.assert_called_once()
        mock_write.assert_called_once()

    def test_builtin_module_ignored(self, tmp_path: Path):
        """builtin 模块不应触发 codegen"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "Conv",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "Conv",
                        "params": {},
                        "repeats": 1,
                        "section": "backbone",
                    },
                },
            ],
            "edges": [],
        }

        def db_resolver(module_type: str) -> Optional[Dict[str, Any]]:
            return {
                "type": "Conv",
                "source": "builtin",
                "is_composite": False,
                "schema_json": {},
            }

        output_dir = tmp_path / "extra_modules"
        output_dir.mkdir()

        with patch("app.ml.runtime.yaml_generator.generate_module_code") as mock_gen, \
             patch("app.ml.runtime.yaml_generator.write_module_file") as mock_write:
            results = collect_custom_modules(arch, db_resolver, output_dir)

        assert len(results) == 0
        mock_gen.assert_not_called()
        mock_write.assert_not_called()

    def test_custom_atomic_ignored(self, tmp_path: Path):
        """custom 但非 composite 的模块不应触发 codegen"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "MyLayer",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "MyLayer",
                        "params": {},
                        "repeats": 1,
                        "section": "backbone",
                    },
                },
            ],
            "edges": [],
        }

        def db_resolver(module_type: str) -> Optional[Dict[str, Any]]:
            return {
                "type": "MyLayer",
                "source": "custom",
                "is_composite": False,
                "schema_json": {},
            }

        output_dir = tmp_path / "extra_modules"
        output_dir.mkdir()

        with patch("app.ml.runtime.yaml_generator.generate_module_code") as mock_gen, \
             patch("app.ml.runtime.yaml_generator.write_module_file") as mock_write:
            results = collect_custom_modules(arch, db_resolver, output_dir)

        assert len(results) == 0
        mock_gen.assert_not_called()
        mock_write.assert_not_called()

    def test_codegen_failure_recorded(self, tmp_path: Path):
        """codegen 失败不中断，记录 error"""
        arch = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "BadBlock",
                    "position": {"x": 0, "y": 0},
                    "data": {
                        "moduleType": "BadBlock",
                        "params": {},
                        "repeats": 1,
                        "section": "backbone",
                    },
                },
            ],
            "edges": [],
        }

        def db_resolver(module_type: str) -> Optional[Dict[str, Any]]:
            return {
                "type": "BadBlock",
                "source": "custom",
                "is_composite": True,
                "schema_json": {"sub_nodes": [], "sub_edges": []},
            }

        output_dir = tmp_path / "extra_modules"
        output_dir.mkdir()

        with patch("app.ml.runtime.yaml_generator.generate_module_code") as mock_gen:
            mock_gen.side_effect = RuntimeError("bad schema")
            results = collect_custom_modules(arch, db_resolver, output_dir)

        assert len(results) == 1
        assert results[0]["type"] == "BadBlock"
        assert results[0]["path"] is None
        assert "bad schema" in results[0]["error"]
