/**
 * 执行面板组件
 * 
 * 配置增强任务参数并执行
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Play, Pause, RotateCcw, Check, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { useAugmentationStore } from '@/stores/augmentationStore';
import { JOB_STATUS_LABELS, JOB_STATUS_COLORS } from '@/types/augmentation';
import type {
  AugmentationOperation,
} from '@/types/augmentation';
import type { Dataset } from '@/types';

interface ExecutionPanelProps {
  dataset: Dataset;
  pipelineConfig: AugmentationOperation[];
}

export const ExecutionPanel: React.FC<ExecutionPanelProps> = ({
  dataset,
  pipelineConfig,
}) => {
  const [newDatasetName, setNewDatasetName] = useState(
    `${dataset.name}_augmented`
  );
  const [augmentationFactor, setAugmentationFactor] = useState(2);
  const [targetSplit, setTargetSplit] = useState<'train' | 'val' | 'test' | 'all'>('train');
  const [includeOriginal, setIncludeOriginal] = useState(true);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [progressPolling, setProgressPolling] = useState(false);

  const {
    createJob,
    controlJob,
    fetchJobProgress,
    currentJob,
    jobsLoading,
  } = useAugmentationStore();

  // 轮询任务进度
  useEffect(() => {
    if (!currentJob || !progressPolling) return;

    if (['completed', 'failed', 'cancelled'].includes(currentJob.status)) {
      setProgressPolling(false);
      return;
    }

    const interval = setInterval(async () => {
      try {
        await fetchJobProgress(currentJob.id);
      } catch (error) {
        console.error('获取进度失败:', error);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [currentJob, progressPolling, fetchJobProgress]);

  // 开始增强
  const handleStart = useCallback(async () => {
    setShowConfirmDialog(false);

    try {
      await createJob({
        name: `增强任务 - ${dataset.name}`,
        source_dataset_id: dataset.id,
        pipeline_config: pipelineConfig,
        augmentation_factor: augmentationFactor,
        new_dataset_name: newDatasetName,
        target_split: targetSplit,
        include_original: includeOriginal,
      });

      setProgressPolling(true);
    } catch (error) {
      console.error('创建任务失败:', error);
    }
  }, [
    dataset.id,
    dataset.name,
    pipelineConfig,
    augmentationFactor,
    newDatasetName,
    targetSplit,
    includeOriginal,
    createJob,
  ]);

  // 控制任务
  const handleControl = useCallback(
    async (action: 'pause' | 'resume' | 'cancel') => {
      if (!currentJob) return;

      try {
        await controlJob(currentJob.id, action);

        if (action === 'pause') {
          setProgressPolling(false);
        } else if (action === 'resume') {
          setProgressPolling(true);
        } else if (action === 'cancel') {
          setProgressPolling(false);
        }
      } catch (error) {
        console.error('控制任务失败:', error);
      }
    },
    [currentJob, controlJob]
  );

  // 格式化时间
  const formatTime = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}秒`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}分钟`;
    return `${Math.round(seconds / 3600)}小时`;
  };

  const canExecute =
    pipelineConfig.length > 0 && newDatasetName.trim() && !currentJob;

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 头部 */}
      <div className="p-4 border-b">
        <h3 className="font-medium">执行配置</h3>
        <p className="text-xs text-gray-500">配置增强任务参数</p>
      </div>

      {/* 配置表单 - 可滚动 */}
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-6">
          {/* 源数据集 */}
          <div className="space-y-2">
            <Label className="text-sm">源数据集</Label>
            <div className="p-2 bg-gray-50 rounded border text-sm">
              {dataset.name}
            </div>
          </div>

          {/* 新数据集名称 */}
          <div className="space-y-2">
            <Label className="text-sm">新数据集名称</Label>
            <Input
              value={newDatasetName}
              onChange={(e) => setNewDatasetName(e.target.value)}
              placeholder="输入新数据集名称"
              disabled={!!currentJob}
            />
          </div>

          {/* 目标划分 */}
          <div className="space-y-2">
            <Label className="text-sm">目标划分</Label>
            <Select
              value={targetSplit}
              onValueChange={(v) => setTargetSplit(v as 'train' | 'val' | 'test' | 'all')}
              disabled={!!currentJob}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="train">仅训练集 (推荐)</SelectItem>
                <SelectItem value="val">仅验证集</SelectItem>
                <SelectItem value="test">仅测试集</SelectItem>
                <SelectItem value="all">全部 (不推荐)</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-gray-500">
              建议仅增强训练集，避免数据泄露
            </p>
          </div>

          {/* 增强倍数 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-sm">增强倍数</Label>
              <span className="text-sm text-gray-500">{augmentationFactor}x</span>
            </div>
            <Slider
              value={[augmentationFactor]}
              min={1}
              max={10}
              step={1}
              onValueChange={([v]) => setAugmentationFactor(v)}
              disabled={!!currentJob}
            />
            <p className="text-xs text-gray-500">
              每张原始图像将生成 {augmentationFactor} 张增强图像
            </p>
          </div>

          {/* 包含原图 */}
          <div className="flex items-center justify-between p-3 border rounded-lg">
            <div className="space-y-0.5">
              <Label className="text-sm">包含原始图像</Label>
              <p className="text-xs text-gray-500">
                新数据集同时包含原图和增强后的图像
              </p>
            </div>
            <Switch
              checked={includeOriginal}
              onCheckedChange={setIncludeOriginal}
              disabled={!!currentJob}
            />
          </div>

          {/* 预计信息 */}
          {!currentJob && (
            <div className="p-3 bg-blue-50 rounded-lg space-y-1">
              <div className="flex items-center gap-2 text-blue-700 text-sm">
                <span className="font-medium">预计生成:</span>
                <span>
                  {targetSplit === 'all' ? dataset.total_images : Math.floor(dataset.total_images * (targetSplit === 'train' ? 0.7 : targetSplit === 'val' ? 0.2 : 0.1))} 
                  张原图
                  {augmentationFactor > 0 && ` + ${(targetSplit === 'all' ? dataset.total_images : Math.floor(dataset.total_images * (targetSplit === 'train' ? 0.7 : targetSplit === 'val' ? 0.2 : 0.1))) * augmentationFactor} 张增强图`}
                </span>
              </div>
              <div className="text-xs text-blue-600">
                目标: {targetSplit === 'train' ? '训练集' : targetSplit === 'val' ? '验证集' : targetSplit === 'test' ? '测试集' : '全部'} 
                {includeOriginal ? '(含原图)' : '(仅增强图)'}
              </div>
            </div>
          )}

          {/* 任务状态 */}
          {currentJob && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">任务状态</span>
                <span
                  className={`px-2 py-0.5 rounded-full text-xs text-white ${
                    JOB_STATUS_COLORS[currentJob.status]
                  }`}
                >
                  {JOB_STATUS_LABELS[currentJob.status]}
                </span>
              </div>

              {/* 进度条 */}
              <div className="space-y-1">
                <Progress value={currentJob.progress} className="h-2" />
                <div className="flex items-center justify-between text-xs text-gray-500">
                  <span>{currentJob.progress.toFixed(1)}%</span>
                  <span>
                    {currentJob.generated_count} / {currentJob.total_count} 张
                  </span>
                </div>
              </div>

              {/* 统计信息 */}
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-xs text-gray-500">已生成</div>
                  <div className="font-medium">{currentJob.generated_count} 张</div>
                </div>
                <div className="p-2 bg-gray-50 rounded">
                  <div className="text-xs text-gray-500">执行时间</div>
                  <div className="font-medium">
                    {currentJob.timing_stats
                      ? formatTime(currentJob.timing_stats.duration_seconds)
                      : '-'}
                  </div>
                </div>
              </div>

              {/* 错误信息 */}
              {currentJob.error_message && (
                <div className="p-3 bg-red-50 text-red-700 text-sm rounded">
                  {currentJob.error_message}
                </div>
              )}
            </div>
          )}
        </div>
      </ScrollArea>

      {/* 操作按钮 */}
      <div className="p-4 border-t space-y-2">
        {!currentJob ? (
          <Button
            className="w-full"
            disabled={!canExecute || jobsLoading}
            onClick={() => setShowConfirmDialog(true)}
          >
            {jobsLoading ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Play className="h-4 w-4 mr-1" />
            )}
            开始增强
          </Button>
        ) : currentJob.status === 'running' ? (
          <div className="flex gap-2">
            <Button
              variant="outline"
              className="flex-1"
              onClick={() => handleControl('pause')}
            >
              <Pause className="h-4 w-4 mr-1" />
              暂停
            </Button>
            <Button
              variant="destructive"
              className="flex-1"
              onClick={() => handleControl('cancel')}
            >
              取消
            </Button>
          </div>
        ) : currentJob.status === 'paused' ? (
          <div className="flex gap-2">
            <Button
              className="flex-1"
              onClick={() => handleControl('resume')}
            >
              <Play className="h-4 w-4 mr-1" />
              继续
            </Button>
            <Button
              variant="destructive"
              className="flex-1"
              onClick={() => handleControl('cancel')}
            >
              取消
            </Button>
          </div>
        ) : (
          <Button
            variant="outline"
            className="w-full"
            onClick={() => window.location.reload()}
          >
            <RotateCcw className="h-4 w-4 mr-1" />
            新建任务
          </Button>
        )}
      </div>

      {/* 确认对话框 */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认开始增强？</DialogTitle>
            <DialogDescription asChild>
              <div className="space-y-2">
                <p>请确认以下配置：</p>
                <ul className="text-sm space-y-1 list-disc list-inside">
                  <li>源数据集: {dataset.name}</li>
                  <li>新数据集: {newDatasetName}</li>
                  <li>目标划分: {targetSplit === 'train' ? '训练集' : targetSplit === 'val' ? '验证集' : targetSplit === 'test' ? '测试集' : '全部'}</li>
                  <li>增强倍数: {augmentationFactor}x</li>
                  <li>包含原图: {includeOriginal ? '是' : '否'}</li>
                </ul>
                <p className="text-yellow-600">
                  增强过程可能需要较长时间，请勿关闭页面。
                </p>
              </div>
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowConfirmDialog(false)}
            >
              取消
            </Button>
            <Button onClick={handleStart}>
              <Check className="h-4 w-4 mr-1" />
              确认开始
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ExecutionPanel;
