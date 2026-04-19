import { describe, it, expect } from 'vitest';
import { nestNodes, flattenNodes } from './nestedNodes';
import type { RFNode } from '@/types/mlModule';

function makeNode(id: string, parentId?: string): RFNode {
  return {
    id,
    position: { x: 0, y: 0 },
    type: 'module',
    data: {},
    ...(parentId ? { parentId } : {}),
  } as unknown as RFNode;
}

describe('nestNodes', () => {
  it('空数组返回空树和空孤儿', () => {
    const result = nestNodes([]);
    expect(result.tree).toEqual([]);
    expect(result.orphans).toEqual([]);
  });

  it('单个顶层节点、无子节点', () => {
    const nodes = [makeNode('a')];
    const result = nestNodes(nodes);
    expect(result.tree).toHaveLength(1);
    expect(result.tree[0].node.id).toBe('a');
    expect(result.tree[0].children).toEqual([]);
    expect(result.orphans).toEqual([]);
  });

  it('一个顶层节点带两个子节点', () => {
    const nodes = [makeNode('parent'), makeNode('child1', 'parent'), makeNode('child2', 'parent')];
    const result = nestNodes(nodes);
    expect(result.tree).toHaveLength(1);
    expect(result.tree[0].children).toHaveLength(2);
    expect(result.tree[0].children.map((c) => c.node.id)).toEqual(['child1', 'child2']);
    expect(result.orphans).toEqual([]);
  });

  it('两个顶层节点，各带一个子节点', () => {
    const nodes = [
      makeNode('p1'),
      makeNode('p2'),
      makeNode('c1', 'p1'),
      makeNode('c2', 'p2'),
    ];
    const result = nestNodes(nodes);
    expect(result.tree).toHaveLength(2);
    expect(result.tree[0].children.map((c) => c.node.id)).toEqual(['c1']);
    expect(result.tree[1].children.map((c) => c.node.id)).toEqual(['c2']);
    expect(result.orphans).toEqual([]);
  });

  it('嵌套 3 层（祖父-父-孙）', () => {
    const nodes = [makeNode('g'), makeNode('p', 'g'), makeNode('c', 'p')];
    const result = nestNodes(nodes);
    expect(result.tree).toHaveLength(1);
    expect(result.tree[0].node.id).toBe('g');
    expect(result.tree[0].children[0].node.id).toBe('p');
    expect(result.tree[0].children[0].children[0].node.id).toBe('c');
    expect(result.orphans).toEqual([]);
  });

  it('孤儿节点（parentId 指向不存在的节点）进 orphans，不进 tree', () => {
    const nodes = [makeNode('a', 'missing')];
    const result = nestNodes(nodes);
    expect(result.tree).toEqual([]);
    expect(result.orphans).toHaveLength(1);
    expect(result.orphans[0].id).toBe('a');
  });

  it('nestNodes 不 mutate 输入数组', () => {
    const nodes = [makeNode('a'), makeNode('b', 'a')];
    const before = JSON.stringify(nodes);
    nestNodes(nodes);
    const after = JSON.stringify(nodes);
    expect(after).toBe(before);
  });
});

describe('flattenNodes', () => {
  it('flattenNodes(nestNodes(input)) 的节点 id 集合与 input 相等', () => {
    const nodes = [
      makeNode('p1'),
      makeNode('p2'),
      makeNode('c1', 'p1'),
      makeNode('c2', 'p2'),
      makeNode('orphan', 'missing'),
    ];
    const nested = nestNodes(nodes);
    const flat = flattenNodes(nested);
    const idsBefore = new Set(nodes.map((n) => n.id));
    const idsAfter = new Set(flat.map((n) => n.id));
    expect(idsAfter).toEqual(idsBefore);
  });

  it('flattenNodes 对仅含 tree 的对象也能正常工作', () => {
    const nodes = [makeNode('a'), makeNode('b', 'a')];
    const nested = nestNodes(nodes);
    const flat = flattenNodes({ tree: nested.tree });
    expect(flat.map((n) => n.id)).toContain('a');
    expect(flat.map((n) => n.id)).toContain('b');
  });
});
