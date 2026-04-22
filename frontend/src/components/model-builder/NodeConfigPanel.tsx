/**
 * 节点参数配置面板（右侧抽屉）
 *
 * 根据新 params_schema 数组动态生成参数表单。
 * 支持类型: int, float, bool, string, int[], float[], tuple[...]
 * 未知类型降级为 JSON 文本输入，绝不 throw。
 */
import { useState, useEffect, useCallback } from 'react';
import { X, Info, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/utils/cn';
import { useToast } from '@/hooks/use-toast';
import type { RFNode, ModuleDefinitionDetail, ParamSchema } from '@/types/mlModule';

interface NodeConfigPanelProps {
  node: RFNode | null;
  moduleDetails: ModuleDefinitionDetail | null;
  onParamChange: (nodeId: string, params: Record<string, unknown>) => void;
  onClose: () => void;
  className?: string;
}

/** Port 节点（InputPort / OutputPort）精简参数表单 */
function PortConfigForm({
  node,
  onParamChange,
  onClose,
  className,
}: {
  node: RFNode;
  onParamChange: (nodeId: string, params: Record<string, unknown>) => void;
  onClose: () => void;
  className?: string;
}) {
  const [name, setName] = useState('');
  const { toast } = useToast();

  useEffect(() => {
    const params = (node.data.parameters as Record<string, unknown>) || {};
    setName(String(params.name ?? ''));
  }, [node.id]);

  const handleApply = useCallback(() => {
    onParamChange(node.id, { name });
    toast({ title: '参数已更新', description: '端口名称已保存' });
  }, [node.id, name, onParamChange, toast]);

  const label = node.type === 'input_port' ? '输入端口' : '输出端口';

  return (
    <div className={cn('flex flex-col h-full bg-card border-l w-[320px]', className)}>
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h2 className="text-lg font-semibold">参数配置</h2>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-sm font-medium">端口名称</Label>
            <Input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={node.type === 'input_port' ? 'x' : 'out'}
            />
          </div>
        </div>
      </ScrollArea>

      <div className="p-4 border-t space-y-2">
        <Button className="w-full" onClick={handleApply}>应用更改</Button>
        <Button variant="outline" className="w-full" onClick={onClose}>取消</Button>
      </div>
    </div>
  );
}

function extractDefaults(paramsSchema: ParamSchema[]): Record<string, unknown> {
  const d: Record<string, unknown> = {};
  for (const p of paramsSchema) {
    if (p.default !== undefined) d[p.name] = p.default;
  }
  return d;
}

/** 判断是否为数组/元组类型 */
function isArrayLikeType(type: string): boolean {
  return type.includes('[]') || type.startsWith('tuple') || type.startsWith('list');
}

/** 将值序列化为可编辑的字符串 */
function serializeValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

/** 反序列化用户输入 */
function deserializeValue(raw: string): unknown {
  const trimmed = raw.trim();
  if (trimmed === '') return '';
  if (trimmed === 'true') return true;
  if (trimmed === 'false') return false;
  if (/^-?\d+$/.test(trimmed)) return parseInt(trimmed, 10);
  if (/^-?\d+\.\d+$/.test(trimmed)) return parseFloat(trimmed);
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

export function NodeConfigPanel({
  node,
  moduleDetails,
  onParamChange,
  onClose,
  className,
}: NodeConfigPanelProps) {
  const [localParams, setLocalParams] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const { toast } = useToast();

  // 节点或模块详情变化时，合并默认值 + 当前值
  useEffect(() => {
    if (node && moduleDetails) {
      const defaults = extractDefaults(moduleDetails.params_schema);
      const current = ((node.data.parameters as Record<string, unknown>) || {}) as Record<string, unknown>;
      const merged = { ...defaults, ...current };
      setLocalParams(merged);
      setErrors({});
    }
  }, [node?.id, moduleDetails?.type]);

  const paramsSchema = moduleDetails?.params_schema || [];

  const getParamConfig = useCallback(
    (name: string): ParamSchema | undefined => paramsSchema.find((p) => p.name === name),
    [paramsSchema]
  );

  const validateParam = useCallback(
    (name: string, value: unknown): string | null => {
      const config = getParamConfig(name);
      if (!config) return null;
      const t = config.type;
      if ((t === 'int' || t === 'float') && !isArrayLikeType(t)) {
        const n = Number(value);
        if (isNaN(n)) return '请输入有效的数字';
        if (config.min !== undefined && n < config.min) return `最小值为 ${config.min}`;
        if (config.max !== undefined && n > config.max) return `最大值为 ${config.max}`;
      }
      if (isArrayLikeType(t) && value !== undefined && value !== '') {
        if (!Array.isArray(value)) return '必须是数组格式，例如 [1, 2, 3]';
      }
      return null;
    },
    [getParamConfig]
  );

  const handleParamChange = useCallback(
    (name: string, value: unknown) => {
      setLocalParams((prev) => ({ ...prev, [name]: value }));
      setErrors((prev) => ({ ...prev, [name]: validateParam(name, value) || '' }));
    },
    [validateParam]
  );

  const handleApply = useCallback(() => {
    if (!node) return;
    const newErrors: Record<string, string> = {};
    for (const key of Object.keys(localParams)) {
      const err = validateParam(key, localParams[key]);
      if (err) newErrors[key] = err;
    }
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      toast({ title: '参数验证失败', description: '请检查并修正参数值', variant: 'destructive' });
      return;
    }
    onParamChange(node.id, localParams);
    toast({ title: '参数已更新', description: '节点参数已成功保存' });
  }, [node, localParams, validateParam, onParamChange, toast]);

  const handleReset = useCallback(() => {
    if (moduleDetails) {
      const defaults = extractDefaults(moduleDetails.params_schema);
      setLocalParams(defaults);
      setErrors({});
      toast({ title: '已重置', description: '参数已恢复为默认值' });
    }
  }, [moduleDetails, toast]);

  // ============ 渲染单个参数字段 ============
  const renderParamField = useCallback(
    (param: ParamSchema) => {
      const rawValue = localParams[param.name];
      const error = errors[param.name];
      const label = param.name;
      const desc = param.description;
      const t = param.type;

      // --- bool ---
      if (t === 'bool' || t === 'boolean') {
        return (
          <div key={param.name} className="flex items-center justify-between py-2">
            <div className="space-y-0.5">
              <Label className="text-sm font-medium">{label}</Label>
              {desc && <p className="text-xs text-muted-foreground">{desc}</p>}
            </div>
            <Switch
              checked={Boolean(rawValue)}
              onCheckedChange={(v) => handleParamChange(param.name, v)}
            />
          </div>
        );
      }

      // --- int / float (标量) ---
      if ((t === 'int' || t === 'float') && !isArrayLikeType(t)) {
        const numValue = Number(rawValue ?? param.default ?? 0);
        const hasRange = param.min !== undefined && param.max !== undefined;

        return (
          <div key={param.name} className="space-y-2 py-2">
            <div className="flex items-center gap-2">
              <Label className="text-sm font-medium">{label}</Label>
              {desc && (
                <TooltipProvider delayDuration={300}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent><p className="max-w-xs">{desc}</p></TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
            {hasRange && (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono bg-muted px-2 py-0.5 rounded">{numValue}</span>
                </div>
                <Slider
                  value={[numValue]}
                  min={param.min}
                  max={param.max}
                  step={t === 'int' ? 1 : 0.1}
                  onValueChange={([v]) => handleParamChange(param.name, v)}
                />
              </>
            )}
            <Input
              type="number"
              value={typeof rawValue === 'number' ? rawValue : (param.default as number) ?? ''}
              onChange={(e) =>
                handleParamChange(
                  param.name,
                  t === 'int' ? parseInt(e.target.value) || 0 : parseFloat(e.target.value) || 0
                )
              }
              min={param.min}
              max={param.max}
              className={cn(error && 'border-destructive')}
            />
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
        );
      }

      // --- int[] / float[] / tuple[...] ---
      if (isArrayLikeType(t)) {
        const display = serializeValue(rawValue ?? param.default ?? []);
        return (
          <div key={param.name} className="space-y-2 py-2">
            <div className="flex items-center gap-2">
              <Label className="text-sm font-medium">{label}</Label>
              {desc && (
                <TooltipProvider delayDuration={300}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent><p className="max-w-xs">{desc}</p></TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
            <Input
              type="text"
              value={display}
              placeholder="[1, 2, 3]"
              onChange={(e) => {
                const parsed = deserializeValue(e.target.value);
                handleParamChange(param.name, parsed);
              }}
              className={cn(error && 'border-destructive', 'font-mono text-xs')}
            />
            <p className="text-xs text-muted-foreground">JSON 数组格式，例如 [512, 256, 128]</p>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
        );
      }

      // --- string (默认兜底) ---
      return (
        <div key={param.name} className="space-y-2 py-2">
          <div className="flex items-center gap-2">
            <Label className="text-sm font-medium">{label}</Label>
            {desc && (
              <TooltipProvider delayDuration={300}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="h-3.5 w-3.5 text-muted-foreground cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent><p className="max-w-xs">{desc}</p></TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
          <Input
            type="text"
            value={String(rawValue ?? param.default ?? '')}
            onChange={(e) => handleParamChange(param.name, e.target.value)}
            className={cn(error && 'border-destructive')}
          />
          {error && <p className="text-xs text-destructive">{error}</p>}
        </div>
      );
    },
    [localParams, errors, handleParamChange]
  );

  // 空状态
  if (!node) {
    return (
      <div className={cn('flex flex-col h-full bg-card border-l', className)}>
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold">参数配置</h2>
        </div>
        <div className="flex-1 flex items-center justify-center text-muted-foreground">
          <p>双击节点或点击节点以编辑参数</p>
        </div>
      </div>
    );
  }

  // Port 节点走精简渲染
  if (node.type === 'input_port' || node.type === 'output_port') {
    return (
      <PortConfigForm
        node={node}
        onParamChange={onParamChange}
        onClose={onClose}
        className={className}
      />
    );
  }

  const displayName = String(node.data.displayName || node.data.moduleName || '');

  return (
    <div className={cn('flex flex-col h-full bg-card border-l w-[320px]', className)}>
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h2 className="text-lg font-semibold">参数配置</h2>
          <p className="text-xs text-muted-foreground">{displayName}</p>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={handleReset} title="重置为默认值">
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {paramsSchema.length > 0 ? (
            paramsSchema.map((param) => (
              <div key={param.name}>
                {renderParamField(param)}
                <Separator className="mt-2" />
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>此模块没有可配置参数</p>
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="p-4 border-t space-y-2">
        <Button className="w-full" onClick={handleApply}>应用更改</Button>
        <Button variant="outline" className="w-full" onClick={onClose}>取消</Button>
      </div>
    </div>
  );
}

export default NodeConfigPanel;
