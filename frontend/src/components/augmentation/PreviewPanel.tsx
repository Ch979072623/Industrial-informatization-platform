/**
 * 实时预览面板组件
 * 
 * 功能：
 * - 数据集样本选择 / 本地上传（拖拽支持）
 * - 左右对比布局，支持缩放查看细节
 * - 标注框可视化（同步显示、颜色区分、悬停提示）
 * - 显示图片信息和标注框统计
 * - 自动预览（防抖500ms）+ 手动刷新
 * - 完整的错误处理和加载状态
 */
import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { 
  RefreshCw, 
  Image as ImageIcon, 
  AlertCircle, 
  ZoomIn, 
  ZoomOut, 
  Maximize,
  Eye,
  EyeOff,
  Upload,
  X,
  ChevronDown,
  Maximize2,
  Loader2,
  RotateCcw,
  WifiOff,
  Database,
  Settings
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { datasetApi } from '@/services/api';
import { useAugmentationStore } from '@/stores/augmentationStore';
import {
  createPreviewWithRetry,
  validateUploadFile,
  extractImageMetadata,
  readFileAsDataURL,
  classifyPreviewError,
  clearPreviewCache,
} from '@/services/previewService';
import type { Dataset } from '@/types';
import type { AugmentationOperation } from '@/types/augmentation';
import type { 
  PreviewResult, 
  PreviewError, 
  PreviewBBox, 
  UploadFileInfo,
  ZoomState,
  PreviewSampleType,
  PreviewDisplayMode,
} from '@/types/preview';
import { PREVIEW_CONFIG, getClassColor } from '@/types/preview';

// ==================== 子组件 ====================

/**
 * 标注框覆盖层组件
 * 使用百分比定位，自适应图片大小
 */
interface BBoxOverlayProps {
  bboxes: PreviewBBox[];
  displayMode: PreviewDisplayMode;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  classNames: string[];
}

const BBoxOverlay: React.FC<BBoxOverlayProps> = ({
  bboxes,
  displayMode,
  selectedId,
  onSelect,
  classNames,
}) => {
  if (displayMode === 'image_only' || bboxes.length === 0) return null;

  return (
    <div className="absolute inset-0 pointer-events-none">
      {bboxes.map((bbox) => {
        const isSelected = selectedId === bbox.id;
        const color = getClassColor(bbox.class_id);
        const className = bbox.class_name || classNames[bbox.class_id] || `类别 ${bbox.class_id}`;
        
        // 使用百分比定位，相对于父容器
        const left = bbox.x1 * 100;
        const top = bbox.y1 * 100;
        const width = (bbox.x2 - bbox.x1) * 100;
        const height = (bbox.y2 - bbox.y1) * 100;
        
        return (
          <TooltipProvider key={bbox.id}>
            <Tooltip>
              <TooltipTrigger asChild>
                <div
                  className="absolute pointer-events-auto cursor-pointer transition-all"
                  style={{
                    left: `${left}%`,
                    top: `${top}%`,
                    width: `${width}%`,
                    height: `${height}%`,
                    border: `2px solid ${color}`,
                    backgroundColor: isSelected ? `${color}40` : 'transparent',
                    boxShadow: isSelected ? `0 0 0 2px ${color}` : 'none',
                    minWidth: '4px',
                    minHeight: '4px',
                  }}
                  onClick={() => onSelect(isSelected ? null : bbox.id)}
                  onMouseEnter={() => onSelect(bbox.id)}
                  onMouseLeave={() => onSelect(null)}
                />
              </TooltipTrigger>
              <TooltipContent side="top">
                <div className="text-xs">
                  <div className="font-medium" style={{ color }}>{className}</div>
                  {bbox.confidence && (
                    <div>置信度: {(bbox.confidence * 100).toFixed(1)}%</div>
                  )}
                  <div className="text-gray-400">
                    [{Math.round(width)}% x {Math.round(height)}%]
                  </div>
                </div>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        );
      })}
    </div>
  );
};

/**
 * 图片对比视图组件
 */
interface ImageCompareViewProps {
  original: PreviewResult['original'];
  augmented: PreviewResult['augmented'];
  displayMode: PreviewDisplayMode;
  zoom: ZoomState;
  onZoomChange: (zoom: ZoomState) => void;
  selectedBBoxId: string | null;
  onBBoxSelect: (id: string | null) => void;
  classNames: string[];
  isLoading: boolean;
}

const ImageCompareView: React.FC<ImageCompareViewProps> = ({
  original,
  augmented,
  displayMode,
  zoom,
  onZoomChange,
  selectedBBoxId,
  onBBoxSelect,
  classNames,
  isLoading,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);

  // 处理拖拽
  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom.scale > 1) {
      setDragStart({ x: e.clientX - zoom.position.x, y: e.clientY - zoom.position.y });
      onZoomChange({ ...zoom, isDragging: true });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (zoom.isDragging && dragStart) {
      onZoomChange({
        ...zoom,
        position: {
          x: e.clientX - dragStart.x,
          y: e.clientY - dragStart.y,
        },
      });
    }
  };

  const handleMouseUp = () => {
    setDragStart(null);
    onZoomChange({ ...zoom, isDragging: false });
  };

  // 渲染单张图片
  const renderImage = (
    type: 'original' | 'augmented',
    info: PreviewResult['original'] | PreviewResult['augmented']
  ) => (
    <div className="relative flex-1 flex flex-col min-w-0">
      {/* 标签 */}
      <div className="absolute top-2 left-2 z-10 px-2 py-1 bg-black/70 text-white text-xs rounded">
        {type === 'original' ? '原图' : '增强后'}
        <span className="ml-2 text-gray-300">
          {info.width > 0 && `${info.width}×${info.height}`}
        </span>
      </div>

      {/* 标注框数量 */}
      {displayMode === 'image_with_bboxes' && (
        <div className="absolute top-2 right-2 z-10 px-2 py-1 bg-blue-600 text-white text-xs rounded">
          {info.bbox_count} 个标注框
        </div>
      )}

      {/* 图片容器 */}
      <div 
        className="flex-1 relative overflow-hidden bg-gray-100 flex items-center justify-center"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: zoom.isDragging ? 'grabbing' : zoom.scale > 1 ? 'grab' : 'default' }}
      >
        {isLoading ? (
          <Skeleton className="w-full h-full" />
        ) : (
          <div
            className="relative transition-transform duration-100"
            style={{
              transform: `translate(${zoom.position.x}px, ${zoom.position.y}px) scale(${zoom.scale})`,
            }}
          >
            <img
              src={info.url}
              alt={type === 'original' ? '原图' : '增强图'}
              className="max-w-full max-h-full object-contain"
              draggable={false}
              onError={(e) => {
                (e.target as HTMLImageElement).src = '/placeholder-image.png';
              }}
            />
            {/* 标注框覆盖层 */}
            <BBoxOverlay
              bboxes={info.bboxes}
              displayMode={displayMode}
              selectedId={selectedBBoxId}
              onSelect={onBBoxSelect}
              classNames={classNames}
            />
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div ref={containerRef} className="flex-1 flex gap-2 overflow-hidden">
      {renderImage('original', original)}
      {renderImage('augmented', augmented)}
    </div>
  );
};

