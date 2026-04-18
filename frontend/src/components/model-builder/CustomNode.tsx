/**
 * 自定义节点组件
 * 
 * 功能：
 * 1. 显示模块图标和名称
 * 2. 显示输入端口（左侧）和输出端口（右侧）
 * 3. 选中状态边框
 * 4. 参数摘要（小字）
 * 5. 双击打开参数配置
 */
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { 
  Box, 
  Layers, 
  Network, 
  GitMerge, 
  Target, 
  Puzzle,
  Square,
  Zap,
  GitBranch,
  Pyramid,
  Crosshair,
  Minimize,
  Shrink
} from 'lucide-react';
import { cn } from '@/utils/cn';
import type { PortDefinition } from '@/types/mlModule';

// 图标映射
const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Layers,
  Network,
  GitMerge,
  Target,
  Puzzle,
  Box,
  Square,
  Zap,
  GitBranch,
  Pyramid,
  Crosshair,
  Minimize,
  Shrink,
};

/** 节点数据结构 */
interface NodeData {
  moduleName: string;
  displayName: string;
  parameters: Record<string, unknown>;
  inputPorts: PortDefinition[];
  outputPorts: PortDefinition[];
  icon?: string;
}

/**
 * 自定义节点组件
 * 
 * React Flow 使用的自定义节点渲染组件
 */
function CustomNodeComponent({ 
  data,
  selected,
  dragging 
}: NodeProps) {
  const typedData = data as unknown as NodeData;
  const { 
    moduleName, 
    displayName, 
    parameters, 
    inputPorts, 
    outputPorts,
    icon
  } = typedData;

  // 获取图标组件
  const IconComponent = ICON_MAP[icon || 'Box'] || Box;

  // 格式化参数显示
  const formatParamValue = (value: unknown): string => {
    if (value === null || value === undefined) return '';
    if (typeof value === 'boolean') return value ? '是' : '否';
    if (Array.isArray(value)) return `[${value.join(', ')}]`;
    return String(value);
  };

  // 获取前3个参数用于显示
  const paramEntries = Object.entries(parameters || {}).slice(0, 3);

  return (
    <div
      className={cn(
        'relative min-w-[180px] max-w-[240px] bg-card rounded-lg shadow-sm',
        'border-2 transition-all duration-200',
        selected 
          ? 'border-primary shadow-md ring-2 ring-primary/20' 
          : 'border-border hover:border-primary/50',
        dragging && 'shadow-lg scale-105'
      )}
    >
      {/* 输入端口 */}
      {(inputPorts || []).map((port: PortDefinition, index: number) => {
        // 计算端口垂直位置
        const totalPorts = inputPorts.length;
        const spacing = totalPorts > 1 ? 100 / (totalPorts + 1) : 50;
        const top = spacing * (index + 1);
        
        return (
          <Handle
            key={`input-${port.name}`}
            type="target"
            position={Position.Left}
            id={port.name}
            style={{ 
              top: `${top}%`,
              width: 12,
              height: 12,
              background: '#3b82f6', // blue-500
              border: '2px solid white',
              left: -6,
            }}
          />
        );
      })}

      {/* 节点内容 */}
      <div className="p-3">
        {/* 头部：图标和名称 */}
        <div className="flex items-center gap-2 mb-2">
          <div className={cn(
            'w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0',
            selected ? 'bg-primary text-primary-foreground' : 'bg-muted'
          )}>
            <IconComponent className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold truncate">
              {displayName}
            </div>
            <div className="text-xs text-muted-foreground truncate">
              {moduleName}
            </div>
          </div>
        </div>

        {/* 参数摘要 */}
        {paramEntries.length > 0 && (
          <div className="border-t pt-2 mt-2 space-y-0.5">
            {paramEntries.map(([key, value]) => (
              <div 
                key={key}
                className="flex items-center justify-between text-xs"
              >
                <span className="text-muted-foreground truncate max-w-[80px]">
                  {key}:
                </span>
                <span className="font-mono truncate max-w-[100px]">
                  {formatParamValue(value)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 输出端口 */}
      {(outputPorts || []).map((port: PortDefinition, index: number) => {
        // 计算端口垂直位置
        const totalPorts = outputPorts.length;
        const spacing = totalPorts > 1 ? 100 / (totalPorts + 1) : 50;
        const top = spacing * (index + 1);
        
        return (
          <Handle
            key={`output-${port.name}`}
            type="source"
            position={Position.Right}
            id={port.name}
            style={{ 
              top: `${top}%`,
              width: 12,
              height: 12,
              background: '#22c55e', // green-500
              border: '2px solid white',
              right: -6,
            }}
          />
        );
      })}
    </div>
  );
}

// 使用 memo 优化渲染性能
export const CustomNode = memo(CustomNodeComponent);

export default CustomNode;
