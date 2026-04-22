/**
 * 模块库组件
 *
 * 功能：
 * 1. 按分类展示所有可用模块（可折叠的手风琴）
 * 2. 搜索模块（实时过滤）
 * 3. 拖拽模块到画布（drag start 事件）
 * 4. 显示模块参数预览（tooltip）
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Layers,
  Network,
  GitMerge,
  Target,
  Puzzle,
  Search,
  ChevronDown,
  ChevronRight,
  Box,
  Square,
  Zap,
  GitBranch,
  Pyramid,
  Crosshair,
  Minimize,
  Shrink,
  Eye,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/utils/cn';
import { mlModuleApi } from '@/services/api';
import { useToast } from '@/hooks/use-toast';
import type { ModuleDefinition, ModuleCategory, CanvasMode } from '@/types/mlModule';

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
  Eye,
};

// 分类配置（与新后端对齐）
const CATEGORIES: Array<{ key: ModuleCategory; label: string; icon: string }> = [
  { key: 'atomic', label: '原子层', icon: 'Layers' },
  { key: 'backbone', label: '骨干网络', icon: 'Network' },
  { key: 'neck', label: '颈部网络', icon: 'GitMerge' },
  { key: 'head', label: '检测头', icon: 'Target' },
  { key: 'attention', label: '注意力', icon: 'Eye' },
  { key: 'custom', label: '自定义模块', icon: 'Puzzle' },
];

interface ModuleLibraryProps {
  /** 拖拽开始回调 */
  onModuleDragStart: (module: ModuleDefinition) => void;
  /** 点击模块回调（可选） */
  onModuleClick?: (module: ModuleDefinition) => void;
  /** 画布模式 */
  mode?: CanvasMode;
  /** 自定义类名 */
  className?: string;
}

/**
 * 模块库组件
 *
 * 显示可拖拽的神经网络模块列表
 */
