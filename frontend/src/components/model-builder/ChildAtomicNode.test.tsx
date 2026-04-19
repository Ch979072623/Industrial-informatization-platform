import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ChildAtomicNode from './ChildAtomicNode';
import type { SubNode } from '@/types/mlModule';

const mockSubNode: SubNode = {
  id: 'conv_3x3',
  type: 'Conv2d',
  params: { in_channels: 64 },
  position: { x: 100, y: 120 },
};

describe('ChildAtomicNode', () => {
  it('渲染正常 subNode，位置按 props 计算', () => {
    render(<ChildAtomicNode subNode={mockSubNode} />);
    const el = screen.getByTestId('child-node-conv_3x3');
    expect(el).toBeInTheDocument();
    expect(el).toHaveTextContent('Conv2d');
    expect(el).toHaveTextContent('conv_3x3');
    expect(el).toHaveStyle({ left: '100px', top: '120px' });
  });

  it('点击不触发任何回调（验证只读）', () => {
    render(<ChildAtomicNode subNode={mockSubNode} />);
    const el = screen.getByTestId('child-node-conv_3x3');
    expect(() => fireEvent.click(el)).not.toThrow();
  });
});
