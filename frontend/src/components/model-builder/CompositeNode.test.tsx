import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import CompositeNode from './CompositeNode';
import { useModelBuilderStore } from '@/stores/modelBuilderStore';
import type { ModelNodeData } from '@/types/mlModule';

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

  it('展开态渲染占位区域且不渲染参数摘要', () => {
    const props = {
      id: 'node-4',
      type: 'module' as const,
      data: { ...baseData, collapsed: false },
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.getByTestId('composite-expanded-placeholder')).toBeInTheDocument();
    expect(screen.queryByText('[1, 2, 4]')).not.toBeInTheDocument();
  });

  it('折叠态渲染参数摘要不渲染占位区域', () => {
    for (const collapsed of [true, undefined]) {
      const { unmount } = renderWithProvider({
        id: 'node-5',
        type: 'module' as const,
        data: { ...baseData, collapsed },
        selected: false,
      });

      expect(screen.queryByTestId('composite-expanded-placeholder')).not.toBeInTheDocument();
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
});
