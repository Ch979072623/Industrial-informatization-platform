import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import AtomicNode from './AtomicNode';
import type { ModelNodeData } from '@/types/mlModule';

// Mock useNodeConnections 以控制连接数
vi.mock('@xyflow/react', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@xyflow/react')>();
  return {
    ...actual,
    useNodeConnections: vi.fn(() => []),
  };
});

// 必须在 mock 之后导入
import { useNodeConnections } from '@xyflow/react';

const baseData: ModelNodeData = {
  moduleType: 'Conv2d',
  moduleName: 'Conv2d',
  displayName: '卷积层',
  parameters: { in_channels: 64, out_channels: 128, kernel_size: 3 },
  inputPorts: [{ name: 'input', type: 'tensor' }],
  outputPorts: [{ name: 'output', type: 'tensor' }],
};

const concatData: ModelNodeData = {
  moduleType: 'Concat',
  moduleName: 'Concat',
  displayName: '通道拼接',
  parameters: { dim: 1 },
  inputPorts: [
    { name: 'in_0', type: 'tensor' },
    { name: 'in_1', type: 'tensor' },
  ],
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
  beforeEach(() => {
    // 重置 mock 为默认值（无连接）
    (useNodeConnections as ReturnType<typeof vi.fn>).mockReturnValue([]);
  });

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

  it('静态端口模式：按 inputPorts 原样渲染，不动态扩展', () => {
    const props = {
      id: 'node-static',
      type: 'module' as const,
      data: { ...concatData, inputPortsDynamic: false },
      selected: false,
    };

    const { container } = renderWithProvider(props);
    const inputHandles = container.querySelectorAll('.react-flow__handle[data-handlepos="left"]');
    expect(inputHandles.length).toBe(2);
  });

  it('动态端口模式 - 无连接：渲染 basePorts.length 个端口', () => {
    const props = {
      id: 'node-dyn-empty',
      type: 'module' as const,
      data: { ...concatData, inputPortsDynamic: true },
      selected: false,
    };

    const { container } = renderWithProvider(props);
    const inputHandles = container.querySelectorAll('.react-flow__handle[data-handlepos="left"]');
    expect(inputHandles.length).toBe(2);
  });

  it('动态端口模式 - 已连接 2 条：渲染 3 个端口（2 连接 + 1 预留）', () => {
    (useNodeConnections as ReturnType<typeof vi.fn>).mockReturnValue([
      { source: 'a', sourceHandle: 'out', target: 'node-dyn-2', targetHandle: 'in_0' },
      { source: 'b', sourceHandle: 'out', target: 'node-dyn-2', targetHandle: 'in_1' },
    ]);

    const props = {
      id: 'node-dyn-2',
      type: 'module' as const,
      data: { ...concatData, inputPortsDynamic: true },
      selected: false,
    };

    const { container } = renderWithProvider(props);
    const inputHandles = container.querySelectorAll('.react-flow__handle[data-handlepos="left"]');
    expect(inputHandles.length).toBe(3);

    // 验证第三个动态生成的端口存在
    const handlesArray = Array.from(inputHandles);
    const thirdHandle = handlesArray[2] as HTMLElement;
    expect(thirdHandle.getAttribute('data-handleid')).toBe('in_2');
  });
});
