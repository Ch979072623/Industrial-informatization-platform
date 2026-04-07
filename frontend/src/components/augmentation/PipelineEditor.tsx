/**
 * 流水线编排组件
 * 
 * 支持拖拽排序、参数配置、删除等操作
 */
import React, { useState, useCallback, useEffect } from 'react';
import {
  GripVertical,
  ChevronDown,
  ChevronUp,
  Trash2,
  ArrowUp,
  ArrowDown,
  AlertCircle,
  Settings,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import type {
  AugmentationOperation,
  AugmentationOperationDefinition,
} from '@/types/augmentation';

interface PipelineEditorProps {
  pipeline: AugmentationOperation[];
  operations: AugmentationOperationDefinition[];
  onPipelineChange: (pipeline: AugmentationOperation[]) => void;
  disabled?: boolean;
}

// 获取操作的参数定义
const getOperationDefinition = (
  operations: AugmentationOperationDefinition[],
  operationType: string
): AugmentationOperationDefinition | undefined => {
  return operations.find((op) => op.operation_type === operationType);
};

// 参数输入组件
interface ParameterInputProps {
  param: {
    name: string;
    type: string;
    default: unknown;
    min?: number;
    max?: number;
    step?: number;
  };
  value: unknown;
  onChange: (value: unknown) => void;
}

const ParameterInput: React.FC<ParameterInputProps> = ({
  param,
  value,
  onChange,
}) => {
  const currentValue = value !== undefined ? value : param.default;

  switch (param.type) {
    case 'probability':
      const probValue = (currentValue as number) * 100;
      return (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-xs">概率</Label>
            <span className="text-xs text-gray-500">{probValue.toFixed(0)}%</span>
          </div>
          <div className="flex items-center gap-2">
            <Slider
              value={[probValue]}
              min={0}
              max={100}
              step={1}
              onValueChange={([v]) => onChange(v / 100)}
            />
            <Input
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={currentValue as number}
              onChange={(e) => onChange(parseFloat(e.target.value))}
              className="w-20 text-xs"
            />
          </div>
        </div>
      );

    case 'range':
      const rangeValue = currentValue as [number, number];
      return (
        <div className="space-y-2">
          <Label className="text-xs">范围</Label>
          <div className="flex items-center gap-2">
            <Input
              type="number"
              min={param.min}
              max={param.max}
              step={param.step}
              value={rangeValue[0]}
              onChange={(e) =>
                onChange([parseFloat(e.target.value), rangeValue[1]])
              }
              className="w-20 text-xs"
            />
            <span className="text-gray-400">-</span>
            <Input
              type="number"
              min={param.min}
              max={param.max}
              step={param.step}
              value={rangeValue[1]}
              onChange={(e) =>
                onChange([rangeValue[0], parseFloat(e.target.value)])
              }
              className="w-20 text-xs"
            />
          </div>
        </div>
      );

    case 'float':
      return (
        <div className="space-y-1">
          <Label className="text-xs capitalize">{param.name}</Label>
          <div className="flex items-center gap-2">
            <Slider
              value={[currentValue as number]}
              min={param.min}
              max={param.max}
              step={param.step || 0.1}
              onValueChange={([v]) => onChange(v)}
            />
            <Input
              type="number"
              min={param.min}
              max={param.max}
              step={param.step}
              value={currentValue as number}
              onChange={(e) => onChange(parseFloat(e.target.value))}
              className="w-20 text-xs"
            />
          </div>
        </div>
      );

    case 'int':
      return (
        <div className="space-y-1">
          <Label className="text-xs capitalize">{param.name}</Label>
          <div className="flex items-center gap-2">
            <Slider
              value={[currentValue as number]}
              min={param.min}
              max={param.max}
              step={param.step || 1}
              onValueChange={([v]) => onChange(Math.round(v))}
            />
            <Input
              type="number"
              min={param.min}
              max={param.max}
              step={param.step || 1}
              value={currentValue as number}
              onChange={(e) => onChange(parseInt(e.target.value))}
              className="w-20 text-xs"
            />
          </div>
        </div>
      );

    default:
      return null;
  }
};

export const PipelineEditor: React.FC<PipelineEditorProps> = ({
  pipeline,
  operations,
  onPipelineChange,
  disabled = false,
}) => {
  // console.log('[PipelineEditor] Component render, pipeline.length:', pipeline.length);
  
  const [expandedItemIds, setExpandedItemIds] = useState<Set<string>>(new Set());
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // 监听 pipeline 变化
  // useEffect(() => {
  //   console.log('[PipelineEditor] Pipeline effect:', pipeline);
  // }, [pipeline]);

  // 切换展开状态
  const toggleExpand = (opId: string) => {
    setExpandedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(opId)) {
        next.delete(opId);
      } else {
        next.add(opId);
      }
      return next;
    });
  };

  // 更新操作
  const updateOperation = (index: number, updates: Partial<AugmentationOperation>) => {
    const newPipeline = [...pipeline];
    newPipeline[index] = { ...newPipeline[index], ...updates };
    onPipelineChange(newPipeline);
  };

  // 删除操作
  const removeOperation = (index: number) => {
    // console.log('[PipelineEditor] Removing operation at index:', index, 'current length:', pipeline.length);
    const newPipeline = pipeline
      .filter((_, i) => i !== index)
      .map((op, i) => ({ ...op, order: i }));
    // console.log('[PipelineEditor] Calling onPipelineChange with length:', newPipeline.length);
    // 如果删除后为空，重置拖拽状态
    if (newPipeline.length === 0) {
      setDragOverIndex(null);
    }
    onPipelineChange(newPipeline);
  };

  // 移动操作
  const moveOperation = (fromIndex: number, toIndex: number) => {
    if (toIndex < 0 || toIndex >= pipeline.length) return;
    const newPipeline = [...pipeline];
    const [moved] = newPipeline.splice(fromIndex, 1);
    newPipeline.splice(toIndex, 0, moved);
    // 更新顺序 - 创建新对象以保持不可变性
    onPipelineChange(newPipeline.map((op, i) => ({ ...op, order: i })));
  };

  // 拖拽处理
  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverIndex(index);
  };

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    setDragOverIndex(null);

    const dragData = e.dataTransfer.getData('text/plain');
    if (dragData) {
      const dragIndex = parseInt(dragData, 10);
      if (!isNaN(dragIndex) && dragIndex !== dropIndex) {
        moveOperation(dragIndex, dropIndex);
      }
    }
  };

  // 清空流水线
  const clearPipeline = () => {
    onPipelineChange([]);
    setExpandedItemIds(new Set());
    setDragOverIndex(null);
  };

  // 验证参数
  const validateOperation = (op: AugmentationOperation): string | null => {
    const definition = getOperationDefinition(operations, op.operation_type);
    if (!definition) return '未知操作类型';

    for (const param of definition.parameters) {
      const value = op[param.name as keyof AugmentationOperation];

      if (param.type === 'range' && Array.isArray(value)) {
        if (value[0] > value[1]) {
          return `${param.name} 的最小值不能大于最大值`;
        }
      }

      if (param.type === 'probability' && typeof value === 'number') {
        if (value < 0 || value > 1) {
          return '概率必须在 0-1 之间';
        }
      }
    }

    return null;
  };

  // 估算执行时间
  const estimatedTime = useCallback(() => {
    const baseTime = 0.1; // 每张图基础时间（秒）
    const operationTime = 0.05; // 每个操作时间（秒）
    return Math.round((baseTime + pipeline.length * operationTime) * 10) / 10;
  }, [pipeline]);

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 头部 */}
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h3 className="font-medium">增强流水线</h3>
          <p className="text-xs text-gray-500">
            {pipeline.length} 个操作 · 预计每张图 {estimatedTime()}s
          </p>
        </div>
        {pipeline.length > 0 && (
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="sm" disabled={disabled}>
                <Trash2 className="h-4 w-4 mr-1" />
                清空
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>确认清空流水线？</AlertDialogTitle>
                <AlertDialogDescription>
                  此操作将删除所有已配置的增强操作，无法撤销。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction onClick={clearPipeline} className="bg-red-600">
                  确认清空
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        )}
      </div>

      {/* 流水线列表 */}
      <ScrollArea className="flex-1 p-4">
        {pipeline.length === 0 ? (
          <div
            className={`flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-lg transition-colors ${
              dragOverIndex === 0
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200'
            }`}
            onDragOver={(e) => handleDragOver(e, 0)}
            onDrop={(e) => handleDrop(e, 0)}
            onDragLeave={() => setDragOverIndex(null)}
          >
            <Settings className="h-12 w-12 text-gray-300 mb-2" />
            <p className="text-sm text-gray-500">拖拽左侧操作到此处</p>
            <p className="text-xs text-gray-400">开始配置增强流水线</p>
          </div>
        ) : (
          <div className="space-y-2">
            {pipeline.map((operation, index) => {
              const definition = getOperationDefinition(
                operations,
                operation.operation_type
              );
              const isExpanded = operation.id ? expandedItemIds.has(operation.id) : false;
              const validationError = validateOperation(operation);

              return (
                <div
                  key={operation.id || `${operation.operation_type}-${index}`}
                  draggable={!disabled}
                  onDragStart={(e) => {
                    e.dataTransfer.setData('text/plain', index.toString());
                    e.dataTransfer.effectAllowed = 'move';
                  }}
                  onDragOver={(e) => handleDragOver(e, index)}
                  onDrop={(e) => handleDrop(e, index)}
                  onDragLeave={() => setDragOverIndex(null)}
                  className={`border rounded-lg transition-all ${
                    validationError
                      ? 'border-red-300 bg-red-50'
                      : dragOverIndex === index
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200'
                  } ${disabled ? 'opacity-50' : ''}`}
                >
                  {/* 头部 */}
                  <div className="flex items-center gap-2 p-3">
                    <div className="cursor-move">
                      <GripVertical className="h-4 w-4 text-gray-400" />
                    </div>

                    <span className="text-xs text-gray-400 w-6">{index + 1}</span>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm truncate">
                          {operation.name}
                        </span>
                        {validationError && (
                          <AlertCircle className="h-4 w-4 text-red-500" />
                        )}
                      </div>
                      <div className="text-xs text-gray-500">
                        概率: {(operation.probability * 100).toFixed(0)}%
                      </div>
                    </div>

                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        disabled={disabled}
                        onClick={() => moveOperation(index, index - 1)}
                      >
                        <ArrowUp className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        disabled={disabled}
                        onClick={() => moveOperation(index, index + 1)}
                      >
                        <ArrowDown className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => operation.id && toggleExpand(operation.id)}
                      >
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-red-500 hover:text-red-600"
                        disabled={disabled}
                        onClick={() => removeOperation(index)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {/* 展开的配置面板 */}
                  {isExpanded && definition && (
                    <div className="px-3 pb-3 border-t bg-gray-50">
                      {/* 启用开关 */}
                      <div className="flex items-center justify-between py-2">
                        <Label className="text-xs">启用此操作</Label>
                        <Switch
                          checked={operation.enabled}
                          onCheckedChange={(checked) =>
                            updateOperation(index, { enabled: checked })
                          }
                          disabled={disabled}
                        />
                      </div>

                      {/* 参数配置 */}
                      <div className="space-y-3">
                        {definition.parameters.map((param) => (
                          <ParameterInput
                            key={param.name}
                            param={param}
                            value={operation[param.name as keyof AugmentationOperation]}
                            onChange={(value) =>
                              updateOperation(index, { [param.name]: value })
                            }
                          />
                        ))}
                      </div>

                      {validationError && (
                        <div className="mt-3 p-2 bg-red-100 text-red-700 text-xs rounded">
                          {validationError}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {pipeline.length >= 20 && (
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-xs text-yellow-700">
                  流水线包含 {pipeline.length} 个操作，过多操作可能影响性能
                </p>
              </div>
            )}
          </div>
        )}
      </ScrollArea>
    </div>
  );
};

export default PipelineEditor;
