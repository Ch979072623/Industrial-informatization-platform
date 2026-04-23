import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useModelBuilderStore } from '@/stores/modelBuilderStore';
import { mlModuleApi, modelBuilderApi } from '@/services/api';
import type { RFNode } from '@/types/mlModule';

// Mock API
vi.mock('@/services/api', () => ({
  mlModuleApi: {
    getModule: vi.fn(),
    createModule: vi.fn(),
    getModules: vi.fn(),
  },
  modelBuilderApi: {
    getConfigs: vi.fn(),
    getConfig: vi.fn(),
    createConfig: vi.fn(),
  },
}));

const toastMock = vi.hoisted(() => vi.fn());
vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useSearchParams: () => [new URLSearchParams(), vi.fn()],
}));

vi.mock('@/components/model-builder/ModelCanvas', () => ({
  ModelCanvas: ({ onNodeSelect, onSave }: { onNodeSelect?: (node: RFNode | null) => void; onSave?: () => void }) => (
    <div data-testid="model-canvas">
      <button
        data-testid="select-input-port"
        onClick={() =>
          onNodeSelect?.({
            id: 'ip-1',
            type: 'input_port',
            position: { x: 0, y: 0 },
            data: {
              moduleType: 'InputPort',
              moduleName: 'InputPort',
              displayName: '输入端口',
              parameters: { name: 'x' },
              inputPorts: [],
              outputPorts: [{ name: 'out', type: 'tensor' }],
            },
          } as unknown as RFNode)
        }
      >
        Select InputPort
      </button>
      <button
        data-testid="select-output-port"
        onClick={() =>
          onNodeSelect?.({
            id: 'op-1',
            type: 'output_port',
            position: { x: 0, y: 0 },
            data: {
              moduleType: 'OutputPort',
              moduleName: 'OutputPort',
              displayName: '输出端口',
              parameters: { name: 'out' },
              inputPorts: [{ name: 'in', type: 'tensor' }],
              outputPorts: [],
            },
          } as unknown as RFNode)
        }
      >
        Select OutputPort
      </button>
      <button
        data-testid="select-module"
        onClick={() =>
          onNodeSelect?.({
            id: 'mod-1',
            type: 'module',
            position: { x: 0, y: 0 },
            data: {
              moduleType: 'Conv2d',
              moduleName: 'Conv2d',
              displayName: '卷积层',
              parameters: {},
              inputPorts: [{ name: 'input', type: 'tensor' }],
              outputPorts: [{ name: 'output', type: 'tensor' }],
            },
          } as unknown as RFNode)
        }
      >
        Select Module
      </button>
      <button data-testid="save-button" onClick={() => onSave?.()}>保存</button>
    </div>
  ),
}));

vi.mock('@/components/model-builder/ModuleLibrary', () => ({
  ModuleLibrary: () => <div data-testid="module-library" />,
}));

vi.mock('@/components/model-builder/NodeConfigPanel', () => ({
  NodeConfigPanel: () => <div data-testid="node-config-panel" />,
}));

vi.mock('@/components/ErrorBoundary', () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('ModelBuilder port node guard', () => {
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
      updateNodeInternalsRef: null,
      mode: 'architecture',
    });
    vi.mocked(mlModuleApi.getModule).mockClear();
    vi.mocked(mlModuleApi.createModule).mockClear();
    vi.mocked(modelBuilderApi.createConfig).mockClear();
  });

  it('点击 InputPort 节点时不发起模块详情请求', async () => {
    const ModelBuilder = (await import('./ModelBuilder')).default;
    render(<ModelBuilder />);

    fireEvent.click(screen.getByTestId('select-input-port'));

    await waitFor(() => {
      expect(mlModuleApi.getModule).not.toHaveBeenCalled();
    });
  });

  it('点击 OutputPort 节点时不发起模块详情请求', async () => {
    const ModelBuilder = (await import('./ModelBuilder')).default;
    render(<ModelBuilder />);

    fireEvent.click(screen.getByTestId('select-output-port'));

    await waitFor(() => {
      expect(mlModuleApi.getModule).not.toHaveBeenCalled();
    });
  });

  it('点击普通 module 节点时仍发起模块详情请求', async () => {
    vi.mocked(mlModuleApi.getModule).mockResolvedValue({
      data: {
        success: true,
        data: {
          type: 'Conv2d',
          display_name: '卷积层',
          category: 'atomic',
          is_composite: false,
          proxy_inputs: [{ name: 'input' }],
          proxy_outputs: [{ name: 'output' }],
          params_schema: [
            { name: 'in_channels', type: 'int', default: 64 },
          ],
          input_ports_dynamic: false,
        },
      },
    } as unknown as Awaited<ReturnType<typeof mlModuleApi.getModule>>);

    const ModelBuilder = (await import('./ModelBuilder')).default;
    render(<ModelBuilder />);

    fireEvent.click(screen.getByTestId('select-module'));

    await waitFor(() => {
      expect(mlModuleApi.getModule).toHaveBeenCalledOnce();
      expect(mlModuleApi.getModule).toHaveBeenCalledWith('Conv2d');
    });
  });
});

