import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReactFlowProvider } from '@xyflow/react';
import { InputPortNode, OutputPortNode } from './PortNode';
import type { ModelNodeData } from '@/types/mlModule';

function renderWithProvider(node: React.ReactNode) {
  return render(<ReactFlowProvider>{node}</ReactFlowProvider>);
}

describe('InputPortNode', () => {
  it('渲染端口名称', () => {
    const data: ModelNodeData = {
      moduleType: 'InputPort',
      moduleName: 'InputPort',
      displayName: '输入端口',
      parameters: { name: 'features' },
      inputPorts: [],
      outputPorts: [{ name: 'out', type: 'tensor' }],
    };

    renderWithProvider(
      <InputPortNode
        id="ip-1"
        type="input_port"
        data={data as unknown as Record<string, unknown>}
        selected={false}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        {...{} as any}
      />
    );

    expect(screen.getByText('features')).toBeInTheDocument();
  });

  it('使用默认名称当参数缺失时', () => {
    const data: ModelNodeData = {
      moduleType: 'InputPort',
      moduleName: 'InputPort',
      displayName: '输入端口',
      parameters: {},
      inputPorts: [],
      outputPorts: [],
    };

    renderWithProvider(
      <InputPortNode
        id="ip-2"
        type="input_port"
        data={data as unknown as Record<string, unknown>}
        selected={false}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        {...{} as any}
      />
    );

    expect(screen.getByText('InputPort')).toBeInTheDocument();
  });
});

describe('OutputPortNode', () => {
  it('渲染端口名称', () => {
    const data: ModelNodeData = {
      moduleType: 'OutputPort',
      moduleName: 'OutputPort',
      displayName: '输出端口',
      parameters: { name: 'predictions' },
      inputPorts: [{ name: 'in', type: 'tensor' }],
      outputPorts: [],
    };

    renderWithProvider(
      <OutputPortNode
        id="op-1"
        type="output_port"
        data={data as unknown as Record<string, unknown>}
        selected={false}
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        {...{} as any}
      />
    );

    expect(screen.getByText('predictions')).toBeInTheDocument();
  });
});
