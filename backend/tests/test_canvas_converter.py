"""
画布 → schema 转换器单元测试
"""
import pytest

from app.ml.modules.canvas_converter import canvas_to_schema, CanvasConversionError


def _resolver(schemas: dict):
    """辅助函数：构造模块解析器"""
    return lambda module_type: schemas.get(module_type)


class TestCanvasToSchema:
    """最简转换场景"""

    def test_simple_conversion(self):
        resolver = _resolver({
            "Conv2d": {
                "input_ports": [{"name": "input"}],
                "output_ports": [{"name": "output"}],
            }
        })

        nodes = [
            {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
             "data": {"parameters": {"name": "x"}}},
            {"id": "conv1", "type": "module", "position": {"x": 100, "y": 100},
             "data": {"moduleType": "Conv2d", "parameters": {}}},
            {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 200},
             "data": {"parameters": {"name": "out"}}},
        ]
        edges = [
            {"id": "e1", "source": "ip1", "target": "conv1", "targetHandle": "input"},
            {"id": "e2", "source": "conv1", "target": "op1", "sourceHandle": "output"},
        ]

        result = canvas_to_schema(nodes, edges, module_resolver=resolver)

        assert result["is_composite"] is True
        assert len(result["proxy_inputs"]) == 1
        assert result["proxy_inputs"][0] == {"sub_node_id": "conv1", "port_index": 0, "name": "x"}
        assert len(result["proxy_outputs"]) == 1
        assert result["proxy_outputs"][0] == {"sub_node_id": "conv1", "port_index": 0, "name": "out"}
        assert len(result["sub_nodes"]) == 1
        assert result["sub_nodes"][0]["type"] == "Conv2d"
        assert len(result["sub_edges"]) == 0

    def test_multi_input(self):
        """多输入：3 InputPort + FocusFeature + 1 OutputPort"""
        resolver = _resolver({
            "FocusFeature": {
                "proxy_inputs": [{"name": "p5"}, {"name": "p4"}, {"name": "p3"}],
                "proxy_outputs": [{"name": "out"}],
            }
        })

        nodes = [
            {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
             "data": {"parameters": {"name": "p5"}}},
            {"id": "ip2", "type": "input_port", "position": {"x": 0, "y": 100},
             "data": {"parameters": {"name": "p4"}}},
            {"id": "ip3", "type": "input_port", "position": {"x": 0, "y": 200},
             "data": {"parameters": {"name": "p3"}}},
            {"id": "ff1", "type": "module", "position": {"x": 100, "y": 100},
             "data": {"moduleType": "FocusFeature", "parameters": {}}},
            {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 100},
             "data": {"parameters": {"name": "out"}}},
        ]
        edges = [
            {"id": "e1", "source": "ip1", "target": "ff1", "targetHandle": "p5"},
            {"id": "e2", "source": "ip2", "target": "ff1", "targetHandle": "p4"},
            {"id": "e3", "source": "ip3", "target": "ff1", "targetHandle": "p3"},
            {"id": "e4", "source": "ff1", "target": "op1", "sourceHandle": "out"},
        ]

        result = canvas_to_schema(nodes, edges, module_resolver=resolver)

        assert len(result["proxy_inputs"]) == 3
        assert result["proxy_inputs"][0]["port_index"] == 0
        assert result["proxy_inputs"][1]["port_index"] == 1
        assert result["proxy_inputs"][2]["port_index"] == 2

    def test_multi_output(self):
        """多输出：1 InputPort + Detect_SASD + 3 OutputPort"""
        resolver = _resolver({
            "Detect_SASD": {
                "proxy_inputs": [{"name": "in"}],
                "proxy_outputs": [{"name": "o3"}, {"name": "o4"}, {"name": "o5"}],
            }
        })

        nodes = [
            {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
             "data": {"parameters": {"name": "x"}}},
            {"id": "ds1", "type": "module", "position": {"x": 100, "y": 100},
             "data": {"moduleType": "Detect_SASD", "parameters": {}}},
            {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 0},
             "data": {"parameters": {"name": "o3"}}},
            {"id": "op2", "type": "output_port", "position": {"x": 200, "y": 100},
             "data": {"parameters": {"name": "o4"}}},
            {"id": "op3", "type": "output_port", "position": {"x": 200, "y": 200},
             "data": {"parameters": {"name": "o5"}}},
        ]
        edges = [
            {"id": "e1", "source": "ip1", "target": "ds1", "targetHandle": "in"},
            {"id": "e2", "source": "ds1", "target": "op1", "sourceHandle": "o3"},
            {"id": "e3", "source": "ds1", "target": "op2", "sourceHandle": "o4"},
            {"id": "e4", "source": "ds1", "target": "op3", "sourceHandle": "o5"},
        ]

        result = canvas_to_schema(nodes, edges, module_resolver=resolver)

        assert len(result["proxy_outputs"]) == 3
        assert result["proxy_outputs"][0]["port_index"] == 0
        assert result["proxy_outputs"][1]["port_index"] == 1
        assert result["proxy_outputs"][2]["port_index"] == 2

    def test_dynamic_port_fallback(self):
        """动态端口 fallback：Concat 的 in_0 / in_1"""
        resolver = _resolver({
            "Concat": {
                "input_ports": [],
                "output_ports": [{"name": "output"}],
            }
        })

        nodes = [
            {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
             "data": {"parameters": {"name": "a"}}},
            {"id": "ip2", "type": "input_port", "position": {"x": 0, "y": 100},
             "data": {"parameters": {"name": "b"}}},
            {"id": "cat1", "type": "module", "position": {"x": 100, "y": 50},
             "data": {"moduleType": "Concat", "parameters": {}}},
            {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 50},
             "data": {"parameters": {"name": "out"}}},
        ]
        edges = [
            {"id": "e1", "source": "ip1", "target": "cat1", "targetHandle": "in_0"},
            {"id": "e2", "source": "ip2", "target": "cat1", "targetHandle": "in_1"},
            {"id": "e3", "source": "cat1", "target": "op1", "sourceHandle": "output"},
        ]

        result = canvas_to_schema(nodes, edges, module_resolver=resolver)

        assert len(result["proxy_inputs"]) == 2
        assert result["proxy_inputs"][0]["port_index"] == 0
        assert result["proxy_inputs"][1]["port_index"] == 1

    def test_no_input_port_raises(self):
        """0 InputPort → raise"""
        with pytest.raises(CanvasConversionError, match="至少.*1 个 InputPort"):
            canvas_to_schema([], [], module_resolver=lambda x: None)

    def test_unknown_port_raises(self):
        """端口名在 schema 中不存在 → raise"""
        resolver = _resolver({
            "Conv2d": {
                "input_ports": [{"name": "input"}],
                "output_ports": [{"name": "output"}],
            }
        })

        nodes = [
            {"id": "ip1", "type": "input_port", "position": {"x": 0, "y": 0},
             "data": {"parameters": {"name": "x"}}},
            {"id": "conv1", "type": "module", "position": {"x": 100, "y": 100},
             "data": {"moduleType": "Conv2d", "parameters": {}}},
            {"id": "op1", "type": "output_port", "position": {"x": 200, "y": 200},
             "data": {"parameters": {"name": "out"}}},
        ]
        edges = [
            {"id": "e1", "source": "ip1", "target": "conv1", "targetHandle": "nonexistent"},
        ]

        with pytest.raises(CanvasConversionError, match="nonexistent"):
            canvas_to_schema(nodes, edges, module_resolver=resolver)
