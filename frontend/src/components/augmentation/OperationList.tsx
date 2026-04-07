/**
 * 增强操作列表组件
 * 
 * 显示可拖拽的增强操作分类列表
 */
import React, { useState, useMemo } from 'react';
import { Search, ChevronDown, ChevronRight, GripVertical } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { CATEGORY_NAMES, CATEGORY_ICONS } from '@/types/augmentation';
import type { AugmentationOperationDefinition, AugmentationCategory } from '@/types/augmentation';

interface OperationListProps {
  operations: AugmentationOperationDefinition[];
  categories: { key: AugmentationCategory; name: string; icon: string }[];
  onDragStart: (operation: AugmentationOperationDefinition) => void;
}

// 图标映射
const iconComponents: Record<string, React.ReactNode> = {
  Move: <span className="text-blue-500">📐</span>,
  RotateCw: <span className="text-blue-500">🔄</span>,
  Crop: <span className="text-blue-500">✂️</span>,
  Maximize: <span className="text-blue-500">⬛</span>,
  FlipHorizontal: <span className="text-blue-500">↔️</span>,
  FlipVertical: <span className="text-blue-500">↕️</span>,
  Palette: <span className="text-orange-500">🎨</span>,
  Sun: <span className="text-orange-500">☀️</span>,
  Contrast: <span className="text-orange-500">◐</span>,
  BarChart: <span className="text-orange-500">📊</span>,
  BarChart2: <span className="text-orange-500">📈</span>,
  Zap: <span className="text-purple-500">⚡</span>,
  ZapOff: <span className="text-purple-500">🔇</span>,
  Blur: <span className="text-purple-500">💨</span>,
  Wind: <span className="text-purple-500">🌪️</span>,
  Sparkles: <span className="text-pink-500">✨</span>,
  Square: <span className="text-pink-500">⬜</span>,
  Code: <span className="text-gray-500">💻</span>,
};

export const OperationList: React.FC<OperationListProps> = ({
  operations,
  categories,
  onDragStart,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(
    () => new Set(categories.map((c) => c.key))
  );

  // 按分类过滤操作
  const groupedOperations = useMemo(() => {
    const filtered = operations.filter(
      (op) =>
        op.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        op.description.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const grouped: Record<string, AugmentationOperationDefinition[]> = {};
    categories.forEach((cat) => {
      grouped[cat.key] = filtered.filter((op) => op.category === cat.key);
    });

    return grouped;
  }, [operations, categories, searchQuery]);

  // 切换分类展开状态
  const toggleCategory = (key: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // 处理拖拽开始
  const handleDragStart = (
    e: React.DragEvent<HTMLDivElement>,
    operation: AugmentationOperationDefinition
  ) => {
    e.dataTransfer.effectAllowed = 'copy';
    e.dataTransfer.setData('application/json', JSON.stringify(operation));
    onDragStart(operation);
  };

  return (
    <div className="flex flex-col h-full bg-white border-r">
      {/* 搜索栏 */}
      <div className="p-4 border-b">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
          <Input
            placeholder="搜索增强操作..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* 操作列表 */}
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-2">
          {categories.map((category) => {
            const ops = groupedOperations[category.key] || [];
            if (ops.length === 0 && searchQuery) return null;

            const isExpanded = expandedCategories.has(category.key);

            return (
              <div key={category.key} className="border rounded-lg overflow-hidden">
                <button
                  onClick={() => toggleCategory(category.key)}
                  className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{iconComponents[category.icon]}</span>
                    <span className="font-medium text-sm">{category.name}</span>
                    <span className="text-xs text-gray-500">({ops.length})</span>
                  </div>
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-gray-500" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-gray-500" />
                  )}
                </button>

                {isExpanded && (
                  <div className="p-2 space-y-1">
                    {ops.length === 0 ? (
                      <div className="text-sm text-gray-400 text-center py-4">
                        暂无操作
                      </div>
                    ) : (
                      ops.map((operation) => (
                        <div
                          key={operation.operation_type}
                          draggable
                          onDragStart={(e) => handleDragStart(e, operation)}
                          className="flex items-center gap-2 p-2 rounded-md bg-white border hover:bg-blue-50 hover:border-blue-200 cursor-move transition-all group"
                        >
                          <GripVertical className="h-4 w-4 text-gray-300 group-hover:text-gray-500" />
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium truncate">
                              {operation.name}
                            </div>
                            <div className="text-xs text-gray-500 truncate">
                              {operation.description}
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </ScrollArea>

      {/* 底部提示 */}
      <div className="p-3 border-t bg-gray-50 text-xs text-gray-500 text-center">
        拖拽操作到右侧流水线
      </div>
    </div>
  );
};

export default OperationList;
