"""
画布数据 → schema_json 转换器

把 Module 画布（nodes + edges）转换为 ModuleDefinition.schema_json 格式。
"""
import re
from typing import List, Dict, Any, Optional, Callable


class CanvasConversionError(ValueError):
    """画布转换错误"""
    pass


def _resolve_port_index(
    schema: Optional[Dict[str, Any]],
    handle_name: Optional[str],
    direction: str,
) -> int:
    """
    根据 handle 名称解析端口索引。

    Args:
        schema: 模块的 schema_json（可为 None）
        handle_name: 端口 handle 字符串（如 "input", "output", "in_0"）
        direction: "input" 或 "output"

    Returns:
        端口整数索引

    Raises:
        CanvasConversionError: 无法解析时抛出
    """
    if handle_name is None or handle_name == "":
        return 0

    if schema:
        if direction == "input":
            ports = schema.get("input_ports", []) or schema.get("proxy_inputs", [])
        else:
            ports = schema.get("output_ports", []) or schema.get("proxy_outputs", [])

        for idx, port in enumerate(ports):
            if port.get("name") == handle_name:
                return idx

    # 动态端口 fallback
    m = re.match(r"^in_(\d+)$", handle_name)
    if m:
        return int(m.group(1))
    m = re.match(r"^out_(\d+)$", handle_name)
    if m:
        return int(m.group(1))

    raise CanvasConversionError(f"端口 {handle_name} 在 schema 中找不到")


def canvas_to_schema(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    *,
    module_resolver: Callable[[str], Optional[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    把 Module 画布数据转换为 ModuleDefinition.schema_json 格式。

    Args:
        nodes: 画布节点列表，每项含 {id, type, data, ...}
        edges: 画布边列表，每项含 {id, source, sourceHandle, target, targetHandle}
        module_resolver: 函数 (module_type: str) -> schema_json | None，
            用于查询画布子节点对应模块的 proxy_inputs/outputs 列表，
            以便把 sourceHandle 字符串映射为 source_port 整数

    Returns:
        符合 schema.json 格式的 dict，含 is_composite / sub_nodes / sub_edges
        / proxy_inputs / proxy_outputs 等字段

    Raises:
        CanvasConversionError: InputPort/OutputPort 缺失、端口映射失败等
    """
    input_ports = [n for n in nodes if n.get("type") == "input_port"]
    output_ports = [n for n in nodes if n.get("type") == "output_port"]
    sub_nodes_candidates = [n for n in nodes if n.get("type") not in ("input_port", "output_port")]

    if not input_ports:
        raise CanvasConversionError("Module 必须至少有 1 个 InputPort 和 1 个 OutputPort")
    if not output_ports:
        raise CanvasConversionError("Module 必须至少有 1 个 InputPort 和 1 个 OutputPort")

    # ---- proxy_inputs ----
    proxy_inputs: List[Dict[str, Any]] = []
    for ip in input_ports:
        ip_id = ip["id"]
        downstream_edges = [e for e in edges if e.get("source") == ip_id]
        for edge in downstream_edges:
            target_id = edge["target"]
            target_handle = edge.get("targetHandle")

            target_node = next((n for n in sub_nodes_candidates if n["id"] == target_id), None)
            if target_node is None:
                raise CanvasConversionError(f"InputPort {ip_id} 的下游节点 {target_id} 不存在")

            module_type = target_node.get("data", {}).get("moduleType") or target_node.get("data", {}).get("moduleName")
            schema = module_resolver(module_type) if module_type else None
            port_index = _resolve_port_index(schema, target_handle, "input")

            name = ip.get("data", {}).get("parameters", {}).get("name", "input")
            proxy_inputs.append({
                "sub_node_id": target_id,
                "port_index": port_index,
                "name": name,
            })

    # ---- proxy_outputs ----
    proxy_outputs: List[Dict[str, Any]] = []
    for op in output_ports:
        op_id = op["id"]
        upstream_edges = [e for e in edges if e.get("target") == op_id]
        for edge in upstream_edges:
            source_id = edge["source"]
            source_handle = edge.get("sourceHandle")

            source_node = next((n for n in sub_nodes_candidates if n["id"] == source_id), None)
            if source_node is None:
                raise CanvasConversionError(f"OutputPort {op_id} 的上游节点 {source_id} 不存在")

            module_type = source_node.get("data", {}).get("moduleType") or source_node.get("data", {}).get("moduleName")
            schema = module_resolver(module_type) if module_type else None
            port_index = _resolve_port_index(schema, source_handle, "output")

            name = op.get("data", {}).get("parameters", {}).get("name", "output")
            proxy_outputs.append({
                "sub_node_id": source_id,
                "port_index": port_index,
                "name": name,
            })

    # ---- sub_nodes ----
    sub_nodes: List[Dict[str, Any]] = []
    for node in sub_nodes_candidates:
        sub_nodes.append({
            "id": node["id"],
            "type": node.get("data", {}).get("moduleType") or node.get("data", {}).get("moduleName", "Unknown"),
            "params": node.get("data", {}).get("parameters", {}),
            "position": node.get("position", {"x": 0, "y": 0}),
        })

    # ---- sub_edges ----
    port_node_ids = {n["id"] for n in input_ports + output_ports}
    sub_edges: List[Dict[str, Any]] = []
    for edge in edges:
        if edge.get("source") in port_node_ids or edge.get("target") in port_node_ids:
            continue

        source_id = edge["source"]
        target_id = edge["target"]
        source_handle = edge.get("sourceHandle")
        target_handle = edge.get("targetHandle")

        source_node = next((n for n in sub_nodes_candidates if n["id"] == source_id), None)
        target_node = next((n for n in sub_nodes_candidates if n["id"] == target_id), None)

        if source_node is None or target_node is None:
            continue

        source_module_type = source_node.get("data", {}).get("moduleType") or source_node.get("data", {}).get("moduleName")
        target_module_type = target_node.get("data", {}).get("moduleType") or target_node.get("data", {}).get("moduleName")

        source_schema = module_resolver(source_module_type) if source_module_type else None
        target_schema = module_resolver(target_module_type) if target_module_type else None

        source_port = _resolve_port_index(source_schema, source_handle, "output")
        target_port = _resolve_port_index(target_schema, target_handle, "input")

        sub_edges.append({
            "source": source_id,
            "source_port": source_port,
            "target": target_id,
            "target_port": target_port,
        })

    return {
        "is_composite": True,
        "sub_nodes": sub_nodes,
        "sub_edges": sub_edges,
        "proxy_inputs": proxy_inputs,
        "proxy_outputs": proxy_outputs,
    }
