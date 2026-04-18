"""
模块定义基础类型与抽象

定义模块 schema 的 Python 表达，供 registry 和动态构图使用。
"""
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field


@dataclass
class ParamSchemaItem:
    """参数 schema 单项"""
    name: str
    type: str  # "int", "float", "bool", "string", "int[]", "float[]"
    default: Any = None
    description: str = ""
    min: Optional[Union[int, float]] = None
    max: Optional[Union[int, float]] = None


@dataclass
class ProxyPort:
    """代理端口定义（复合模块折叠态的入口/出口）"""
    sub_node_id: str
    port_index: int
    name: str


@dataclass
class SubNode:
    """复合模块内部子节点"""
    id: str
    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    position: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0})


@dataclass
class SubEdge:
    """复合模块内部子边"""
    source: str
    source_port: int
    target: str
    target_port: int


@dataclass
class CompositeModuleSpec:
    """
    复合模块规范（schema.json 的 Python 表达）
    """
    type: str
    category: str
    display_name: str
    is_composite: bool = True
    params_schema: List[ParamSchemaItem] = field(default_factory=list)
    proxy_inputs: List[ProxyPort] = field(default_factory=list)
    proxy_outputs: List[ProxyPort] = field(default_factory=list)
    sub_nodes: List[SubNode] = field(default_factory=list)
    sub_edges: List[SubEdge] = field(default_factory=list)

    @classmethod
    def from_schema(cls, schema: Dict[str, Any]) -> "CompositeModuleSpec":
        """从 schema dict 解析"""
        return cls(
            type=schema["type"],
            category=schema["category"],
            display_name=schema.get("display_name", schema["type"]),
            is_composite=schema.get("is_composite", True),
            params_schema=[
                ParamSchemaItem(
                    name=p["name"],
                    type=p["type"],
                    default=p.get("default"),
                    description=p.get("description", ""),
                    min=p.get("min"),
                    max=p.get("max"),
                )
                for p in schema.get("params_schema", [])
            ],
            proxy_inputs=[
                ProxyPort(
                    sub_node_id=p["sub_node_id"],
                    port_index=p["port_index"],
                    name=p["name"],
                )
                for p in schema.get("proxy_inputs", [])
            ],
            proxy_outputs=[
                ProxyPort(
                    sub_node_id=p["sub_node_id"],
                    port_index=p["port_index"],
                    name=p["name"],
                )
                for p in schema.get("proxy_outputs", [])
            ],
            sub_nodes=[
                SubNode(
                    id=n["id"],
                    type=n["type"],
                    params=n.get("params", {}),
                    position=n.get("position", {"x": 0, "y": 0}),
                )
                for n in schema.get("sub_nodes", [])
            ],
            sub_edges=[
                SubEdge(
                    source=e["source"],
                    source_port=e["source_port"],
                    target=e["target"],
                    target_port=e["target_port"],
                )
                for e in schema.get("sub_edges", [])
            ],
        )
