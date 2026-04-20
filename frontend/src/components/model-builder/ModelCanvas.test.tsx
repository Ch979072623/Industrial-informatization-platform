import { describe, it, expect } from 'vitest';
import { isValidConnection } from './ModelCanvas';
import type { RFNode, ModelNodeData } from '@/types/mlModule';

function makeNode(id: string, inputPorts: string[], outputPorts: string[]): RFNode {
  const data: ModelNodeData = {
    moduleType: 'Test',
    moduleName: 'Test',
    displayName: 'Test',
    parameters: {},
    inputPorts: inputPorts.map((name) => ({ name, type: 'tensor' })),
    outputPorts: outputPorts.map((name) => ({ name, type: 'tensor' })),
  };
  return {
    id,
    position: { x: 0, y: 0 },
    type: 'module',
    data: data as unknown as Record<string, unknown>,
  };
}

describe('isValidConnection', () => {
  it('从 source handle（输出端口）出发 → 允许', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'n1',
      sourceHandle: 'out',
      target: 'n2',
      targetHandle: 'in',
    });
    expect(result).toBe(true);
  });

  it('从 target handle（输入端口）出发 → 拒绝', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'n1',
      sourceHandle: 'in',
      target: 'n2',
      targetHandle: 'out',
    });
    expect(result).toBe(false);
  });

  it('sourceHandle 不存在于节点端口列表 → 拒绝', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'n1',
      sourceHandle: 'nonexistent',
      target: 'n2',
      targetHandle: 'in',
    });
    expect(result).toBe(false);
  });

  it('sourceHandle 为 null → 允许（由其他校验处理）', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'n1',
      sourceHandle: null,
      target: 'n2',
      targetHandle: 'in',
    });
    expect(result).toBe(true);
  });

  it('source 节点不存在 → 允许（由其他校验处理）', () => {
    const nodes = [makeNode('n1', ['in'], ['out'])];
    const result = isValidConnection(nodes, {
      source: 'missing',
      sourceHandle: 'out',
      target: 'n2',
      targetHandle: 'in',
    } as const);
    expect(result).toBe(true);
  });

  it('多输出端口时只匹配 outputPorts', () => {
    const nodes = [makeNode('n1', ['a', 'b'], ['x', 'y'])];
    expect(isValidConnection(nodes, { source: 'n1', sourceHandle: 'x', target: 'n2', targetHandle: 'a' })).toBe(true);
    expect(isValidConnection(nodes, { source: 'n1', sourceHandle: 'y', target: 'n2', targetHandle: 'a' })).toBe(true);
    expect(isValidConnection(nodes, { source: 'n1', sourceHandle: 'a', target: 'n2', targetHandle: 'x' })).toBe(false);
    expect(isValidConnection(nodes, { source: 'n1', sourceHandle: 'b', target: 'n2', targetHandle: 'x' })).toBe(false);
  });
});
