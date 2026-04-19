/**
 * 复合节点组件
 * 
 * 功能：
 * 1. 显示模块图标和名称
 * 2. 显示输入端口（左侧）和输出端口（右侧）
 * 3. 选中状态边框
 * 4. 折叠态：参数摘要 + Maximize2 图标
 * 5. 展开态：虚线边框容器 + 占位区域 + Minimize2 图标
 * 6. 双击标题栏切换折叠/展开
 */
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
  Shrink,
  Maximize2,
  Minimize2,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { useModelBuilderStore } from '@/stores/modelBuilderStore';
import type { ModelNodeData, PortDefinition } from '@/types/mlModule';

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

export default function CompositeNode({ 
  id,
  data: _data,
  selected,
  dragging 
}: NodeProps) {
  const data = _data as unknown as ModelNodeData;
  const { 
    moduleName, 
    displayName, 
    parameters, 
    inputPorts, 
    outputPorts,
    icon
  } = data;

  const toggleCollapse = useModelBuilderStore((state) => state.toggleCollapse);
  const isExpanded = data.collapsed === false;

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
        'relative rounded-lg shadow-sm transition-all duration-200',
        isExpanded
          ? 'w-[280px] min-h-[200px] bg-muted/30 border-2 border-dashed border-primary/40 flex flex-col'
          : 'min-w-[180px] max-w-[240px] bg-card border-2',
        selected 
          ? 'border-primary shadow-md ring-2 ring-primary/20' 
          : isExpanded
            ? 'border-primary/30 hover:border-primary/60'
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

      {/* 标题栏：双击此区域触发折叠切换 */}
      <div
        className={cn(
          'flex items-center gap-2 select-none',
          isExpanded ? 'p-3' : 'p-3 pb-0'
        )}
        onDoubleClick={(e) => {
          e.stopPropagation();
          toggleCollapse(id);
        }}
        data-testid="composite-header"
      >
        <div className={cn(
          'w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0',
          selected ? 'bg-primary text-primary-foreground' : 'bg-muted'
        )}>
          <IconComponent className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0 pr-6">
          <div className="text-sm font-semibold truncate">
            {displayName}
          </div>
          <div className="text-xs text-muted-foreground truncate">
            {moduleName}
          </div>
        </div>

        {/* 右上角：折叠图标根据状态切换 */}
        <div 
          className="absolute top-2 right-2 text-muted-foreground/60"
          data-testid="composite-collapse-indicator"
        >
          {isExpanded 
            ? <Minimize2 className="h-4 w-4" />
            : <Maximize2 className="h-4 w-4" />
          }
        </div>
      </div>

      {/* 折叠态：参数摘要 */}
      {!isExpanded && paramEntries.length > 0 && (
        <div className="px-3 pb-3 pt-2">
          <div className="border-t pt-2 space-y-0.5">
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
        </div>
      )}

      {/* 展开态：占位区域 */}
      {isExpanded && (
        <div 
          className="flex-1 flex items-center justify-center px-3 pb-3"
          data-testid="composite-expanded-placeholder"
        >
          <p className="text-sm text-muted-foreground">
            子节点将在此渲染（A-3c）
          </p>
        </div>
      )}

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
