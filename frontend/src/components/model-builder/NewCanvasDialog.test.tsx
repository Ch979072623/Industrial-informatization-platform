import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NewCanvasDialog } from './NewCanvasDialog';

describe('NewCanvasDialog', () => {
  it('默认选中 Architecture 模式', () => {
    render(
      <NewCanvasDialog
        open={true}
        onOpenChange={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(2);
    // 第一个 radio 对应 architecture（默认选中）
    expect(radios[1]).toBeChecked(); // architecture radio
    expect(radios[0]).not.toBeChecked(); // module radio
  });

  it('可切换为 Module 模式', () => {
    render(
      <NewCanvasDialog
        open={true}
        onOpenChange={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    const radios = screen.getAllByRole('radio');
    fireEvent.click(radios[0]); // module radio
    expect(radios[0]).toBeChecked();
    expect(radios[1]).not.toBeChecked();
  });

  it('点击确认时回调所选模式', () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();

    render(
      <NewCanvasDialog
        open={true}
        onOpenChange={onOpenChange}
        onConfirm={onConfirm}
      />
    );

    const radios = screen.getAllByRole('radio');
    fireEvent.click(radios[0]); // module radio

    const confirmBtn = screen.getByRole('button', { name: /确认创建/i });
    fireEvent.click(confirmBtn);

    expect(onConfirm).toHaveBeenCalledWith('module');
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('点击取消关闭弹窗', () => {
    const onOpenChange = vi.fn();

    render(
      <NewCanvasDialog
        open={true}
        onOpenChange={onOpenChange}
        onConfirm={vi.fn()}
      />
    );

    const cancelBtn = screen.getByRole('button', { name: /取消/i });
    fireEvent.click(cancelBtn);

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
