/**
 * 输入/输出端口节点
 *
 * Module 编辑模式下使用，作为子网络的对外接口。
 * - InputPortNode：只有输出 Handle（右侧），对应 proxy_inputs
 * - OutputPortNode：只有输入 Handle（左侧），对应 proxy_outputs
 */
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { ModelNodeData } from '@/types/mlModule';

const NODE_WIDTH = 120;
const NODE_HEIGHT = 40;

function getPortName(data: ModelNodeData): string {
  const params = data.parameters as Record<string, unknown> | undefined;
  return (params?.name as string) || (data.moduleName as string) || 'port';
}

/**
 * 输入端口节点（对外提供输入）
 *
 * 有一个输出 Handle 在右侧。
 */
export function InputPortNode(props: NodeProps) {
  const data = props.data as unknown as ModelNodeData;
  const name = getPortName(data);

  return (
    <div
      className="rounded-md border border-blue-200 bg-blue-50 shadow-sm flex items-center justify-center"
      style={{ width: NODE_WIDTH, height: NODE_HEIGHT }}
    >
      <span className="text-xs font-medium text-blue-700 truncate px-2">{name}</span>
      <Handle
        type="source"
        position={Position.Right}
        id="out"
        className="!w-3 !h-3 !bg-blue-400 !border-blue-500"
        style={{ right: -6 }}
      />
    </div>
  );
}

/**
 * 输出端口节点（对外提供输出）
 *
 * 有一个输入 Handle 在左侧。
 */
export function OutputPortNode(props: NodeProps) {
  const data = props.data as unknown as ModelNodeData;
  const name = getPortName(data);

  return (
    <div
      className="rounded-md border border-green-200 bg-green-50 shadow-sm flex items-center justify-center"
      style={{ width: NODE_WIDTH, height: NODE_HEIGHT }}
    >
      <Handle
        type="target"
        position={Position.Left}
        id="in"
        className="!w-3 !h-3 !bg-green-400 !border-green-500"
        style={{ left: -6 }}
      />
      <span className="text-xs font-medium text-green-700 truncate px-2">{name}</span>
    </div>
  );
}

export default { InputPortNode, OutputPortNode };
