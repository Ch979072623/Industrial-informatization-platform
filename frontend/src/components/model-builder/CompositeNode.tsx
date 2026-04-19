/**
 * 复合节点组件
 * 
 * 功能：
 * 1. 显示模块图标和名称
 * 2. 显示输入端口（左侧）和输出端口（右侧）
 * 3. 选中状态边框
 * 4. 折叠态：参数摘要 + Maximize2 图标
 * 5. 展开态：虚线边框容器 + 子画布（loading/error/success 三态）+ Minimize2 图标
 * 6. 双击标题栏切换折叠/展开
 */
import { useEffect, useMemo } from 'react';
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
import type { ModelNodeData, PortDefinition, SubNode, SubEdge, ModuleSchemaDetail } from '@/types/mlModule';
import ChildAtomicNode from './ChildAtomicNode';

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

const CHILD_NODE_WIDTH = 100;
const CHILD_NODE_HEIGHT = 60;

function computeBounds(subNodes: SubNode[]) {
  if (subNodes.length === 0) return { width: 200, height: 200 };
  const maxX = Math.max(...subNodes.map((n) => n.position.x));
  const maxY = Math.max(...subNodes.map((n) => n.position.y));
  return {
    width: maxX + CHILD_NODE_WIDTH + 20,
    height: maxY + CHILD_NODE_HEIGHT + 20,
  };
}

function SubEdgeLine({ edge, subNodes }: { edge: SubEdge; subNodes: SubNode[] }) {
  const source = subNodes.find((n) => n.id === edge.source);
  const target = subNodes.find((n) => n.id === edge.target);
  if (!source || !target) return null;

  const sx = source.position.x + CHILD_NODE_WIDTH;
  const sy = source.position.y + CHILD_NODE_HEIGHT / 2;
  const tx = target.position.x;
  const ty = target.position.y + CHILD_NODE_HEIGHT / 2;

  return (
    <path
      d={`M ${sx} ${sy} C ${sx + 40} ${sy}, ${tx - 40} ${ty}, ${tx} ${ty}`}
      stroke="#9ca3af"
      strokeWidth="1.5"
      fill="none"
    />
  );
}

function SubGraphView({ schema }: { schema: ModuleSchemaDetail }) {
  const raw_sub_nodes = schema.sub_nodes || [];
  const sub_edges = schema.sub_edges || [];

  // 横向化：把 Phase 4a schema 的纵向坐标 (x,y) 转置为 (y,x)
  // 原因：外部端口在左右两侧暗示横向数据流，但 schema 的 position 是纵向布局。
  // 纯前端转置，不改 schema 本身。
  const sub_nodes = useMemo(
    () =>
      raw_sub_nodes.map((n) => ({
        ...n,
        position: { x: n.position.y, y: n.position.x },
      })),
    [raw_sub_nodes]
  );

  const bounds = computeBounds(sub_nodes);

  return (
    <div
      className="relative"
      style={{ width: bounds.width, height: bounds.height }}
      data-testid="subgraph-view"
    >
      <svg
        className="absolute top-0 left-0 pointer-events-none"
        width={bounds.width}
        height={bounds.height}
      >
        {sub_edges.map((edge) => (
          <SubEdgeLine
            key={`${edge.source}-${edge.target}-${edge.source_port}-${edge.target_port}`}
            edge={edge}
            subNodes={sub_nodes}
          />
        ))}
      </svg>
      {sub_nodes.map((subNode) => (
        <ChildAtomicNode key={subNode.id} subNode={subNode} />
      ))}
    </div>
  );
}

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
  const getOrLoadModuleSchema = useModelBuilderStore((state) => state.getOrLoadModuleSchema);
  const clearModuleSchemaError = useModelBuilderStore((state) => state.clearModuleSchemaError);
  const moduleSchemas = useModelBuilderStore((state) => state.moduleSchemas);
  const moduleSchemaLoading = useModelBuilderStore((state) => state.moduleSchemaLoading);
  const moduleSchemaError = useModelBuilderStore((state) => state.moduleSchemaError);

  const isExpanded = data.collapsed === false;
  const moduleType = data.moduleType;

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

  // 展开时触发 schema 懒加载
  useEffect(() => {
    if (isExpanded && moduleType) {
      const state = useModelBuilderStore.getState();
      if (
        !state.moduleSchemas[moduleType] &&
        !state.moduleSchemaLoading[moduleType] &&
        !state.moduleSchemaError[moduleType]
      ) {
        state.getOrLoadModuleSchema(moduleType).then((schema) => {
          if (schema) {
            state.markSubLoaded(id);
          }
        });
      }
    }
  }, [isExpanded, moduleType, id]);

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

      {/* 展开态：子画布区域 */}
      {isExpanded && (
        <div
          className="flex-1 flex flex-col overflow-auto"
          style={{ maxHeight: 400 }}
          data-testid="composite-children"
        >
          {(() => {
            const schema = moduleSchemas[moduleType];
            const loading = moduleSchemaLoading[moduleType];
            const error = moduleSchemaError[moduleType];

            if (loading) {
              return (
                <div
                  className="flex-1 flex items-center justify-center py-4"
                  data-testid="composite-loading"
                >
                  <div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full" />
                  <span className="ml-2 text-sm text-muted-foreground">加载中...</span>
                </div>
              );
            }

            if (error) {
              return (
                <div
                  className="flex-1 flex flex-col items-center justify-center py-4 gap-2"
                  data-testid="composite-error"
                >
                  <span className="text-sm text-destructive">加载失败：{error}</span>
                  <button
                    type="button"
                    className="text-xs px-2 py-1 rounded border hover:bg-muted"
                    onClick={() => {
                      clearModuleSchemaError(moduleType);
                      getOrLoadModuleSchema(moduleType);
                    }}
                  >
                    重试
                  </button>
                </div>
              );
            }

            if (!schema || !schema.sub_nodes) {
              return (
                <div
                  className="flex-1 flex items-center justify-center py-4 text-sm text-muted-foreground"
                  data-testid="composite-empty"
                >
                  暂无子节点信息
                </div>
              );
            }

            return <SubGraphView schema={schema} />;
          })()}
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
