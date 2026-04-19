import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import AtomicNode from './AtomicNode';
import type { ModelNodeData } from '@/types/mlModule';

const baseData: ModelNodeData = {
  moduleType: 'Conv2d',
  moduleName: 'Conv2d',
  displayName: '卷积层',
  parameters: { in_channels: 64, out_channels: 128, kernel_size: 3 },
  inputPorts: [{ name: 'input', type: 'tensor' }],
  outputPorts: [{ name: 'output', type: 'tensor' }],
};

function renderWithProvider(props: unknown) {
  return render(
    <ReactFlowProvider>
      <AtomicNode {...props as React.ComponentProps<typeof AtomicNode>} />
    </ReactFlowProvider>
  );
}

describe('AtomicNode', () => {
  it('渲染完整原子节点', () => {
    const props = {
      id: 'node-1',
      type: 'module' as const,
      data: baseData,
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.getByText('卷积层')).toBeInTheDocument();
    expect(screen.getByText('Conv2d')).toBeInTheDocument();
  });

  it('空端口数组不渲染 Handle 且不崩溃', () => {
    const props = {
      id: 'node-2',
      type: 'module' as const,
      data: { ...baseData, inputPorts: [], outputPorts: [] },
      selected: false,
    };

    const { container } = renderWithProvider(props);
    const handles = container.querySelectorAll('.react-flow__handle');
    expect(handles.length).toBe(0);
  });

  it('不渲染复合节点展开图标', () => {
    const props = {
      id: 'node-3',
      type: 'module' as const,
      data: baseData,
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.queryByTestId('composite-expand-icon')).not.toBeInTheDocument();
  });
});
