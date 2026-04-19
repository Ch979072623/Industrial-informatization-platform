import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import CompositeNode from './CompositeNode';
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

  it('渲染右上角展开图标', () => {
    const props = {
      id: 'node-2',
      type: 'module' as const,
      data: baseData,
      selected: false,
    };

    renderWithProvider(props);
    expect(screen.getByTestId('composite-expand-icon')).toBeInTheDocument();
  });

  it('不同 collapsed 值视觉一致（均按折叠态渲染）', () => {
    for (const collapsed of [true, false, undefined]) {
      const { unmount } = renderWithProvider({
        id: 'node-3',
        type: 'module' as const,
        data: { ...baseData, collapsed },
        selected: false,
      });

      expect(screen.getByTestId('composite-expand-icon')).toBeInTheDocument();
      expect(screen.queryByTestId('composite-children')).not.toBeInTheDocument();
      unmount();
    }
  });
});
