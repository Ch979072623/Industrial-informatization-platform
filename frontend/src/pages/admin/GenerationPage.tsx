/**
 * 数据生成页面
 * 
 * 提供数据生成功能的配置、预览和执行
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { generationApi } from '@/services/api';
// import { useAuthStore } from '@/stores/authStore';
import type { 
  GeneratorInfo, 
  GenerationJob,
  GenerationPreviewResponse,
  DefectMigrationConfig,
  StableDiffusionAPIConfig,
  ColorMatchMode,
  PlacementStrategyType,
} from '@/types/generation';

// UI 组件
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';

// 图标
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Image as ImageIcon, 
  Settings, 
  Wand2,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Eye,
  Trash2,
  Database,
  Cpu,
  Sparkles,
  Layers,
  X
} from 'lucide-react';

// ==================== 类型定义 ====================

interface GeneratorCardProps {
  generator: GeneratorInfo;
  isSelected: boolean;
  onSelect: () => void;
}

// ==================== 生成器卡片组件 ====================

const GeneratorCard = ({ generator, isSelected, onSelect }: GeneratorCardProps) => {
  const getIcon = () => {
    switch (generator.name) {
      case 'defect_migration':
        return <Layers className="h-8 w-8" />;
      case 'stable_diffusion_api':
        return <Sparkles className="h-8 w-8" />;
      default:
        return <Cpu className="h-8 w-8" />;
    }
  };

  const getBadgeColor = () => {
    if (generator.is_builtin) return 'bg-green-100 text-green-800';
    return 'bg-blue-100 text-blue-800';
  };

  return (
    <Card 
      className={`cursor-pointer transition-all hover:shadow-md ${
        isSelected ? 'ring-2 ring-primary border-primary' : ''
      }`}
      onClick={onSelect}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          <div className={`p-3 rounded-lg ${isSelected ? 'bg-primary/10' : 'bg-muted'}`}>
            {getIcon()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold truncate">{generator.name}</h3>
              <Badge variant="secondary" className={getBadgeColor()}>
                {generator.is_builtin ? '内置' : '外部'}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground line-clamp-2">
              {generator.description}
            </p>
            <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
              <span>支持: {generator.supported_formats.join(', ')}</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// ==================== 缺陷迁移配置表单 ====================

interface DatasetOption {
  id: string;
  name: string;
  image_count: number;
  annotated_count: number;
}

const DefectMigrationConfigForm = ({ 
  config, 
  onChange,
  sourceDatasets,
  baseDatasets
}: { 
  config: Partial<DefectMigrationConfig>; 
  onChange: (config: Partial<DefectMigrationConfig>) => void;
  sourceDatasets: DatasetOption[];
  baseDatasets: DatasetOption[];
}) => {
  const colorModes: { value: ColorMatchMode; label: string; desc: string }[] = [
    { value: 'light', label: '轻度匹配', desc: '仅 LAB 空间统计匹配，适合背景颜色接近的场景' },
    { value: 'standard', label: '标准匹配', desc: 'LAB 匹配 + CLAHE 增强（论文方法）' },
    { value: 'strong', label: '强匹配', desc: 'LAB + CLAHE + 自适应亮度 + 可见度增强' },
    { value: 'custom', label: '自定义', desc: '手动配置各参数' },
  ];

  const placementStrategies: { value: PlacementStrategyType; label: string }[] = [
    { value: 'random', label: '完全随机' },
    { value: 'region', label: '指定区域' },
    { value: 'grid', label: '网格式均匀' },
    { value: 'heatmap', label: '热力图引导' },
    { value: 'center', label: '中心优先' },
    { value: 'edge', label: '边缘优先' },
  ];

  return (
    <div className="space-y-6">
      {/* 数据源配置 */}
      <div className="space-y-4">
        <h4 className="font-medium flex items-center gap-2">
          <Database className="h-4 w-4" />
          数据源配置
        </h4>
        
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>缺陷源数据集（需要有标注）</Label>
            <Select 
              value={config.source_dataset_id || ''} 
              onValueChange={(v) => onChange({ ...config, source_dataset_id: v })}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择有标注的数据集" />
              </SelectTrigger>
              <SelectContent>
                {sourceDatasets.length === 0 ? (
                  <SelectItem value="__empty__" disabled>没有可用的有标注数据集</SelectItem>
                ) : (
                  sourceDatasets.map((ds) => (
                    <SelectItem key={ds.id} value={ds.id}>
                      {ds.name} (总计 {ds.annotated_count} 个标注 / {ds.image_count} 张图片)
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
          
          <div className="space-y-2">
            <Label>基底数据集（干净背景）</Label>
            <Select 
              value={config.base_dataset_id || ''} 
              onValueChange={(v) => onChange({ ...config, base_dataset_id: v })}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择基底数据集" />
              </SelectTrigger>
              <SelectContent>
                {baseDatasets.length === 0 ? (
                  <SelectItem value="__empty__" disabled>没有可用的数据集</SelectItem>
                ) : (
                  baseDatasets.map((ds) => (
                    <SelectItem key={ds.id} value={ds.id}>
                      {ds.name} ({ds.image_count} 张图片)
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <Separator />

      {/* 颜色匹配 */}
      <div className="space-y-4">
        <h4 className="font-medium">颜色匹配模式</h4>
        
        <div className="grid grid-cols-2 gap-3">
          {colorModes.map((mode) => (
            <div
              key={mode.value}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                config.color_match_mode === mode.value 
                  ? 'border-primary bg-primary/5' 
                  : 'border-border hover:border-primary/50'
              }`}
              onClick={() => onChange({ ...config, color_match_mode: mode.value })}
            >
              <div className="font-medium text-sm">{mode.label}</div>
              <div className="text-xs text-muted-foreground mt-1">{mode.desc}</div>
            </div>
          ))}
        </div>

        {config.color_match_mode === 'custom' && (
          <div className="grid grid-cols-2 gap-4 p-4 bg-muted rounded-lg">
            <div className="space-y-2">
              <Label>亮度调整</Label>
              <Slider 
                value={[config.color_match_params?.brightness_adjust ?? 1.0]}
                min={0}
                max={2}
                step={0.1}
                onValueChange={([v]) => onChange({
                  ...config,
                  color_match_params: { ...config.color_match_params, brightness_adjust: v }
                })}
              />
            </div>
            <div className="space-y-2">
              <Label>CLAHE clipLimit</Label>
              <Slider 
                value={[config.color_match_params?.clip_limit ?? 2.0]}
                min={1}
                max={10}
                step={0.5}
                onValueChange={([v]) => onChange({
                  ...config,
                  color_match_params: { ...config.color_match_params, clip_limit: v }
                })}
              />
            </div>
          </div>
        )}
      </div>

      <Separator />

      {/* 放置策略 */}
      <div className="space-y-4">
        <h4 className="font-medium">放置策略</h4>
        
        <Select 
          value={config.placement_strategy?.type} 
          onValueChange={(v) => onChange({
            ...config,
            placement_strategy: { ...config.placement_strategy, type: v as PlacementStrategyType }
          })}
        >
          <SelectTrigger>
            <SelectValue placeholder="选择放置策略" />
          </SelectTrigger>
          <SelectContent>
            {placementStrategies.map((s) => (
              <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* ROI 配置（仅在 region 策略时显示） */}
        {config.placement_strategy?.type === 'region' && (
          <div className="p-4 bg-muted rounded-lg space-y-4">
            <h5 className="text-sm font-medium">感兴趣区域 (ROI) 配置</h5>
            <div className="grid grid-cols-4 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">X 坐标</Label>
                <Input 
                  type="number"
                  min={0}
                  placeholder="0"
                  value={config.placement_strategy?.roi?.[0] ?? ''}
                  onChange={(e) => {
                    const roi = config.placement_strategy?.roi || [0, 0, 100, 100];
                    roi[0] = parseInt(e.target.value) || 0;
                    onChange({
                      ...config,
                      placement_strategy: {
                        ...config.placement_strategy,
                        roi
                      }
                    });
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Y 坐标</Label>
                <Input 
                  type="number"
                  min={0}
                  placeholder="0"
                  value={config.placement_strategy?.roi?.[1] ?? ''}
                  onChange={(e) => {
                    const roi = config.placement_strategy?.roi || [0, 0, 100, 100];
                    roi[1] = parseInt(e.target.value) || 0;
                    onChange({
                      ...config,
                      placement_strategy: {
                        ...config.placement_strategy,
                        roi
                      }
                    });
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">宽度</Label>
                <Input 
                  type="number"
                  min={1}
                  placeholder="100"
                  value={config.placement_strategy?.roi?.[2] ?? ''}
                  onChange={(e) => {
                    const roi = config.placement_strategy?.roi || [0, 0, 100, 100];
                    roi[2] = parseInt(e.target.value) || 100;
                    onChange({
                      ...config,
                      placement_strategy: {
                        ...config.placement_strategy,
                        roi
                      }
                    });
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">高度</Label>
                <Input 
                  type="number"
                  min={1}
                  placeholder="100"
                  value={config.placement_strategy?.roi?.[3] ?? ''}
                  onChange={(e) => {
                    const roi = config.placement_strategy?.roi || [0, 0, 100, 100];
                    roi[3] = parseInt(e.target.value) || 100;
                    onChange({
                      ...config,
                      placement_strategy: {
                        ...config.placement_strategy,
                        roi
                      }
                    });
                  }}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              设置缺陷放置的矩形区域 [x, y, width, height]，坐标相对于图像左上角
            </p>
          </div>
        )}

        {/* 网格配置（仅在 grid 策略时显示） */}
        {config.placement_strategy?.type === 'grid' && (
          <div className="p-4 bg-muted rounded-lg space-y-4">
            <h5 className="text-sm font-medium">网格配置</h5>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">行数</Label>
                <Input 
                  type="number"
                  min={1}
                  max={10}
                  placeholder="3"
                  value={config.placement_strategy?.grid?.rows ?? 3}
                  onChange={(e) => {
                    const grid = config.placement_strategy?.grid || { rows: 3, cols: 3 };
                    grid.rows = parseInt(e.target.value) || 3;
                    onChange({
                      ...config,
                      placement_strategy: {
                        ...config.placement_strategy,
                        grid
                      }
                    });
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">列数</Label>
                <Input 
                  type="number"
                  min={1}
                  max={10}
                  placeholder="3"
                  value={config.placement_strategy?.grid?.cols ?? 3}
                  onChange={(e) => {
                    const grid = config.placement_strategy?.grid || { rows: 3, cols: 3 };
                    grid.cols = parseInt(e.target.value) || 3;
                    onChange({
                      ...config,
                      placement_strategy: {
                        ...config.placement_strategy,
                        grid
                      }
                    });
                  }}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              将图像划分为网格，在每个网格内放置缺陷
            </p>
          </div>
        )}

        {/* 热力图配置（仅在 heatmap 策略时显示） */}
        {config.placement_strategy?.type === 'heatmap' && (
          <div className="p-4 bg-muted rounded-lg space-y-4">
            <h5 className="text-sm font-medium">热力图配置</h5>
            
            <div className="space-y-2">
              <Label className="text-xs">热力图类型</Label>
              <Select
                value={config.placement_strategy?.heatmap?.type || 'gaussian'}
                onValueChange={(v) => {
                  onChange({
                    ...config,
                    placement_strategy: {
                      ...config.placement_strategy,
                      heatmap: {
                        ...config.placement_strategy?.heatmap,
                        type: v
                      }
                    }
                  });
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择热力图类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gaussian">高斯分布（中心高概率）</SelectItem>
                  <SelectItem value="edge">边缘偏好</SelectItem>
                  <SelectItem value="center">中心偏好</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {config.placement_strategy?.heatmap?.type === 'gaussian' && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">中心 X ({config.placement_strategy?.heatmap?.center_x ?? 50}%)</Label>
                  <Slider
                    value={[config.placement_strategy?.heatmap?.center_x ?? 50]}
                    min={0}
                    max={100}
                    step={5}
                    onValueChange={([v]) => {
                      onChange({
                        ...config,
                        placement_strategy: {
                          ...config.placement_strategy,
                          heatmap: {
                            ...config.placement_strategy?.heatmap,
                            center_x: v
                          }
                        }
                      });
                    }}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">中心 Y ({config.placement_strategy?.heatmap?.center_y ?? 50}%)</Label>
                  <Slider
                    value={[config.placement_strategy?.heatmap?.center_y ?? 50]}
                    min={0}
                    max={100}
                    step={5}
                    onValueChange={([v]) => {
                      onChange({
                        ...config,
                        placement_strategy: {
                          ...config.placement_strategy,
                          heatmap: {
                            ...config.placement_strategy?.heatmap,
                            center_y: v
                          }
                        }
                      });
                    }}
                  />
                </div>
                <div className="space-y-1 col-span-2">
                  <Label className="text-xs">扩散程度 ({config.placement_strategy?.heatmap?.sigma ?? 30})</Label>
                  <Slider
                    value={[config.placement_strategy?.heatmap?.sigma ?? 30]}
                    min={10}
                    max={100}
                    step={5}
                    onValueChange={([v]) => {
                      onChange({
                        ...config,
                        placement_strategy: {
                          ...config.placement_strategy,
                          heatmap: {
                            ...config.placement_strategy?.heatmap,
                            sigma: v
                          }
                        }
                      });
                    }}
                  />
                </div>
              </div>
            )}

            {config.placement_strategy?.heatmap?.type === 'edge' && (
              <div className="space-y-2">
                <Label className="text-xs">边缘宽度 ({config.placement_strategy?.heatmap?.edge_width ?? 10}%)</Label>
                <Slider
                  value={[config.placement_strategy?.heatmap?.edge_width ?? 10]}
                  min={5}
                  max={30}
                  step={1}
                  onValueChange={([v]) => {
                    onChange({
                      ...config,
                      placement_strategy: {
                        ...config.placement_strategy,
                        heatmap: {
                          ...config.placement_strategy?.heatmap,
                          edge_width: v
                        }
                      }
                    });
                  }}
                />
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              热力图亮度表示缺陷放置的概率，越亮的位置越可能放置缺陷
            </p>
          </div>
        )}

        {/* 中心优先提示 */}
        {config.placement_strategy?.type === 'center' && (
          <div className="p-4 bg-muted rounded-lg">
            <p className="text-sm text-muted-foreground">
              缺陷将优先放置在图像中心区域，偏离中心的概率随距离增加而降低
            </p>
          </div>
        )}

        {/* 边缘优先提示 */}
        {config.placement_strategy?.type === 'edge' && (
          <div className="p-4 bg-muted rounded-lg">
            <p className="text-sm text-muted-foreground">
              缺陷将优先放置在图像边缘区域（上、下、左、右四边）
            </p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>每图最小缺陷数</Label>
            <Input 
              type="number"
              min={1}
              max={10}
              value={config.placement_strategy?.defects_per_image?.min ?? 1}
              onChange={(e) => onChange({
                ...config,
                placement_strategy: {
                  ...config.placement_strategy,
                  defects_per_image: {
                    ...config.placement_strategy?.defects_per_image,
                    min: parseInt(e.target.value)
                  }
                }
              })}
            />
          </div>
          <div className="space-y-2">
            <Label>每图最大缺陷数</Label>
            <Input 
              type="number"
              min={1}
              max={10}
              value={config.placement_strategy?.defects_per_image?.max ?? 3}
              onChange={(e) => onChange({
                ...config,
                placement_strategy: {
                  ...config.placement_strategy,
                  defects_per_image: {
                    ...config.placement_strategy?.defects_per_image,
                    max: parseInt(e.target.value)
                  }
                }
              })}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

// ==================== Stable Diffusion API 配置表单 ====================

const API_ENDPOINT_OPTIONS = [
  { value: 'https://api.replicate.com/v1/predictions', label: 'Replicate (推荐，速度快)' },
  { value: 'https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell', label: 'HuggingFace FLUX Schnell ⭐ (免费，快)' },
  { value: 'https://router.huggingface.co/hf-inference/models/runwayml/stable-diffusion-v1-5', label: 'HuggingFace SD 1.5 (免费，需协议)' },
  { value: 'https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-2-1', label: 'HuggingFace SD 2.1 (免费，需协议)' },
  { value: 'http://localhost:7860/sdapi/v1/txt2img', label: '本地 A1111 (需GPU)' },
  { value: 'custom', label: '自定义地址...' },
];

const REPLICATE_MODEL_OPTIONS = [
  { value: 'black-forest-labs/flux-schnell', label: 'FLUX Schnell (推荐，4步出图，速度快)' },
  { value: 'black-forest-labs/flux-1.1-pro', label: 'FLUX 1.1 Pro (最高质量)' },
  { value: 'black-forest-labs/flux-dev', label: 'FLUX Dev (质量速度平衡)' },
  { value: 'stability-ai/stable-diffusion-xl-base-1.0', label: 'SDXL Base 1.0 (传统模型)' },
];

const StableDiffusionConfigForm = ({ config, onChange }: { 
  config: Partial<StableDiffusionAPIConfig>; 
  onChange: (config: Partial<StableDiffusionAPIConfig>) => void;
}) => {
  const [customEndpoint, setCustomEndpoint] = useState(false);
  
  // 检测是否使用自定义地址
  const isCustomEndpoint = config.api_endpoint && 
    !API_ENDPOINT_OPTIONS.some(opt => opt.value === config.api_endpoint);
  
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label>API 提供商</Label>
        <Select 
          value={isCustomEndpoint ? 'custom' : (config.api_endpoint || 'https://api.replicate.com/v1/predictions')}
          onValueChange={(v) => {
            if (v === 'custom') {
              setCustomEndpoint(true);
            } else {
              setCustomEndpoint(false);
              onChange({ ...config, api_endpoint: v });
            }
          }}
        >
          <SelectTrigger>
            <SelectValue placeholder="选择 API 提供商" />
          </SelectTrigger>
          <SelectContent>
            {API_ENDPOINT_OPTIONS.map(opt => (
              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {(customEndpoint || isCustomEndpoint) && (
          <Input 
            className="mt-2"
            placeholder="输入自定义 API 地址"
            value={config.api_endpoint || ''}
            onChange={(e) => onChange({ ...config, api_endpoint: e.target.value })}
          />
        )}
      </div>

      {config.api_endpoint?.includes('replicate.com') && (
        <div className="space-y-2">
          <Label>Replicate 模型版本</Label>
          <Select 
            value={config.replicate_version || 'black-forest-labs/flux-schnell'}
            onValueChange={(v) => onChange({ ...config, replicate_version: v })}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择模型" />
            </SelectTrigger>
            <SelectContent>
              {REPLICATE_MODEL_OPTIONS.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            FLUX 模型速度快，SD 模型兼容性好
          </p>
        </div>
      )}

      <div className="space-y-2">
        <Label>API 密钥</Label>
        <Input 
          type="password"
          placeholder={config.api_endpoint?.includes('huggingface') ? "hf_xxx 或从 huggingface.co/settings/tokens 获取" : "r8_xxx 或从 replicate.com/account/api-tokens 获取"}
          value={config.api_key || ''}
          onChange={(e) => onChange({ ...config, api_key: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          {config.api_endpoint?.includes('localhost') 
            ? "本地部署可留空"
            : config.api_endpoint?.includes('huggingface')
            ? "HuggingFace Token 以 hf_ 开头"
            : "Replicate Token 以 r8_ 开头"}
        </p>
      </div>

      <div className="space-y-2">
        <Label>生成提示词</Label>
        <textarea 
          className="w-full min-h-[100px] p-3 rounded-md border border-input bg-background"
          placeholder="描述要生成的缺陷类型，如 'a scratch on white metal surface, industrial defect, high quality'"
          value={config.prompt || ''}
          onChange={(e) => onChange({ ...config, prompt: e.target.value })}
        />
      </div>

      <div className="space-y-2">
        <Label>负向提示词 {config.api_endpoint?.includes('flux') && <span className="text-muted-foreground">(FLUX 模型可忽略)</span>}</Label>
        <Input 
          placeholder="不希望出现的内容，如 blurry, low quality, text, watermark"
          value={config.negative_prompt || ''}
          onChange={(e) => onChange({ ...config, negative_prompt: e.target.value })}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>推理步数 ({config.num_inference_steps ?? (config.api_endpoint?.includes('flux') ? 4 : 20)})</Label>
          <Slider 
            value={[config.num_inference_steps ?? (config.api_endpoint?.includes('flux') ? 4 : 20)]}
            min={4}
            max={config.api_endpoint?.includes('flux') ? 8 : 50}
            step={1}
            onValueChange={([v]) => onChange({ ...config, num_inference_steps: v })}
          />
          <p className="text-xs text-muted-foreground">
            {config.api_endpoint?.includes('flux') ? "FLUX 只需 4 步" : "SD 建议 20-30 步"}
          </p>
        </div>
        <div className="space-y-2">
          <Label>引导强度 ({config.guidance_scale ?? 7.5})</Label>
          <Slider 
            value={[config.guidance_scale ?? 7.5]}
            min={1}
            max={20}
            step={0.5}
            onValueChange={([v]) => onChange({ ...config, guidance_scale: v })}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>图像宽度</Label>
          <Select 
            value={String(config.image_size?.width ?? 512)}
            onValueChange={(v) => onChange({
              ...config,
              image_size: { ...config.image_size, width: parseInt(v) }
            })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="256">256px</SelectItem>
              <SelectItem value="512">512px</SelectItem>
              <SelectItem value="768">768px</SelectItem>
              <SelectItem value="1024">1024px</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>图像高度</Label>
          <Select 
            value={String(config.image_size?.height ?? 512)}
            onValueChange={(v) => onChange({
              ...config,
              image_size: { ...config.image_size, height: parseInt(v) }
            })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="256">256px</SelectItem>
              <SelectItem value="512">512px</SelectItem>
              <SelectItem value="768">768px</SelectItem>
              <SelectItem value="1024">1024px</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
};

// ==================== 主页面组件 ====================

export default function GenerationPage() {
  const navigate = useNavigate();
  // const { user } = useAuthStore();
  
  // 状态
  const [generators, setGenerators] = useState<GeneratorInfo[]>([]);
  const [selectedGenerator, setSelectedGenerator] = useState<GeneratorInfo | null>(null);
  const [config, setConfig] = useState<Record<string, any>>({});
  const [preview, setPreview] = useState<GenerationPreviewResponse | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  const [activeTab, setActiveTab] = useState('generators');
  const [error, setError] = useState<string | null>(null);
  const [generationCount, setGenerationCount] = useState(100);
  const [outputDatasetName, setOutputDatasetName] = useState('');
  
  // 删除对话框状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [jobToDelete, setJobToDelete] = useState<GenerationJob | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // 数据集列表
  const [sourceDatasets, setSourceDatasets] = useState<DatasetOption[]>([]);
  const [baseDatasets, setBaseDatasets] = useState<DatasetOption[]>([]);

  // 加载生成器列表
  useEffect(() => {
    const loadGenerators = async () => {
      try {
        const response = await generationApi.getGenerators();
        if (response.data.success) {
          setGenerators(response.data.data.generators);
        }
      } catch (err) {
        setError('加载生成器列表失败');
      }
    };
    loadGenerators();
  }, []);

  // 加载数据集列表
  useEffect(() => {
    const loadDatasets = async () => {
      try {
        console.log('开始加载数据集列表...');
        
        // 加载有标注的数据集（作为缺陷源）
        const sourceResponse = await generationApi.getDatasets({ has_annotations: true });
        console.log('源数据集响应:', sourceResponse.data);
        if (sourceResponse.data.success) {
          setSourceDatasets(sourceResponse.data.data.items);
        }
        
        // 加载所有数据集（作为基底）
        const baseResponse = await generationApi.getDatasets();
        console.log('基底数据集响应:', baseResponse.data);
        if (baseResponse.data.success) {
          setBaseDatasets(baseResponse.data.data.items);
        }
      } catch (err) {
        console.error('加载数据集列表失败', err);
        setError('加载数据集列表失败: ' + (err as Error).message);
      }
    };
    loadDatasets();
  }, []);

  // 加载任务列表
  const loadJobs = useCallback(async () => {
    try {
      const response = await generationApi.getJobs({ page: 1, page_size: 10 });
      if (response.data.success) {
        setJobs(response.data.data.items);
      }
    } catch (err) {
      console.error('加载任务列表失败', err);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  // 生成预览
  const handlePreview = async () => {
    if (!selectedGenerator) return;
    
    setIsPreviewLoading(true);
    setError(null);
    
    try {
      const response = await generationApi.createPreview({
        generator_name: selectedGenerator.name,
        config,
        seed: Math.floor(Math.random() * 10000),
      });
      
      if (response.data.success) {
        setPreview(response.data.data);
      } else {
        setError(response.data.message || '预览生成失败');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '预览生成失败');
    } finally {
      setIsPreviewLoading(false);
    }
  };

  // 开始生成
  const handleGenerate = async () => {
    if (!selectedGenerator || !outputDatasetName) return;
    
    setIsGenerating(true);
    setError(null);
    
    try {
      const response = await generationApi.executeGeneration({
        generator_name: selectedGenerator.name,
        config,
        count: generationCount,
        output_dataset_name: outputDatasetName,
        annotation_format: 'yolo',
      });
      
      if (response.data.success) {
        setActiveTab('jobs');
        loadJobs();
      } else {
        setError(response.data.message || '任务提交失败');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '任务提交失败');
    } finally {
      setIsGenerating(false);
    }
  };

  // 获取状态颜色
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'running': return 'bg-blue-100 text-blue-800';
      case 'failed': return 'bg-red-100 text-red-800';
      case 'paused': return 'bg-yellow-100 text-yellow-800';
      case 'cancelled': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // 渲染配置表单
  const renderConfigForm = () => {
    if (!selectedGenerator) return null;

    switch (selectedGenerator.name) {
      case 'defect_migration':
        return (
          <DefectMigrationConfigForm 
            config={config as Partial<DefectMigrationConfig>}
            onChange={setConfig}
            sourceDatasets={sourceDatasets}
            baseDatasets={baseDatasets}
          />
        );
      case 'stable_diffusion_api':
        return (
          <StableDiffusionConfigForm 
            config={config as Partial<StableDiffusionAPIConfig>}
            onChange={setConfig}
          />
        );
      default:
        return (
          <div className="p-8 text-center text-muted-foreground">
            <Settings className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>该生成器的配置表单待实现</p>
            <p className="text-sm">请使用 JSON 格式配置参数</p>
          </div>
        );
    }
  };

  // 处理删除任务
  const handleDeleteJob = (job: GenerationJob) => {
    setJobToDelete(job);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteJob = async () => {
    if (!jobToDelete) return;
    
    setIsDeleting(true);
    try {
      const response = await generationApi.deleteJob(jobToDelete.id);
      if (response.data.success) {
        setJobs(jobs.filter(j => j.id !== jobToDelete.id));
        setDeleteDialogOpen(false);
        setJobToDelete(null);
      } else {
        setError(response.data.message || '删除任务失败');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || '删除任务失败');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <Wand2 className="h-8 w-8 text-primary" />
            数据生成
          </h1>
          <p className="text-muted-foreground mt-1">
            使用 AI 生成合成缺陷数据，扩充训练数据集
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate('/admin/generation/tasks')}>
          查看任务列表
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="generators">1. 选择生成器</TabsTrigger>
          <TabsTrigger value="config" disabled={!selectedGenerator}>2. 配置参数</TabsTrigger>
          <TabsTrigger value="jobs">3. 执行任务</TabsTrigger>
        </TabsList>

        {/* 选择生成器 */}
        <TabsContent value="generators" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>选择数据生成器</CardTitle>
              <CardDescription>
                选择适合您需求的生成器类型，支持缺陷迁移和外部 API 生成
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {generators.map((generator) => (
                  <GeneratorCard
                    key={generator.name}
                    generator={generator}
                    isSelected={selectedGenerator?.name === generator.name}
                    onSelect={() => {
                      setSelectedGenerator(generator);
                      // 根据生成器类型设置默认配置
                      let defaultConfig = generator.default_config || {};
                      if (generator.name === 'defect_migration') {
                        defaultConfig = {
                          source_type: 'dataset',
                          source_dataset_id: '',
                          base_dataset_id: '',
                          color_match_mode: 'standard',
                          placement_strategy: {
                            type: 'random',
                            defects_per_image: { min: 1, max: 3 }
                          },
                          ...defaultConfig
                        };
                      }
                      setConfig(defaultConfig);
                      setActiveTab('config');
                    }}
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 配置参数 */}
        <TabsContent value="config" className="space-y-6">
          {selectedGenerator && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 配置表单 */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings className="h-5 w-5" />
                    配置参数
                  </CardTitle>
                  <CardDescription>
                    配置 {selectedGenerator.name} 的生成参数
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[600px]">
                    {renderConfigForm()}
                  </ScrollArea>
                </CardContent>
              </Card>

              {/* 预览和执行 */}
              <div className="space-y-6">
                {/* 预览 */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Eye className="h-5 w-5" />
                      实时预览
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="aspect-video bg-muted rounded-lg flex items-center justify-center overflow-hidden">
                      {preview ? (
                        <img 
                          src={preview.generated_image} 
                          alt="生成预览"
                          className="w-full h-full object-contain"
                        />
                      ) : (
                        <div className="text-center text-muted-foreground">
                          <ImageIcon className="h-16 w-16 mx-auto mb-2 opacity-50" />
                          <p>点击"生成预览"查看效果</p>
                        </div>
                      )}
                    </div>

                    {preview && (
                      <div className="text-sm text-muted-foreground space-y-1">
                        <p>缺陷数量: {preview.metadata.num_defects}</p>
                        <p>平均质量: {(preview.metadata.average_quality * 100).toFixed(1)}%</p>
                        <p>生成耗时: {preview.generation_time.toFixed(2)}s</p>
                      </div>
                    )}

                    <Button 
                      variant="outline" 
                      className="w-full"
                      onClick={handlePreview}
                      disabled={isPreviewLoading}
                    >
                      {isPreviewLoading ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          生成中...
                        </>
                      ) : (
                        <>
                          <RotateCcw className="mr-2 h-4 w-4" />
                          生成预览
                        </>
                      )}
                    </Button>
                  </CardContent>
                </Card>

                {/* 执行配置 */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Play className="h-5 w-5" />
                      执行生成
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label>生成数量 (1-10000)</Label>
                      <Input 
                        type="number"
                        min={1}
                        max={10000}
                        value={generationCount}
                        onChange={(e) => setGenerationCount(parseInt(e.target.value) || 100)}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label>输出数据集名称</Label>
                      <Input 
                        placeholder={`${selectedGenerator.name}_generated_${Date.now()}`}
                        value={outputDatasetName}
                        onChange={(e) => setOutputDatasetName(e.target.value)}
                      />
                    </div>

                    <Button 
                      className="w-full"
                      onClick={handleGenerate}
                      disabled={isGenerating || !outputDatasetName}
                    >
                      {isGenerating ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          提交中...
                        </>
                      ) : (
                        <>
                          <Play className="mr-2 h-4 w-4" />
                          开始生成
                        </>
                      )}
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </TabsContent>

        {/* 任务列表 */}
        <TabsContent value="jobs" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>生成任务</CardTitle>
              <CardDescription>
                查看和管理数据生成任务
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {jobs.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>暂无生成任务</p>
                    <Button 
                      variant="link" 
                      onClick={() => setActiveTab('generators')}
                    >
                      创建新任务
                    </Button>
                  </div>
                ) : (
                  jobs.map((job) => (
                    <div 
                      key={job.id}
                      className="p-4 border rounded-lg space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <h4 className="font-medium">{job.name}</h4>
                          <Badge className={getStatusColor(job.status)}>
                            {job.status}
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                          {job.status === 'running' && (
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => generationApi.controlJob(job.id, { action: 'pause' })}
                            >
                              <Pause className="h-4 w-4" />
                            </Button>
                          )}
                          {job.status === 'paused' && (
                            <Button 
                              size="sm" 
                              variant="outline"
                              onClick={() => generationApi.controlJob(job.id, { action: 'resume' })}
                            >
                              <Play className="h-4 w-4" />
                            </Button>
                          )}
                          {(job.status === 'running' || job.status === 'paused') && (
                            <Button 
                              size="sm" 
                              variant="destructive"
                              onClick={() => generationApi.controlJob(job.id, { action: 'cancel' })}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          )}
                          {(job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDeleteJob(job)}
                            >
                              <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                          )}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">
                            进度: {job.processed_count}/{job.total_count}
                          </span>
                          <span className="text-muted-foreground">
                            成功: {job.success_count} | 失败: {job.failed_count}
                          </span>
                        </div>
                        <Progress value={job.progress} />
                      </div>

                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span>生成器: {job.generator_name}</span>
                        <span>格式: {job.annotation_format}</span>
                        <span>
                          创建: {new Date(job.created_at).toLocaleString()}
                        </span>
                      </div>

                      {job.status === 'completed' && job.output_dataset_id && (
                        <div className="flex items-center gap-2 pt-2">
                          <CheckCircle2 className="h-4 w-4 text-green-500" />
                          <span className="text-sm">生成完成</span>
                          <Button 
                            size="sm" 
                            variant="link"
                            onClick={() => navigate(`/admin/datasets/${job.output_dataset_id}`)}
                          >
                            查看数据集
                          </Button>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 删除确认对话框 */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              {`确定要删除任务 "${jobToDelete?.name || ''}" 吗？此操作不可恢复。`}
              {jobToDelete?.output_dataset_id && (
                <span className="block mt-2">关联的输出数据集也将被标记为删除。</span>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={confirmDeleteJob} disabled={isDeleting}>
              {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : '删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
