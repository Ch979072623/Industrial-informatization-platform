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
});
