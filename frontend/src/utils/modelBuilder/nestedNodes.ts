import type { RFNode } from '@/types/mlModule';

export interface NestedNode {
  node: RFNode;
  children: NestedNode[];
}

export interface NestedResult {
  tree: NestedNode[];
  orphans: RFNode[];
}

/**
 * 把扁平节点数组（含 parentId 字段的子节点与无 parentId 的顶层节点混排）转换为嵌套树。
 * 顶层节点进 tree 根数组，子节点挂在其父节点的 children 数组里。
 * 找不到父节点的"孤儿"节点单独放入 orphans，不进 tree（显式暴露以便上层处理）。
 */
export function nestNodes(nodes: RFNode[]): NestedResult {
  const nodeMap = new Map<string, NestedNode>();
  const tree: NestedNode[] = [];
  const orphans: RFNode[] = [];

  // 第一轮：为每个节点创建 NestedNode 包装
  for (const node of nodes) {
    nodeMap.set(node.id, { node, children: [] });
  }

  // 第二轮：建立父子关系
  for (const node of nodes) {
    const nested = nodeMap.get(node.id);
    if (!nested) continue;

    const parentId = (node as unknown as { parentId?: string }).parentId;
    if (parentId) {
      const parent = nodeMap.get(parentId);
      if (parent) {
        parent.children.push(nested);
      } else {
        orphans.push(node);
      }
    } else {
      tree.push(nested);
    }
  }

  return { tree, orphans };
}

/**
 * nestNodes 的反向操作。接受 NestedResult（或仅 tree，orphans 可选）,
 * 返回扁平数组。对称性：nestNodes(flattenNodes(r)) 与 r 等价（节点 id 集合相同）。
 */
export function flattenNodes(
  result: NestedResult | { tree: NestedNode[]; orphans?: RFNode[] }
): RFNode[] {
  const flat: RFNode[] = [];

  function traverse(nodes: NestedNode[]) {
    for (const { node, children } of nodes) {
      flat.push(node);
      traverse(children);
    }
  }

  traverse(result.tree);

  if ('orphans' in result && result.orphans) {
    flat.push(...result.orphans);
  }

  return flat;
}