export function ModuleLibrary({
  onModuleDragStart,
  onModuleClick,
  mode = 'architecture',
  className
}: ModuleLibraryProps) {
  const [modules, setModules] = useState<ModuleDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<ModuleCategory>>(
    new Set(['atomic', 'backbone']) // 默认展开原子层和骨干网络
  );
  const { toast } = useToast();

  // 加载模块列表
  useEffect(() => {
    loadModules();
  }, []);

  const loadModules = useCallback(async () => {
    try {
      setLoading(true);
      const response = await mlModuleApi.getModules({ search: searchQuery || undefined });
      if (response.data.success && response.data.data) {
        setModules(response.data.data);
      }
    } catch (error) {
      console.error('加载模块失败:', error);
      toast({
        title: '加载失败',
        description: '无法加载模块列表，请稍后重试',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }, [searchQuery, toast]);

  // 搜索防抖
  useEffect(() => {
    const timer = setTimeout(() => {
      loadModules();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, loadModules]);

  // 切换分类展开/折叠
  const toggleCategory = (category: ModuleCategory) => {
    setExpandedCategories(prev => {
      const newSet = new Set(prev);
      if (newSet.has(category)) {
        newSet.delete(category);
      } else {
        newSet.add(category);
      }
      return newSet;
    });
  };

  // 处理拖拽开始
  const handleDragStart = (e: React.DragEvent, module: ModuleDefinition) => {
    e.dataTransfer.setData('application/reactflow', JSON.stringify(module));
    e.dataTransfer.effectAllowed = 'move';
    onModuleDragStart(module);
  };

  // 端口节点拖拽
  const handlePortDragStart = (e: React.DragEvent, portType: 'input_port' | 'output_port') => {
    e.dataTransfer.setData('application/reactflow', JSON.stringify({
      __portType: portType,
      display_name: portType === 'input_port' ? '输入端口' : '输出端口',
    }));
    e.dataTransfer.effectAllowed = 'move';
  };

  // 获取分类图标组件
  const getCategoryIcon = (iconName: string) => {
    const IconComponent = ICON_MAP[iconName] || Box;
    return <IconComponent className="h-4 w-4" />;
  };

  // 获取模块图标
  const getModuleIcon = (module: ModuleDefinition) => {
    const iconName = module.is_composite ? 'Network' : 'Layers';
    const IconComponent = ICON_MAP[iconName] || Box;
    return <IconComponent className="h-4 w-4 text-muted-foreground" />;
  };

  // 按分类分组（前端本地分组）
  const groupedModules = useMemo(() => {
    const groups: Record<ModuleCategory, ModuleDefinition[]> = {
      atomic: [], backbone: [], neck: [], head: [], attention: [], custom: [],
    };

    const query = searchQuery.toLowerCase().trim();
    for (const m of modules) {
      if (query) {
        const match =
          m.type.toLowerCase().includes(query) ||
          m.display_name.toLowerCase().includes(query);
        if (!match) continue;
      }
      if (groups[m.category as ModuleCategory]) {
        groups[m.category as ModuleCategory].push(m);
      } else {
        // 未知分类归入 custom
        groups.custom.push(m);
      }
    }
    return groups;
  }, [modules, searchQuery]);

  // 渲染端口伪模块卡片
  const renderPortCard = (portType: 'input_port' | 'output_port', label: string, colorClass: string) => (
    <div
      key={portType}
      draggable
      onDragStart={(e) => handlePortDragStart(e, portType)}
      className={cn(
        'flex items-center gap-3 p-3 rounded-lg border cursor-move',
        'bg-card hover:bg-accent hover:border-primary/50',
        'transition-all duration-200',
        'active:cursor-grabbing'
      )}
    >
      <div className={cn('flex-shrink-0 w-8 h-8 rounded-md flex items-center justify-center', colorClass)}>
        <span className="text-xs font-bold text-white">{portType === 'input_port' ? 'IN' : 'OUT'}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{label}</div>
        <div className="text-xs text-muted-foreground truncate">{portType === 'input_port' ? 'InputPort' : 'OutputPort'}</div>
      </div>
    </div>
  );

  // 渲染模块卡片
  const renderModuleCard = (module: ModuleDefinition) => (
    <TooltipProvider key={module.id} delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            draggable
            onDragStart={(e) => handleDragStart(e, module)}
            onClick={() => onModuleClick?.(module)}
            className={cn(
              'flex items-center gap-3 p-3 rounded-lg border cursor-move',
              'bg-card hover:bg-accent hover:border-primary/50',
              'transition-all duration-200',
              'active:cursor-grabbing',
              onModuleClick && 'cursor-pointer'
            )}
          >
            <div className="flex-shrink-0 w-8 h-8 rounded-md bg-muted flex items-center justify-center">
              {getModuleIcon(module)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">
                {module.display_name}
              </div>
              <div className="text-xs text-muted-foreground truncate">
                {module.type}
              </div>
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="right" className="max-w-xs">
          <div className="space-y-1">
            <p className="font-medium">{module.display_name}</p>
            <p className="text-xs text-muted-foreground">{module.type}</p>
            <p className="text-xs text-muted-foreground">
              分类: {CATEGORIES.find(c => c.key === module.category)?.label || module.category}
            </p>
            <p className="text-xs text-muted-foreground">
              类型: {module.is_composite ? '复合模块' : '原子层'}
            </p>
            {module.params_schema.length > 0 && (
              <p className="text-xs text-muted-foreground">
                参数: {module.params_schema.map(p => p.name).join(', ')}
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );

  // 计算总数
  const totalCount = useMemo(() => {
    return Object.values(groupedModules).reduce((sum, arr) => sum + arr.length, 0);
  }, [groupedModules]);

  return (
    <div className={cn('flex flex-col h-full bg-card border-r', className)}>
      {/* 标题栏 */}
      <div className="p-4 border-b">
        <h2 className="text-lg font-semibold mb-3">模块库</h2>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索模块..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* 模块列表 */}
      <ScrollArea className="flex-1">
        <div className="p-3 space-y-2">
          {/* Module 模式：顶部显示端口节点 */}
          {mode === 'module' && (
            <div className="space-y-1 pb-2 border-b">
              <div className="text-xs font-medium text-muted-foreground px-2 py-1">端口节点</div>
              {renderPortCard('input_port', '输入端口', 'bg-blue-500')}
              {renderPortCard('output_port', '输出端口', 'bg-green-500')}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : (
            CATEGORIES.map((category) => {
              const categoryModules = groupedModules[category.key] || [];
              if (categoryModules.length === 0) return null;

              const isExpanded = expandedCategories.has(category.key);

              return (
                <div key={category.key} className="space-y-1">
                  {/* 分类标题 */}
                  <button
                    onClick={() => toggleCategory(category.key)}
                    className={cn(
                      'w-full flex items-center gap-2 px-2 py-2 rounded-md',
                      'text-sm font-medium text-muted-foreground',
                      'hover:bg-accent hover:text-accent-foreground',
                      'transition-colors'
                    )}
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                    {getCategoryIcon(category.icon)}
                    <span className="flex-1 text-left">{category.label}</span>
                    <span className="text-xs text-muted-foreground">
                      {categoryModules.length}
                    </span>
                  </button>

                  {/* 模块列表 */}
                  {isExpanded && (
                    <div className="pl-6 space-y-1">
                      {categoryModules.map(renderModuleCard)}
                    </div>
                  )}
                </div>
              );
            })
          )}

          {/* 搜索结果为空 */}
          {!loading && totalCount === 0 && (
            <div className="text-center py-8 text-muted-foreground">
              未找到匹配的模块
            </div>
          )}
        </div>
      </ScrollArea>

      {/* 底部提示 */}
      <div className="p-3 border-t text-xs text-muted-foreground">
        <p>拖拽模块到画布以添加节点 · 共 {totalCount} 个</p>
      </div>
    </div>
  );
}

export default ModuleLibrary;
