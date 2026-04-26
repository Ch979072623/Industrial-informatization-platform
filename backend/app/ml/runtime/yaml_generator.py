"""
Architecture JSON → ultralytics 兼容 YAML 生成器

纯函数实现，不读文件、不写文件、不访问数据库。
"""
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from app.ml.runtime.codegen import generate_module_code, write_module_file


class YamlGeneratorError(Exception):
    """YAML 生成过程中的异常"""
    pass


def _topological_sort(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
    """
    对节点进行拓扑排序；入度相同时按 y 坐标升序打破平级。

    返回节点 id 的有序列表。
    """
    node_map = {n["id"]: n for n in nodes}
    adj: Dict[str, List[str]] = {n["id"]: [] for n in nodes}
    in_degree: Dict[str, int] = {n["id"]: 0 for n in nodes}

    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src in adj and tgt in adj:
            adj[src].append(tgt)
            in_degree[tgt] += 1

    # Kahn 算法，队列按 (in_degree, y) 排序，这里用列表每次取最小
    queue: List[str] = [nid for nid, deg in in_degree.items() if deg == 0]

    def _sort_key(nid: str) -> tuple:
        pos = node_map[nid].get("position", {})
        y = pos.get("y", 0) if isinstance(pos, dict) else 0
        return (in_degree[nid], y)

    queue.sort(key=_sort_key)
    result: List[str] = []

    while queue:
        # 取出当前 in_degree 最小且 y 最小的节点
        queue.sort(key=_sort_key)
        nid = queue.pop(0)
        result.append(nid)

        for neighbor in adj[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(nodes):
        raise YamlGeneratorError("图中存在环，无法进行拓扑排序")

    return result


def _derive_from(
    node_id: str,
    topo_order: List[str],
    incoming: Dict[str, List[str]],
) -> Any:
    """
    推导 YAML 中的 `from` 字段。

    - 无入边 → -1
    - 单一入边且来自拓扑序中紧邻的前一个节点 → -1
    - 单一入边且来自非紧邻节点 → 该节点层序号
    - 多条入边 → 按层序号排序的列表
    """
    preds = incoming.get(node_id, [])
    idx_map = {nid: i for i, nid in enumerate(topo_order)}
    current_idx = idx_map[node_id]

    if not preds:
        return -1

    # 过滤掉不在 topo_order 中的前驱（理论上不应发生）
    valid_preds = [p for p in preds if p in idx_map]
    if not valid_preds:
        return -1

    if len(valid_preds) == 1:
        pred = valid_preds[0]
        pred_idx = idx_map[pred]
        # 如果前驱是紧邻的前一个节点，用 -1
        if pred_idx == current_idx - 1:
            return -1
        return pred_idx

    # 多条入边，按层序号排序
    pred_idxs = sorted(idx_map[p] for p in valid_preds)
    return pred_idxs


def _build_incoming(edges: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """构建每个节点的入边来源映射"""
    incoming: Dict[str, List[str]] = {}
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src and tgt:
            incoming.setdefault(tgt, []).append(src)
    return incoming


def _extract_args(node_data: Dict[str, Any], params_schema: Optional[List[Dict[str, Any]]]) -> List[Any]:
    """
    将节点 data.params 转换为 args 列表。
    如果有 params_schema，按 schema 顺序提取；否则按字典序。
    """
    params = node_data.get("params") or node_data.get("parameters") or {}
    if not isinstance(params, dict):
        return []

    if params_schema:
        args: List[Any] = []
        for p in params_schema:
            name = p.get("name")
            if name is not None and name in params:
                args.append(params[name])
        return args

    # 无 schema 时按 key 排序
    return [v for _, v in sorted(params.items())]


def architecture_to_yaml(
    architecture_json: Dict[str, Any],
    resolver: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
) -> str:
    """
    将 architecture_json 转换为 ultralytics 兼容的 YAML 字符串。

    Parameters
    ----------
    architecture_json: dict
        包含 nodes, edges, metadata 等字段的架构描述。
    resolver: callable, optional
        用于解析模块类型到参数 schema 的函数，签名为 (module_type: str) -> Optional[dict]。

    Returns
    -------
    str
        生成的 YAML 字符串。

    Raises
    ------
    YamlGeneratorError
        拓扑排序检测到环、节点缺少 section 等。
    """
    nodes = architecture_json.get("nodes", [])
    edges = architecture_json.get("edges", [])
    metadata = architecture_json.get("metadata", {})

    if not nodes:
        raise YamlGeneratorError("架构中没有任何节点")

    # 1. 拓扑排序
    topo_order = _topological_sort(nodes, edges)
    idx_map = {nid: i for i, nid in enumerate(topo_order)}
    node_map = {n["id"]: n for n in nodes}
    incoming = _build_incoming(edges)

    # 2. 按 section 分组
    backbone_lines: List[str] = []
    head_lines: List[str] = []

    for nid in topo_order:
        node = node_map[nid]
        data = node.get("data", {})
        section = data.get("section")
        if section is None:
            raise YamlGeneratorError(
                f"节点 '{nid}' (type={node.get('type')}) 缺少 section 分区信息，"
                f"无法确定其属于 backbone 还是 head"
            )
        if section not in ("backbone", "head"):
            raise YamlGeneratorError(
                f"节点 '{nid}' 的 section 值 '{section}' 不合法，仅支持 'backbone' 或 'head'"
            )

        module_type = data.get("moduleType") or data.get("moduleName") or node.get("type", "Unknown")
        repeats = data.get("repeats", 1)
        if not isinstance(repeats, int) or repeats < 1:
            repeats = 1

        # 解析参数 schema 并生成 args
        params_schema = None
        if resolver:
            module_info = resolver(module_type)
            if module_info and isinstance(module_info.get("params_schema"), list):
                params_schema = module_info["params_schema"]
            elif module_info and isinstance(module_info.get("schema_json", {}).get("params_schema"), list):
                params_schema = module_info["schema_json"]["params_schema"]

        args = _extract_args(data, params_schema)

        from_val = _derive_from(nid, topo_order, incoming)
        line = f"  - [{from_val}, {repeats}, {module_type}, {args}]"

        if section == "backbone":
            backbone_lines.append(line)
        else:
            head_lines.append(line)

    # 3. 组装 YAML
    nc = metadata.get("num_classes") if isinstance(metadata, dict) else None
    if nc is None:
        nc = architecture_json.get("num_classes", 80)
    if not isinstance(nc, int):
        nc = 80

    yaml_lines = [
        f"nc: {nc}",
        "scales:",
        "  n: [0.33, 0.25, 1024]",
        "",
        "backbone:",
    ]
    yaml_lines.extend(backbone_lines)
    yaml_lines.append("")
    yaml_lines.append("head:")
    yaml_lines.extend(head_lines)

    return "\n".join(yaml_lines)


def collect_custom_modules(
    architecture_json: Dict[str, Any],
    db_resolver: Callable[[str], Optional[Dict[str, Any]]],
    output_dir: Path,
) -> List[Dict[str, Any]]:
    """
    扫描 architecture_json 中的 custom composite 节点，触发代码生成。

    Parameters
    ----------
    architecture_json: dict
        架构 JSON。
    db_resolver: callable
        (module_type: str) -> Optional[dict]，返回模块定义字典。
    output_dir: Path
        .py 文件输出目录。

    Returns
    -------
    list[dict]
        每个元素的字段：type, path（成功时）, error（失败时）。
    """
    nodes = architecture_json.get("nodes", [])
    results: List[Dict[str, Any]] = []

    for node in nodes:
        data = node.get("data", {})
        module_type = data.get("moduleType") or data.get("moduleName") or node.get("type", "")
        if not module_type:
            continue

        module_info = db_resolver(module_type)
        if not module_info:
            continue

        source = module_info.get("source", "")
        is_composite = module_info.get("is_composite", False)

        if source == "custom" and is_composite:
            schema_json = module_info.get("schema_json")
            if not schema_json:
                results.append({
                    "type": module_type,
                    "path": None,
                    "error": f"模块 '{module_type}' 缺少 schema_json",
                })
                continue

            try:
                code = generate_module_code(schema_json, expand_composites=True, _resolver=db_resolver)
                output_path = write_module_file(schema_json, expand_composites=True, output_dir=output_dir, resolver=db_resolver)
                results.append({
                    "type": module_type,
                    "path": str(output_path),
                    "error": None,
                })
            except Exception as exc:
                results.append({
                    "type": module_type,
                    "path": None,
                    "error": str(exc),
                })

    return results
