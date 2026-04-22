import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NodeConfigPanel } from './NodeConfigPanel';
import type { RFNode } from '@/types/mlModule';

function makeInputPortNode(id: string, name: string): RFNode {
  return {
    id,
    type: 'input_port',
    position: { x: 0, y: 0 },
    data: {
      moduleType: 'InputPort',
      moduleName: 'InputPort',
      displayName: '输入端口',
      parameters: { name },
      inputPorts: [],
      outputPorts: [{ name: 'out', type: 'tensor' }],
    },
  } as unknown as RFNode;
}

function makeOutputPortNode(id: string, name: string): RFNode {
  return {
    id,
    type: 'output_port',
    position: { x: 0, y: 0 },
    data: {
      moduleType: 'OutputPort',
      moduleName: 'OutputPort',
      displayName: '输出端口',
      parameters: { name },
      inputPorts: [{ name: 'in', type: 'tensor' }],
      outputPorts: [],
    },
  } as unknown as RFNode;
}

describe('NodeConfigPanel port nodes', () => {
  it('InputPort 渲染 name 输入框且不显示空状态', () => {
    render(
      <NodeConfigPanel
        node={makeInputPortNode('ip-1', 'x')}
        moduleDetails={null}
        onParamChange={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('端口名称')).toBeInTheDocument();
    expect(screen.getByDisplayValue('x')).toBeInTheDocument();
    expect(screen.queryByText('此模块没有可配置参数')).not.toBeInTheDocument();
  });

  it('OutputPort 渲染 name 输入框且不显示空状态', () => {
    render(
      <NodeConfigPanel
        node={makeOutputPortNode('op-1', 'out')}
        moduleDetails={null}
        onParamChange={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByText('端口名称')).toBeInTheDocument();
    expect(screen.getByDisplayValue('out')).toBeInTheDocument();
    expect(screen.queryByText('此模块没有可配置参数')).not.toBeInTheDocument();
  });

  it('修改 InputPort name 后点击应用，onParamChange 正确触发', () => {
    const onParamChange = vi.fn();
    render(
      <NodeConfigPanel
        node={makeInputPortNode('ip-1', 'x')}
        moduleDetails={null}
        onParamChange={onParamChange}
        onClose={vi.fn()}
      />
    );

    const input = screen.getByDisplayValue('x') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'input_1' } });
    expect(input.value).toBe('input_1');

    const applyBtn = screen.getByRole('button', { name: /应用更改/i });
    fireEvent.click(applyBtn);

    expect(onParamChange).toHaveBeenCalledOnce();
    expect(onParamChange).toHaveBeenCalledWith('ip-1', { name: 'input_1' });
  });

  it('切换 node.id 时本地 state 重置为新节点的 name', () => {
    const { rerender } = render(
      <NodeConfigPanel
        node={makeInputPortNode('ip-a', 'x')}
        moduleDetails={null}
        onParamChange={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue('x')).toBeInTheDocument();

    rerender(
      <NodeConfigPanel
        node={makeInputPortNode('ip-b', 'features')}
        moduleDetails={null}
        onParamChange={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue('features')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('x')).not.toBeInTheDocument();
  });
});
