import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import CompositeNode from './CompositeNode';
import { useModelBuilderStore } from '@/stores/modelBuilderStore';
import type { ModelNodeData, ModuleSchemaDetail } from '@/types/mlModule';

const baseData: ModelNodeData = {
  moduleType: 'PMSFA',
  moduleName: 'PMSFA',
  displayName: '多尺度融合',
  parameters: { scales: [1, 2, 4] },
  inputPorts: [{ name: 'input', type: 'tensor' }],
  outputPorts: [{ name: 'output', type: 'tensor' }],
  isComposite: true,
};

function renderWithProvider(props: unknown) {
  return render(
    <ReactFlowProvider>
      <CompositeNode {...props as React.ComponentProps<typeof CompositeNode>} />
    </ReactFlowProvider>
  );
}

describe('CompositeNode', () => {
  beforeEach(() => {
    useModelBuilderStore.setState({
      moduleSchemas: {},
      moduleSchemaLoading: {},
      moduleSchemaError: {},
    });
  });

  it('渲染复合节点基础字段', () => {
    const props = {
      id: 'node-1',
      type: 'module' as const,
      data: baseData,
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.getByText('多尺度融合')).toBeInTheDocument();
    expect(screen.getByText('PMSFA')).toBeInTheDocument();
  });

  it('渲染右上角折叠状态图标', () => {
    const props = {
      id: 'node-2',
      type: 'module' as const,
      data: baseData,
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.getByTestId('composite-collapse-indicator')).toBeInTheDocument();
  });

  it('折叠态（collapsed 为 true 或 undefined）渲染折叠外观', () => {
    for (const collapsed of [true, undefined]) {
      const { unmount } = renderWithProvider({
        id: 'node-3',
        type: 'module' as const,
        data: { ...baseData, collapsed },
        selected: false,
      });

      expect(screen.getByTestId('composite-collapse-indicator')).toBeInTheDocument();
      expect(screen.queryByTestId('composite-children')).not.toBeInTheDocument();
      unmount();
    }
  });

  it('展开态渲染子画布容器且不渲染参数摘要', () => {
    const props = {
      id: 'node-4',
      type: 'module' as const,
      data: { ...baseData, collapsed: false },
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.getByTestId('composite-children')).toBeInTheDocument();
    expect(screen.queryByText('[1, 2, 4]')).not.toBeInTheDocument();
  });

  it('折叠态渲染参数摘要不渲染子画布容器', () => {
    for (const collapsed of [true, undefined]) {
      const { unmount } = renderWithProvider({
        id: 'node-5',
        type: 'module' as const,
        data: { ...baseData, collapsed },
        selected: false,
      });

      expect(screen.queryByTestId('composite-children')).not.toBeInTheDocument();
      expect(screen.getByText('[1, 2, 4]')).toBeInTheDocument();
      unmount();
    }
  });

  it('展开态右上角图标为 Minimize2', () => {
    const props = {
      id: 'node-6',
      type: 'module' as const,
      data: { ...baseData, collapsed: false },
      selected: false,
    };

    renderWithProvider(props);
    const indicator = screen.getByTestId('composite-collapse-indicator');
    expect(indicator.querySelector('.lucide-minimize2')).toBeInTheDocument();
  });

  it('折叠态右上角图标为 Maximize2', () => {
    for (const collapsed of [true, undefined]) {
      const { unmount } = renderWithProvider({
        id: 'node-7',
        type: 'module' as const,
        data: { ...baseData, collapsed },
        selected: false,
      });

      const indicator = screen.getByTestId('composite-collapse-indicator');
      expect(indicator.querySelector('.lucide-maximize2')).toBeInTheDocument();
      unmount();
    }
  });

  it('双击标题栏触发 toggleCollapse', () => {
    const spy = vi.spyOn(useModelBuilderStore.getState(), 'toggleCollapse');

    const props = {
      id: 'test-node-id',
      type: 'module' as const,
      data: { ...baseData, collapsed: true },
      selected: false,
    };

    renderWithProvider(props);
    const header = screen.getByTestId('composite-header');
    fireEvent.doubleClick(header);

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith('test-node-id');

    spy.mockRestore();
  });

  it('展开态 loading 状态显示 spinner', () => {
    useModelBuilderStore.setState({ moduleSchemaLoading: { PMSFA: true } });
    const props = {
      id: 'node-loading',
      type: 'module' as const,
      data: { ...baseData, collapsed: false },
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.getByTestId('composite-loading')).toBeInTheDocument();
  });

  it('展开态 error 状态显示重试按钮', () => {
    useModelBuilderStore.setState({ moduleSchemaError: { PMSFA: '网络错误' } });
    const props = {
      id: 'node-error',
      type: 'module' as const,
      data: { ...baseData, collapsed: false },
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.getByTestId('composite-error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /重试/i })).toBeInTheDocument();
  });

  it('展开态 success 状态显示 SubGraphView', () => {
    const schema: Partial<ModuleSchemaDetail> = {
      sub_nodes: [
        { id: 'a', type: 'Conv2d', params: {}, position: { x: 0, y: 0 } },
        { id: 'b', type: 'ReLU', params: {}, position: { x: 120, y: 0 } },
      ],
      sub_edges: [{ source: 'a', source_port: 0, target: 'b', target_port: 0 }],
    };
    useModelBuilderStore.setState({
      moduleSchemas: { PMSFA: schema as ModuleSchemaDetail },
    });
    const props = {
      id: 'node-success',
      type: 'module' as const,
      data: { ...baseData, collapsed: false },
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.getByTestId('subgraph-view')).toBeInTheDocument();
    expect(screen.getByText('Conv2d')).toBeInTheDocument();
    expect(screen.getByText('ReLU')).toBeInTheDocument();
  });

  it('展开态子画布应用横向转置：sub_nodes 的 x 和 y 被交换渲染', () => {
    const schema: Partial<ModuleSchemaDetail> = {
      sub_nodes: [
        // 原始 schema 是纵向布局：x 相同，y 递增
        { id: 'n1', type: 'Conv2d', params: {}, position: { x: 100, y: 40 } },
        { id: 'n2', type: 'Chunk', params: {}, position: { x: 100, y: 120 } },
      ],
      sub_edges: [],
    };
    useModelBuilderStore.setState({
      moduleSchemas: { PMSFA: schema as ModuleSchemaDetail },
    });
    const props = {
      id: 'node-transpose',
      type: 'module' as const,
      data: { ...baseData, collapsed: false },
      selected: false,
    };

    renderWithProvider(props);
    const n1 = screen.getByTestId('child-node-n1');
    const n2 = screen.getByTestId('child-node-n2');

    // 转置后：left/top 应该互换
    expect(n1).toHaveStyle({ left: '40px', top: '100px' });
    expect(n2).toHaveStyle({ left: '120px', top: '100px' });
  });
});
