import { describe, it, expect, beforeEach } from 'vitest';
import { useModelBuilderStore } from './modelBuilderStore';
import type { RFNode } from '@/types/mlModule';

function makeNode(
  id: string,
  isComposite?: boolean,
  collapsed?: boolean,
  subLoaded?: boolean
): RFNode {
  return {
    id,
    position: { x: 0, y: 0 },
    type: 'module',
    data: {
      moduleType: 'test',
      moduleName: 'Test',
      displayName: 'Test',
      parameters: {},
      inputPorts: [],
      outputPorts: [],
      ...(isComposite !== undefined ? { isComposite } : {}),
      ...(collapsed !== undefined ? { collapsed } : {}),
      ...(subLoaded !== undefined ? { subLoaded } : {}),
    },
  } as unknown as RFNode;
}

describe('modelBuilderStore actions', () => {
  beforeEach(() => {
    localStorage.clear();
    useModelBuilderStore.setState({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      history: [],
      historyIndex: -1,
    });
  });

  it('toggleCollapse 对 composite 节点正确翻转 collapsed', () => {
    const store = useModelBuilderStore.getState();
    store.setNodes([makeNode('n1', true)]);

    store.toggleCollapse('n1');
    let node = useModelBuilderStore.getState().nodes.find((n) => n.id === 'n1');
    expect(node?.data.collapsed).toBe(false);

    store.toggleCollapse('n1');
    node = useModelBuilderStore.getState().nodes.find((n) => n.id === 'n1');
    expect(node?.data.collapsed).toBe(true);
  });

  it('toggleCollapse 对 atomic 节点静默忽略', () => {
    const store = useModelBuilderStore.getState();
    store.setNodes([makeNode('n1', false)]);

    store.toggleCollapse('n1');
    const node = useModelBuilderStore.getState().nodes.find((n) => n.id === 'n1');
    expect(node?.data.collapsed).toBeUndefined();
  });

  it('toggleCollapse 对不存在的 nodeId 静默忽略', () => {
    const store = useModelBuilderStore.getState();
    store.setNodes([makeNode('n1', true)]);

    const before = useModelBuilderStore.getState().nodes;
    store.toggleCollapse('missing');
    const after = useModelBuilderStore.getState().nodes;
    expect(after).toEqual(before);
  });

  it('markSubLoaded 单向置 true', () => {
    const store = useModelBuilderStore.getState();
    store.setNodes([makeNode('n1')]);

    store.markSubLoaded('n1');
    let node = useModelBuilderStore.getState().nodes.find((n) => n.id === 'n1');
    expect(node?.data.subLoaded).toBe(true);

    store.markSubLoaded('n1');
    node = useModelBuilderStore.getState().nodes.find((n) => n.id === 'n1');
    expect(node?.data.subLoaded).toBe(true);
  });

  it('partialize 不把 collapsed/subLoaded 写进 localStorage', () => {
    const store = useModelBuilderStore.getState();
    store.setNodes([makeNode('n1', true, true, true)]);

    const raw = localStorage.getItem('model-builder-draft');
    expect(raw).toBeTruthy();

    const persisted = JSON.parse(raw!);
    expect(persisted.state.nodes).toHaveLength(1);
    expect(persisted.state.nodes[0].data.collapsed).toBeUndefined();
    expect(persisted.state.nodes[0].data.subLoaded).toBeUndefined();
    expect(persisted.state.nodes[0].data.isComposite).toBe(true);
  });
});