describe('ModelBuilder save dialog branch', () => {
  beforeEach(() => {
    localStorage.clear();
    useModelBuilderStore.setState({
      nodes: [
        { id: 'n1', type: 'module', position: { x: 0, y: 0 }, data: { moduleType: 'Conv2d', parameters: {} } },
      ] as unknown as import('@/types/mlModule').RFNode[],
      edges: [],
      selectedNodeId: null,
      history: [],
      historyIndex: -1,
      moduleSchemas: {},
      moduleSchemaLoading: {},
      moduleSchemaError: {},
      updateNodeInternalsRef: null,
      mode: 'architecture',
    });
    vi.mocked(mlModuleApi.createModule).mockClear();
    vi.mocked(modelBuilderApi.createConfig).mockClear();
  });

  it('Module 模式下打开保存对话框显示注册字段', async () => {
    useModelBuilderStore.setState({ mode: 'module' });
    const ModelBuilder = (await import('./ModelBuilder')).default;
    render(<ModelBuilder />);

    fireEvent.click(screen.getByTestId('save-button'));

    await waitFor(() => {
      expect(screen.getByText('注册为新模块')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('模块名 *')).toBeInTheDocument();
    expect(screen.getByLabelText('显示名 *')).toBeInTheDocument();
    expect(screen.getByLabelText('分类 *')).toBeInTheDocument();
    expect(screen.getByLabelText('描述')).toBeInTheDocument();
  });

  it('Architecture 模式下打开保存对话框显示原有字段', async () => {
    const ModelBuilder = (await import('./ModelBuilder')).default;
    render(<ModelBuilder />);

    fireEvent.click(screen.getByTestId('save-button'));

    await waitFor(() => {
      expect(screen.getByText('保存模型配置')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('配置名称 *')).toBeInTheDocument();
    expect(screen.getByLabelText('配置描述')).toBeInTheDocument();
  });

  it('Module 模式点击注册调用 createModule', async () => {
    useModelBuilderStore.setState({ mode: 'module' });
    vi.mocked(mlModuleApi.createModule).mockResolvedValue({
      data: { success: true, data: { type: 'MyBlock' } },
    } as unknown as Awaited<ReturnType<typeof mlModuleApi.createModule>>);
    vi.mocked(mlModuleApi.getModules).mockResolvedValue({
      data: { success: true, data: [] },
    } as unknown as Awaited<ReturnType<typeof mlModuleApi.getModules>>);

    const ModelBuilder = (await import('./ModelBuilder')).default;
    render(<ModelBuilder />);

    fireEvent.click(screen.getByTestId('save-button'));
    await waitFor(() => expect(screen.getByText('注册为新模块')).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('模块名 *'), { target: { value: 'MyBlock' } });
    fireEvent.change(screen.getByLabelText('显示名 *'), { target: { value: '我的模块' } });
    fireEvent.click(screen.getByText('注册'));

    await waitFor(() => {
      expect(mlModuleApi.createModule).toHaveBeenCalledOnce();
    });
    expect(modelBuilderApi.createConfig).not.toHaveBeenCalled();
  });

  it('409 冲突时 toast 显示 suggested_name', async () => {
    useModelBuilderStore.setState({ mode: 'module' });
    vi.mocked(mlModuleApi.createModule).mockRejectedValue({
      response: { status: 409, data: { detail: { suggested_name: 'PMSFA_v2' } } },
    });

    const ModelBuilder = (await import('./ModelBuilder')).default;
    render(<ModelBuilder />);

    fireEvent.click(screen.getByTestId('save-button'));
    await waitFor(() => expect(screen.getByText('注册为新模块')).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('模块名 *'), { target: { value: 'PMSFA' } });
    fireEvent.change(screen.getByLabelText('显示名 *'), { target: { value: 'PMSFA' } });
    fireEvent.click(screen.getByText('注册'));

    await waitFor(() => {
      expect(toastMock).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '模块名已被占用',
          description: '建议使用 PMSFA_v2',
          variant: 'destructive',
        })
      );
    });
  });
});
