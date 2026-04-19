/**
 * 子原子节点组件（用于复合节点展开态内部）
 *
 * 只读缩略视图，不可交互：
 * - 无 onClick / onDoubleClick / onMouseDown
 * - 端口用普通 div 圆点模拟，非 React Flow Handle
 */
import type { SubNode } from '@/types/mlModule';

interface ChildAtomicNodeProps {
  subNode: SubNode;
}

const NODE_WIDTH = 100;
const NODE_HEIGHT = 60;

export default function ChildAtomicNode({ subNode }: ChildAtomicNodeProps) {
  return (
    <div
      className="absolute rounded border bg-card shadow-sm flex flex-col items-center justify-center gap-0.5 select-none pointer-events-none"
      style={{
        left: subNode.position.x,
        top: subNode.position.y,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
      }}
      data-testid={`child-node-${subNode.id}`}
    >
      {/* 模拟输入端口 */}
      <div className="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-blue-500" />
      {/* 模拟输出端口 */}
      <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2 w-1.5 h-1.5 rounded-full bg-green-500" />

      <span className="text-[10px] font-semibold truncate max-w-[90px] px-1">
        {subNode.type}
      </span>
      <span className="text-[8px] text-muted-foreground truncate max-w-[90px] px-1">
        {subNode.id}
      </span>
    </div>
  );
}
