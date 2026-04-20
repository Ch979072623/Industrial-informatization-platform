import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mlModuleApi } from '@/services/api';
import { useModelBuilderStore } from './modelBuilderStore';
import type { RFNode, ModuleSchemaDetail, ModuleDefinitionDetail } from '@/types/mlModule';

vi.mock('@/services/api', () => ({
  mlModuleApi: {
    getModule: vi.fn(),
  },
}));

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
      moduleSchemas: {},
      moduleSchemaLoading: {},
      moduleSchemaError: {},
      updateNodeInternalsRef: null,
    });
    vi.mocked(mlModuleApi.getModule).mockClear();
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

  it('toggleCollapse 会通过 updateNodeInternalsRef 通知 React Flow', async () => {
    const mockUpdate = vi.fn();
    const store = useModelBuilderStore.getState();
    store.setUpdateNodeInternalsRef(mockUpdate);
    store.setNodes([makeNode('test-composite', true)]);

    store.toggleCollapse('test-composite');

    // 等待 queueMicrotask 执行
    await Promise.resolve();

    expect(mockUpdate).toHaveBeenCalledWith('test-composite');
    expect(mockUpdate).toHaveBeenCalledTimes(1);

    store.setUpdateNodeInternalsRef(null);
  });

  it('toggleCollapse 对 atomic 节点不触发 updateNodeInternals', async () => {
    const mockUpdate = vi.fn();
    const store = useModelBuilderStore.getState();
    store.setUpdateNodeInternalsRef(mockUpdate);
    store.setNodes([makeNode('test-atomic', false)]);

    store.toggleCollapse('test-atomic');
    await Promise.resolve();

    expect(mockUpdate).not.toHaveBeenCalled();

    store.setUpdateNodeInternalsRef(null);
  });

  it('toggleCollapse 不触发 saveHistory（纯视觉操作不进 undo 栈）', () => {
    const saveHistorySpy = vi.spyOn(useModelBuilderStore.getState(), 'saveHistory');

    const store = useModelBuilderStore.getState();
    store.setNodes([makeNode('test-composite', true)]);

    store.toggleCollapse('test-composite');

    expect(saveHistorySpy).not.toHaveBeenCalled();
    saveHistorySpy.mockRestore();
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

  it('getOrLoadModuleSchema 缓存命中返回 cached，不走 API', async () => {
    const schema: ModuleSchemaDetail = {
      id: 'test-mod',
      type: 'TestMod',
      display_name: '测试模块',
      category: 'atomic',
      is_composite: false,
      source: 'builtin',
      version: 1,
      params_schema: [],
      proxy_inputs: [],
      proxy_outputs: [],
    };
    useModelBuilderStore.setState({ moduleSchemas: { TestMod: schema } });
    const store = useModelBuilderStore.getState();
    const result = await store.getOrLoadModuleSchema('TestMod');
    expect(result).toEqual(schema);
    expect(mlModuleApi.getModule).not.toHaveBeenCalled();
  });

  it('getOrLoadModuleSchema 缓存 miss 时调 API 且写入缓存', async () => {
    const detail: ModuleDefinitionDetail = {
      id: 'pmsfa',
      type: 'PMSFA',
      display_name: 'PMSFA',
      category: 'backbone',
      is_composite: true,
      source: 'builtin',
      version: 1,
      params_schema: [],
      proxy_inputs: [],
      proxy_outputs: [],
      schema_json: {
        type: 'PMSFA',
        category: 'backbone',
        display_name: 'PMSFA',
        is_composite: true,
        params_schema: [],
        proxy_inputs: [],
        proxy_outputs: [],
        sub_nodes: [{ id: 'n1', type: 'Conv2d', params: {}, position: { x: 0, y: 0 } }],
        sub_edges: [],
      },
    };
    vi.mocked(mlModuleApi.getModule).mockResolvedValue({
      data: { success: true, data: detail },
    } as unknown as Awaited<ReturnType<typeof mlModuleApi.getModule>>);

    const store = useModelBuilderStore.getState();
    const result = await store.getOrLoadModuleSchema('PMSFA');

    expect(mlModuleApi.getModule).toHaveBeenCalledWith('PMSFA');
    expect(result).toBeTruthy();
    expect(useModelBuilderStore.getState().moduleSchemas['PMSFA']).toBeTruthy();
    expect(useModelBuilderStore.getState().moduleSchemaLoading['PMSFA']).toBe(false);
  });

  it('getOrLoadModuleSchema API 失败时设置 error state', async () => {
    vi.mocked(mlModuleApi.getModule).mockRejectedValue(new Error('Network Error'));

    const store = useModelBuilderStore.getState();
    const result = await store.getOrLoadModuleSchema('PMSFA');

    expect(result).toBeNull();
    expect(useModelBuilderStore.getState().moduleSchemaError['PMSFA']).toBe('Network Error');
    expect(useModelBuilderStore.getState().moduleSchemaLoading['PMSFA']).toBe(false);
    expect(useModelBuilderStore.getState().moduleSchemas['PMSFA']).toBeUndefined();
  });

  it('onEdgesChange 处理 remove 类型变更后 edges 数组正确更新', () => {
    const store = useModelBuilderStore.getState();
    store.setNodes([makeNode('n1'), makeNode('n2')]);
    store.setEdges([
      { id: 'e1', source: 'n1', target: 'n2' },
      { id: 'e2', source: 'n2', target: 'n1' },
    ]);

    store.onEdgesChange([{ type: 'remove', id: 'e1' }]);

    const edges = useModelBuilderStore.getState().edges;
    expect(edges).toHaveLength(1);
    expect(edges.find((e) => e.id === 'e1')).toBeUndefined();
    expect(edges[0].id).toBe('e2');
  });

  it('setEdges 过滤选中 edges 后数组正确更新', () => {
    const store = useModelBuilderStore.getState();
    store.setEdges([
      { id: 'e1', source: 'n1', target: 'n2', selected: false },
      { id: 'e2', source: 'n2', target: 'n1', selected: true },
      { id: 'e3', source: 'n1', target: 'n3', selected: true },
    ]);

    const selectedEdgeIds = useModelBuilderStore.getState().edges
      .filter((e) => e.selected)
      .map((e) => e.id);

    store.setEdges((eds) => eds.filter((e) => !selectedEdgeIds.includes(e.id)));

    const edges = useModelBuilderStore.getState().edges;
    expect(edges).toHaveLength(1);
    expect(edges[0].id).toBe('e1');
    expect(edges.find((e) => e.id === 'e2')).toBeUndefined();
    expect(edges.find((e) => e.id === 'e3')).toBeUndefined();
  });

  it('setViewport 正确更新 viewport 状态', () => {
    const store = useModelBuilderStore.getState();
    store.setViewport({ x: 100, y: 200, zoom: 1.5 });

    const state = useModelBuilderStore.getState();
    expect(state.viewport).toEqual({ x: 100, y: 200, zoom: 1.5 });
  });

  it('partialize 把 viewport 写进 localStorage', () => {
    const store = useModelBuilderStore.getState();
    store.setViewport({ x: 50, y: 60, zoom: 0.8 });

    const raw = localStorage.getItem('model-builder-draft');
    expect(raw).toBeTruthy();

    const persisted = JSON.parse(raw!);
    expect(persisted.state.viewport).toEqual({ x: 50, y: 60, zoom: 0.8 });
  });
});
