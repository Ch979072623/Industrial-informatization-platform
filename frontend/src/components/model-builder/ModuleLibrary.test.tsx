import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ModuleLibrary } from './ModuleLibrary';
import { mlModuleApi } from '@/services/api';

vi.mock('@/services/api', () => ({
  mlModuleApi: {
    getModules: vi.fn(),
  },
}));

describe('ModuleLibrary mode filtering', () => {
  beforeEach(() => {
    vi.mocked(mlModuleApi.getModules).mockResolvedValue({
      data: {
        success: true,
        data: [
          {
            id: 'conv2d',
            type: 'Conv2d',
            display_name: '卷积层',
            category: 'atomic',
            is_composite: false,
            proxy_inputs: [],
            proxy_outputs: [{ name: 'output' }],
            params_schema: [],
            input_ports_dynamic: false,
          },
        ],
      },
    } as unknown as Awaited<ReturnType<typeof mlModuleApi.getModules>>);
  });

  it('architecture 模式下不显示端口节点', async () => {
    render(<ModuleLibrary mode="architecture" onModuleDragStart={vi.fn()} />);

    // 等待 API 返回
    await screen.findByText('卷积层');

    expect(screen.queryByText('输入端口')).not.toBeInTheDocument();
    expect(screen.queryByText('输出端口')).not.toBeInTheDocument();
  });

  it('module 模式下显示端口节点', async () => {
    render(<ModuleLibrary mode="module" onModuleDragStart={vi.fn()} />);

    await screen.findByText('卷积层');

    expect(screen.getByText('输入端口')).toBeInTheDocument();
    expect(screen.getByText('输出端口')).toBeInTheDocument();
  });

  it('端口节点可拖拽并携带正确数据', async () => {
    render(<ModuleLibrary mode="module" onModuleDragStart={vi.fn()} />);

    await screen.findByText('卷积层');

    const inputPort = screen.getByText('输入端口').closest('[draggable]') as HTMLElement;
    expect(inputPort).toBeTruthy();

    const dataTransfer = {
      setData: vi.fn(),
      effectAllowed: '',
    };
    fireEvent.dragStart(inputPort, { dataTransfer });

    expect(dataTransfer.setData).toHaveBeenCalledWith(
      'application/reactflow',
      expect.stringContaining('"__portType":"input_port"')
    );
  });
});
