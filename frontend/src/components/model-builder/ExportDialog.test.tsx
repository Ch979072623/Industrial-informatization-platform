import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ExportDialog } from './ExportDialog';

// Monaco Editor 在测试环境动态加载容易失败，直接 mock
vi.mock('@monaco-editor/react', () => ({
  default: function MockEditor({ value }: { value?: string }) {
    return <div data-testid="monaco-editor">{value}</div>;
  },
}));

describe('ExportDialog', () => {
  it('renders_yaml_tab', () => {
    render(
      <ExportDialog
        open={true}
        onClose={vi.fn()}
        yamlContent="backbone: [...]"
        codegenResults={[]}
      />
    );

    expect(screen.getByRole('tab', { name: /model\.yaml/i })).toBeInTheDocument();
  });

  it('renders_py_tabs', () => {
    render(
      <ExportDialog
        open={true}
        onClose={vi.fn()}
        yamlContent="backbone: [...]"
        codegenResults={[
          { type: 'MyBlock', code: 'class MyBlock:' },
          { type: 'CustomHead', code: 'class CustomHead:' },
        ]}
      />
    );

    expect(screen.getByRole('tab', { name: /model\.yaml/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /MyBlock\.py/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /CustomHead\.py/i })).toBeInTheDocument();
  });

  it('download_button_exists', () => {
    render(
      <ExportDialog
        open={true}
        onClose={vi.fn()}
        yamlContent="backbone: [...]"
        codegenResults={[{ type: 'MyBlock', code: 'class MyBlock:' }]}
      />
    );

    // 默认激活 yaml tab，应有下载按钮
    expect(screen.getByRole('button', { name: /下载/i })).toBeInTheDocument();
  });

  it('shows_error_state', () => {
    render(
      <ExportDialog
        open={true}
        onClose={vi.fn()}
        yamlContent=""
        codegenResults={[]}
        error="导出失败：未找到配置"
      />
    );

    expect(screen.getByText('导出失败')).toBeInTheDocument();
    expect(screen.getByText(/未找到配置/i)).toBeInTheDocument();
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
  });

  it('shows_loading_state', () => {
    render(
      <ExportDialog
        open={true}
        onClose={vi.fn()}
        yamlContent=""
        codegenResults={[]}
        loading={true}
      />
    );

    expect(screen.getByText(/正在生成导出文件/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /下载/i })).not.toBeInTheDocument();
  });

  it('py_tab_error', () => {
    render(
      <ExportDialog
        open={true}
        onClose={vi.fn()}
        yamlContent="backbone: [...]"
        codegenResults={[{ type: 'BadBlock', error: '缺少输入端口' }]}
        defaultActiveTab="BadBlock"
      />
    );

    // 错误 tab 应带有红色星号标记
    const badTab = screen.getByRole('tab', { name: /BadBlock\.py/i });
    expect(badTab.querySelector('span.text-destructive')).toBeInTheDocument();

    expect(screen.getByText('代码生成失败')).toBeInTheDocument();
    expect(screen.getByText(/缺少输入端口/i)).toBeInTheDocument();
    expect(screen.queryByTestId('monaco-editor')).not.toBeInTheDocument();
  });
});
