import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { isValidConnection, ModelCanvas } from './ModelCanvas';
import { useModelBuilderStore } from '@/stores/modelBuilderStore';
import type { RFNode, ModelNodeData } from '@/types/mlModule';

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

// React Flow v12 依赖 ResizeObserver，jsdom 未提供
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverMock;

function makeNode(id: string, inputPorts: string[], outputPorts: string[]): RFNode {
  const data: ModelNodeData = {
    moduleType: 'Test',
    moduleName: 'Test',
    displayName: 'Test',
    parameters: {},
    inputPorts: inputPorts.map((name) => ({ name, type: 'tensor' })),
    outputPorts: outputPorts.map((name) => ({ name, type: 'tensor' })),
  };
  return {
    id,
    position: { x: 0, y: 0 },
    type: 'module',
    data: data as unknown as Record<string, unknown>,
  };
}

describe('isValidConnection', () => {
  it('从 source handle（输出端口）出发 → 允许', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'n1',
      sourceHandle: 'out',
      target: 'n2',
      targetHandle: 'in',
    });
    expect(result).toBe(true);
  });

  it('从 target handle（输入端口）出发 → 拒绝', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'n1',
      sourceHandle: 'in',
      target: 'n2',
      targetHandle: 'out',
    });
    expect(result).toBe(false);
  });

  it('sourceHandle 不存在于节点端口列表 → 拒绝', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'n1',
      sourceHandle: 'nonexistent',
      target: 'n2',
      targetHandle: 'in',
    });
    expect(result).toBe(false);
  });

  it('sourceHandle 为 null → 允许（由其他校验处理）', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'n1',
      sourceHandle: null,
      target: 'n2',
      targetHandle: 'in',
    });
    expect(result).toBe(true);
  });

  it('source 节点不存在 → 允许（由其他校验处理）', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'missing',
      sourceHandle: 'out',
      target: 'n2',
      targetHandle: 'in',
    } as const);
    expect(result).toBe(true);
  });

  it('多输出端口时只匹配 outputPorts', () => {
    const nodes = [makeNode('n1', ['a', 'b'], ['x', 'y'])];
    expect(isValidConnection(nodes, { source: 'n1', sourceHandle: 'x', target: 'n2', targetHandle: 'a' })).toBe(true);
    expect(isValidConnection(nodes, { source: 'n1', sourceHandle: 'y', target: 'n2', targetHandle: 'a' })).toBe(true);
    expect(isValidConnection(nodes, { source: 'n1', sourceHandle: 'a', target: 'n2', targetHandle: 'x' })).toBe(false);
    expect(isValidConnection(nodes, { source: 'n1', sourceHandle: 'b', target: 'n2', targetHandle: 'x' })).toBe(false);
  });
});

describe('ModelCanvas toolbar', () => {
  beforeEach(() => {
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
      viewport: undefined,
    });
  });

  it('垃圾桶按钮在无选中节点且无选中 edge 时 disabled', () => {
    render(<ModelCanvas />);
    const btn = screen.getByTitle('删除选中 (Delete)');
    expect(btn).toBeDisabled();
  });

  it('垃圾桶按钮在有选中 edge 时 enabled', () => {
    useModelBuilderStore.setState({
      edges: [{ id: 'e1', source: 'n1', target: 'n2', selected: true }],
    });
    render(<ModelCanvas />);
    const btn = screen.getByTitle('删除选中 (Delete)');
    expect(btn).not.toBeDisabled();
  });

  it('点击垃圾桶按钮删除选中的 edges', () => {
    const store = useModelBuilderStore.getState();
    store.setEdges([
      { id: 'e1', source: 'n1', target: 'n2', selected: true },
      { id: 'e2', source: 'n2', target: 'n3', selected: false },
    ]);

    render(<ModelCanvas />);
    const btn = screen.getByTitle('删除选中 (Delete)');
    fireEvent.click(btn);

    const edges = useModelBuilderStore.getState().edges;
    expect(edges).toHaveLength(1);
    expect(edges[0].id).toBe('e2');
  });
});

describe('ModelCanvas window hotkeys', () => {
  beforeEach(() => {
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
      viewport: undefined,
    });
  });

  it('input 聚焦时 Delete 不触发画布删除', () => {
    useModelBuilderStore.setState({
      edges: [{ id: 'e1', source: 'n1', target: 'n2', selected: true }],
    });
    render(<ModelCanvas />);

    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true }));

    expect(useModelBuilderStore.getState().edges).toHaveLength(1);

    document.body.removeChild(input);
  });

  it('非 input 焦点时 Ctrl+Z 触发 undo', () => {
    useModelBuilderStore.setState({
      nodes: [{ id: 'n1', position: { x: 0, y: 0 }, type: 'module', data: {} } as unknown as RFNode],
      history: [
        { nodes: [], edges: [] },
        { nodes: [{ id: 'n1', position: { x: 0, y: 0 }, type: 'module', data: {} } as unknown as RFNode], edges: [] },
      ],
      historyIndex: 1,
    });
    render(<ModelCanvas />);

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true }));

    expect(useModelBuilderStore.getState().historyIndex).toBe(0);
  });

  it('input 内 Ctrl+S 阻止浏览器保存网页，但不触发画布保存', () => {
    const onSave = vi.fn();
    render(<ModelCanvas onSave={onSave} />);

    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();

    const event = new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true });
    const preventDefaultSpy = vi.spyOn(event, 'preventDefault');
    input.dispatchEvent(event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(onSave).not.toHaveBeenCalled();

    document.body.removeChild(input);
  });

  it('非 input 焦点时 Ctrl+S 触发画布保存', () => {
    const onSave = vi.fn();
    render(<ModelCanvas onSave={onSave} />);

    const event = new KeyboardEvent('keydown', { key: 's', ctrlKey: true, bubbles: true, cancelable: true });
    const preventDefaultSpy = vi.spyOn(event, 'preventDefault');
    window.dispatchEvent(event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