// ==================== 主组件 ====================

interface PreviewPanelProps {
  dataset: Dataset;
  pipelineConfig: AugmentationOperation[];
  disabled?: boolean;
}

export const PreviewPanel: React.FC<PreviewPanelProps> = ({
  dataset,
  pipelineConfig,
  disabled = false,
}) => {
  // ===== 状态管理 =====
  const [sampleType, setSampleType] = useState<PreviewSampleType>('dataset');
  const [selectedImageId, setSelectedImageId] = useState<string>('');
  const [sampleImages, setSampleImages] = useState<Array<{ id: string; filename: string }>>([]);
  const [uploadedFile, setUploadedFile] = useState<UploadFileInfo | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  
  const [displayMode, setDisplayMode] = useState<PreviewDisplayMode>('image_with_bboxes');
  const [zoom, setZoom] = useState<ZoomState>({
    scale: 1,
    position: { x: 0, y: 0 },
    isDragging: false,
  });
  const [selectedBBoxId, setSelectedBBoxId] = useState<string | null>(null);
  
  const [previewState, setPreviewState] = useState<{
    result: PreviewResult | null;
    isLoading: boolean;
    progress: number;
    error: PreviewError | null;
    retryCount: number;
  }>({
    result: null,
    isLoading: false,
    progress: 0,
    error: null,
    retryCount: 0,
  });

  const abortControllerRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const { class_names: classNames = [] } = dataset;

  // ===== 数据加载 =====
  
  // 加载数据集样本图片
  useEffect(() => {
    if (sampleType !== 'dataset') return;

    const loadSamples = async () => {
      // console.log('[PreviewPanel] Loading samples for dataset:', dataset.id);
      try {
        const response = await datasetApi.getDatasetImages(dataset.id, { page: 1, page_size: 20 });
        // console.log('[PreviewPanel] Samples response:', response.data);
        const imagesData = response.data.data?.items || [];
        if (response.data.success && imagesData.length > 0) {
          const images = imagesData.map(img => ({
            id: img.id,
            filename: img.filename,
          }));
          // console.log('[PreviewPanel] Loaded', images.length, 'samples');
          setSampleImages(images);
          // 如果没有选中图片或选中的图片不在列表中，选择第一张
          setSelectedImageId(prev => {
            const imageIds = images.map(img => img.id);
            if (!prev || !imageIds.includes(prev)) {
              // console.log('[PreviewPanel] Auto-selecting first image:', images[0].id);
              return images[0].id;
            }
            return prev;
          });
        } else {
          // console.log('[PreviewPanel] No samples found');
          setSampleImages([]);
          setSelectedImageId('');
        }
      } catch (error) {
        console.error('[PreviewPanel] Failed to load samples:', error);
        setSampleImages([]);
      }
    };

    loadSamples();
  }, [dataset.id, sampleType]);

  // ===== 预览生成 =====

  // 使用 ref 存储状态，避免触发依赖变化
  const uploadedFileRef = useRef(uploadedFile);
  const selectedImageIdRef = useRef(selectedImageId);
  useEffect(() => {
    uploadedFileRef.current = uploadedFile;
  }, [uploadedFile]);
  useEffect(() => {
    selectedImageIdRef.current = selectedImageId;
  }, [selectedImageId]);

  const generatePreview = useCallback(async (isManual: boolean = false, fileInfo?: UploadFileInfo) => {
    // 检查是否可以预览
    if (pipelineConfig.length === 0) return;
    
    // 使用传入的 fileInfo 或 ref 中的值
    const currentFile = fileInfo || uploadedFileRef.current;
    const currentImageId = selectedImageIdRef.current;
    
    if (sampleType === 'dataset' && !currentImageId) return;
    if (sampleType === 'upload' && !currentFile) return;

    // 取消之前的请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setPreviewState(prev => ({
      ...prev,
      isLoading: true,
      progress: 0,
      error: null,
    }));

    try {
      const params = {
        sample_type: sampleType,
        dataset_id: dataset.id,
        image_id: currentImageId,
        pipeline_config: pipelineConfig,
        display_mode: displayMode,
      };

      let result: PreviewResult;
      
      // 如果是本地上传，传递 base64 图片到后端
      if (sampleType === 'upload' && currentFile) {
        result = await createPreviewWithRetry(
          params,
          currentFile.previewUrl // 这是 base64 Data URL
        );
      } else {
        result = await createPreviewWithRetry(params);
      }

      setPreviewState({
        result,
        isLoading: false,
        progress: 100,
        error: null,
        retryCount: 0,
      });
    } catch (error) {
      const previewError = classifyPreviewError(error instanceof Error ? error : new Error('Unknown'));
      
      setPreviewState(prev => ({
        ...prev,
        isLoading: false,
        progress: 0,
        error: previewError,
        retryCount: isManual ? prev.retryCount + 1 : prev.retryCount,
      }));
    }
  }, [dataset.id, pipelineConfig, displayMode, sampleType]);

  // 当流水线为空时清空预览结果
  useEffect(() => {
    if (pipelineConfig.length === 0) {
      setPreviewState(prev => ({
        ...prev,
        result: null,
        error: null,
      }));
    }
  }, [pipelineConfig.length]);

  // 防抖的自动预览
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = setTimeout(() => {
      generatePreview(false);
    }, PREVIEW_CONFIG.DEBOUNCE);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [generatePreview]);

  // ===== 文件上传处理 =====

  const handleFileUpload = async (file: File) => {
    // 验证文件
    const error = validateUploadFile(file);
    if (error) {
      setPreviewState(prev => ({ ...prev, error }));
      return;
    }

    try {
      // 先设置 sampleType
      setSampleType('upload');
      
      // 提取元数据
      const metadata = await extractImageMetadata(file);
      
      // 读取为 Data URL
      const dataUrl = await readFileAsDataURL(file);
      
      const fileInfo: UploadFileInfo = {
        file,
        previewUrl: dataUrl,
        width: metadata.width || 0,
        height: metadata.height || 0,
      };
      
      setUploadedFile(fileInfo);
      setPreviewState(prev => ({ ...prev, error: null }));
      
      // 立即触发预览生成，传入 fileInfo 避免时序问题
      generatePreview(true, fileInfo);
    } catch (error) {
      setPreviewState(prev => ({
        ...prev,
        error: {
          type: 'IMAGE_LOAD_FAILED',
          message: '图片加载失败',
          details: error instanceof Error ? error.message : undefined,
          retryable: true,
        },
      }));
    }
  };

  // 拖拽处理
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileUpload(file);
    }
  };

  // ===== 缩放控制 =====

  const handleZoomIn = () => {
    setZoom(prev => ({
      ...prev,
      scale: Math.min(prev.scale + PREVIEW_CONFIG.ZOOM_RANGE.step, PREVIEW_CONFIG.ZOOM_RANGE.max),
    }));
  };

  const handleZoomOut = () => {
    setZoom(prev => ({
      ...prev,
      scale: Math.max(prev.scale - PREVIEW_CONFIG.ZOOM_RANGE.step, PREVIEW_CONFIG.ZOOM_RANGE.min),
    }));
  };

  const handleResetZoom = () => {
    setZoom({
      scale: 1,
      position: { x: 0, y: 0 },
      isDragging: false,
    });
  };

  // ===== 渲染 =====

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 头部工具栏 */}
      <div className="p-4 border-b space-y-3">
        {/* 标题和刷新 */}
        <div className="flex items-center justify-between">
          <h3 className="font-medium">实时预览</h3>
          <div className="flex items-center gap-1">
            {/* 显示模式切换 */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setDisplayMode(prev => 
                      prev === 'image_only' ? 'image_with_bboxes' : 'image_only'
                    )}
                  >
                    {displayMode === 'image_only' ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{displayMode === 'image_only' ? '显示标注框' : '仅显示图片'}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* 刷新按钮 */}
            <Button
              variant="outline"
              size="sm"
              disabled={previewState.isLoading || pipelineConfig.length === 0}
              onClick={() => {
                clearPreviewCache();
                generatePreview(true);
              }}
            >
              <RefreshCw className={`h-4 w-4 mr-1 ${previewState.isLoading ? 'animate-spin' : ''}`} />
              刷新
            </Button>
          </div>
        </div>

        {/* 样本选择 */}
        <div className="space-y-2">
          <Label className="text-xs text-gray-500">预览样本</Label>
          <Select 
            value={sampleType} 
            onValueChange={(v) => setSampleType(v as PreviewSampleType)}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="dataset">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4" />
                  数据集样本
                </div>
              </SelectItem>
              <SelectItem value="upload">
                <div className="flex items-center gap-2">
                  <Upload className="h-4 w-4" />
                  本地上传
                </div>
              </SelectItem>
            </SelectContent>
          </Select>

          {/* 数据集图片选择 */}
          {sampleType === 'dataset' && sampleImages.length > 0 && (
            <Select 
              value={selectedImageId} 
              onValueChange={(id) => {
                setSelectedImageId(id);
                // 同步更新 ref，确保 generatePreview 能获取到新值
                selectedImageIdRef.current = id;
                // 选择图片后立即触发预览
                if (pipelineConfig.length > 0) {
                  setTimeout(() => generatePreview(true), 0);
                }
              }}
            >
              <SelectTrigger className="w-full text-xs">
                <SelectValue placeholder="选择图片" />
              </SelectTrigger>
              <SelectContent>
                {sampleImages.map(img => (
                  <SelectItem key={img.id} value={img.id} className="text-xs">
                    {img.filename}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {sampleType === 'dataset' && sampleImages.length === 0 && (
            <div className="text-xs text-gray-400 py-2">
              暂无样本图片
            </div>
          )}
        </div>

        {/* 缩放控制 */}
        {previewState.result && (
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleZoomOut}>
              <ZoomOut className="h-4 w-4" />
            </Button>
            <Slider
              value={[zoom.scale]}
              min={PREVIEW_CONFIG.ZOOM_RANGE.min}
              max={PREVIEW_CONFIG.ZOOM_RANGE.max}
              step={PREVIEW_CONFIG.ZOOM_RANGE.step}
              onValueChange={([v]) => setZoom(prev => ({ ...prev, scale: v }))}
              className="flex-1"
            />
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={handleZoomIn}>
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleResetZoom}>
              {Math.round(zoom.scale * 100)}%
            </Button>
          </div>
        )}
      </div>

      {/* 预览内容区 */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {/* 加载进度 */}
          {previewState.isLoading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>正在生成预览...</span>
                <span>{previewState.progress}%</span>
              </div>
              <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${previewState.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* 错误提示 */}
          {previewState.error && (
            <Alert variant="destructive" className="animate-in fade-in">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>预览失败</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>{previewState.error.message}</p>
                {previewState.error.details && (
                  <p className="text-xs text-gray-500">{previewState.error.details}</p>
                )}
                <div className="flex gap-2 mt-2">
                  {previewState.error.retryable && (
                    <Button 
                      size="sm" 
                      variant="outline" 
                      onClick={() => generatePreview(true)}
                    >
                      <RotateCcw className="h-3 w-3 mr-1" />
                      重试
                    </Button>
                  )}
                  <Button 
                    size="sm" 
                    variant="ghost" 
                    onClick={() => setPreviewState(prev => ({ ...prev, error: null }))}
                  >
                    忽略
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {/* 空状态 - 本地上传区域 */}
          {sampleType === 'upload' && !uploadedFile && (
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <Upload className="h-12 w-12 mx-auto mb-4 text-gray-400" />
              <p className="text-sm text-gray-600 mb-2">
                拖拽图片到此处，或
                <label className="text-blue-500 cursor-pointer hover:underline mx-1">
                  点击上传
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                  />
                </label>
              </p>
              <p className="text-xs text-gray-400">
                支持 JPG、PNG、WebP，最大 {PREVIEW_CONFIG.MAX_FILE_SIZE}MB
              </p>
            </div>
          )}

          {/* 已上传文件显示 */}
          {sampleType === 'upload' && uploadedFile && (
            <div className="flex items-center gap-2 p-2 bg-gray-50 rounded text-sm">
              <ImageIcon className="h-4 w-4 text-gray-400" />
              <span className="flex-1 truncate">{uploadedFile.file.name}</span>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-6 w-6"
                onClick={() => {
                  setUploadedFile(null);
                  setPreviewState(prev => ({ ...prev, result: null }));
                }}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          )}

          {/* 图片对比 */}
          {previewState.result ? (
            <div className="h-[400px] border rounded-lg overflow-hidden">
              <ImageCompareView
                original={previewState.result.original}
                augmented={previewState.result.augmented}
                displayMode={displayMode}
                zoom={zoom}
                onZoomChange={setZoom}
                selectedBBoxId={selectedBBoxId}
                onBBoxSelect={setSelectedBBoxId}
                classNames={classNames}
                isLoading={previewState.isLoading}
              />
            </div>
          ) : (
            /* 占位状态 */
            <div className="h-[300px] flex flex-col items-center justify-center text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
              {pipelineConfig.length === 0 ? (
                <>
                  <Settings className="h-12 w-12 mb-2" />
                  <p className="text-sm">配置增强流水线后预览</p>
                </>
              ) : previewState.isLoading ? (
                <>
                  <Loader2 className="h-12 w-12 mb-2 animate-spin" />
                  <p className="text-sm">正在生成预览...</p>
                </>
              ) : (
                <>
                  <ImageIcon className="h-12 w-12 mb-2" />
                  <p className="text-sm">点击刷新生成预览</p>
                </>
              )}
            </div>
          )}

          {/* 操作统计 */}
          {previewState.result && previewState.result.applied_operations.length > 0 && (
            <div className="p-3 bg-gray-50 rounded-lg">
              <div className="text-xs font-medium text-gray-600 mb-2">应用的操作:</div>
              <div className="flex flex-wrap gap-1">
                {previewState.result.applied_operations.map((op, index) => (
                  <span
                    key={index}
                    className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded"
                  >
                    {op}
                  </span>
                ))}
              </div>
              {previewState.result.cache_hit && (
                <span className="text-xs text-gray-400 ml-2">(缓存)</span>
              )}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

export default PreviewPanel;
