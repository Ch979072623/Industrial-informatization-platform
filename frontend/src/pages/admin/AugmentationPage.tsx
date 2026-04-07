/**
 * 数据增强配置页面
 * 
 * 三栏布局：左侧操作列表、中间流水线编排、右侧预览与执行
 */
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Save, FolderOpen, HelpCircle, Loader2, Database, ArrowRight, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { OperationList } from '@/components/augmentation/OperationList';
import { PipelineEditor } from '@/components/augmentation/PipelineEditor';
import { PreviewPanel } from '@/components/augmentation/PreviewPanel';
import { ExecutionPanel } from '@/components/augmentation/ExecutionPanel';
import { useAugmentationStore } from '@/stores/augmentationStore';
import { datasetApi } from '@/services/api';
import type { Dataset } from '@/types';
import type { AugmentationOperation, AugmentationOperationDefinition } from '@/types/augmentation';

const AugmentationPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const datasetId = searchParams.get('dataset');

  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateDescription, setTemplateDescription] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  
  // 数据集选择
  const [showDatasetSelector, setShowDatasetSelector] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetsLoading, setDatasetsLoading] = useState(false);
  const [datasetSearch, setDatasetSearch] = useState('');

  const {
    operations,
    categories,
    pipeline,
    templates,
    currentJob,
    operationsLoading,
    fetchOperations,
    fetchTemplates,
    createTemplate,
    addToPipeline,
    updatePipelineItem,
    removeFromPipeline,
    movePipelineItem,
    clearPipeline,
    loadTemplateToPipeline,
    setPipeline,
  } = useAugmentationStore();

  // 加载数据
  useEffect(() => {
    fetchOperations();
    fetchTemplates();
  }, [fetchOperations, fetchTemplates]);

  // 监听 pipeline 变化
  // useEffect(() => {
  //   console.log('[AugmentationPage] Pipeline changed:', pipeline);
  // }, [pipeline]);

  // 加载数据集信息
  useEffect(() => {
    if (!datasetId) {
      // 如果没有数据集ID，自动打开选择器
      setShowDatasetSelector(true);
      loadDatasets();
      return;
    }

    const loadDataset = async () => {
      setDatasetLoading(true);
      try {
        const response = await datasetApi.getDataset(datasetId);
        if (response.data.success) {
          setDataset(response.data.data);
        }
      } catch (error) {
        console.error('加载数据集失败:', error);
      } finally {
        setDatasetLoading(false);
      }
    };

    loadDataset();
  }, [datasetId]);

  // 加载数据集列表
  const loadDatasets = async () => {
    setDatasetsLoading(true);
    try {
      const response = await datasetApi.getDatasets({ page: 1, page_size: 100 });
      if (response.data.success) {
        setDatasets(response.data.data.items || []);
      }
    } catch (error) {
      console.error('加载数据集列表失败:', error);
    } finally {
      setDatasetsLoading(false);
    }
  };

  // 选择数据集
  const handleSelectDataset = (id: string) => {
    setSearchParams({ dataset: id });
    setShowDatasetSelector(false);
  };

  // 过滤数据集
  const filteredDatasets = datasets.filter(d => 
    d.name.toLowerCase().includes(datasetSearch.toLowerCase()) ||
    (d.description && d.description.toLowerCase().includes(datasetSearch.toLowerCase()))
  );

  // 处理拖拽
  const handleDragStart = (operation: AugmentationOperationDefinition) => {
    // 拖拽开始时记录操作类型
  };

  // 处理拖拽放置
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const data = e.dataTransfer.getData('application/json');
    if (data) {
      try {
        const operation = JSON.parse(data) as AugmentationOperationDefinition;
        addToPipeline(operation);
      } catch (error) {
        console.error('解析拖拽数据失败:', error);
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };

  // 使用 useCallback 稳定回调引用
  const handlePipelineChange = useCallback((newPipeline: AugmentationOperation[]) => {
    // console.log('[AugmentationPage] handlePipelineChange called with length:', newPipeline.length);
    setPipeline(newPipeline);
  }, [setPipeline]);

  // 保存模板
  const handleSaveTemplate = async () => {
    if (!templateName.trim() || pipeline.length === 0) return;

    setIsSaving(true);
    try {
      await createTemplate({
        name: templateName,
        description: templateDescription,
        pipeline_config: pipeline,
      });
      setShowTemplateDialog(false);
      setTemplateName('');
      setTemplateDescription('');
    } catch (error) {
      console.error('保存模板失败:', error);
    } finally {
      setIsSaving(false);
    }
  };

  // 加载模板
  const handleLoadTemplate = (templateId: string) => {
    const template = templates.find((t) => t.id === templateId);
    if (template) {
      loadTemplateToPipeline(template);
    }
  };

  if (datasetLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  // 数据集选择对话框
  if (!datasetId || !dataset) {
    return (
      <div className="flex flex-col h-full bg-gray-50">
        {/* 顶部工具栏 */}
        <div className="flex items-center justify-between px-6 py-3 bg-white border-b">
          <div>
            <h1 className="text-lg font-medium">数据增强配置</h1>
            <p className="text-sm text-gray-500">请先选择一个数据集</p>
          </div>
        </div>

        <div className="flex-1 p-6">
          <div className="max-w-4xl mx-auto">
            {/* 操作按钮 */}
            <div className="flex gap-4 mb-6">
              <Card className="flex-1 cursor-pointer hover:shadow-lg transition-shadow" onClick={() => { setShowDatasetSelector(true); loadDatasets(); }}>
                <CardContent className="flex flex-col items-center justify-center p-8">
                  <Database className="h-12 w-12 text-blue-500 mb-4" />
                  <CardTitle className="text-lg mb-2">选择现有数据集</CardTitle>
                  <p className="text-sm text-gray-500 text-center">
                    从已上传的数据集中选择一个进行增强
                  </p>
                </CardContent>
              </Card>

              <Card className="flex-1 cursor-pointer hover:shadow-lg transition-shadow" onClick={() => navigate('/admin/datasets/upload')}>
                <CardContent className="flex flex-col items-center justify-center p-8">
                  <FolderOpen className="h-12 w-12 text-green-500 mb-4" />
                  <CardTitle className="text-lg mb-2">上传新数据集</CardTitle>
                  <p className="text-sm text-gray-500 text-center">
                    上传新的数据集并开始增强
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* 最近的数据集 */}
            {datasets.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">最近的数据集</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {datasets.slice(0, 6).map((d) => (
                      <div
                        key={d.id}
                        className="p-4 border rounded-lg cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-colors"
                        onClick={() => handleSelectDataset(d.id)}
                      >
                        <div className="font-medium truncate">{d.name}</div>
                        <div className="text-sm text-gray-500">
                          {d.total_images} 张图像 · {d.format}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        {/* 数据集选择对话框 */}
        <Dialog open={showDatasetSelector} onOpenChange={setShowDatasetSelector}>
          <DialogContent className="max-w-3xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle>选择数据集</DialogTitle>
              <DialogDescription>
                选择要进行数据增强的数据集
              </DialogDescription>
            </DialogHeader>
            
            {/* 搜索 */}
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
              <Input
                placeholder="搜索数据集..."
                value={datasetSearch}
                onChange={(e) => setDatasetSearch(e.target.value)}
                className="pl-9"
              />
            </div>

            {/* 数据集列表 */}
            <ScrollArea className="h-[400px]">
              {datasetsLoading ? (
                <div className="flex items-center justify-center h-32">
                  <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
                </div>
              ) : filteredDatasets.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  <Database className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                  <p>没有找到数据集</p>
                  <Button 
                    variant="outline" 
                    className="mt-2"
                    onClick={() => navigate('/admin/datasets/upload')}
                  >
                    上传数据集
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  {filteredDatasets.map((d) => (
                    <div
                      key={d.id}
                      className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50 cursor-pointer"
                      onClick={() => handleSelectDataset(d.id)}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">{d.name}</div>
                        <div className="text-sm text-gray-500">
                          {d.total_images} 张图像 · {d.format} · {d.class_names?.length || 0} 个类别
                        </div>
                        {d.description && (
                          <div className="text-xs text-gray-400 truncate mt-1">
                            {d.description}
                          </div>
                        )}
                      </div>
                      <ArrowRight className="h-5 w-5 text-gray-400" />
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>

            <DialogFooter>
              <Button variant="outline" onClick={() => setShowDatasetSelector(false)}>
                取消
              </Button>
              <Button onClick={() => navigate('/admin/datasets')}>
                管理数据集
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  const isExecuting = currentJob && ['running', 'pending'].includes(currentJob.status);

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* 顶部工具栏 */}
      <div className="flex items-center justify-between px-6 py-3 bg-white border-b">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-lg font-medium">数据增强配置</h1>
            <p className="text-sm text-gray-500">数据集: {dataset.name}</p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            disabled={isExecuting}
            onClick={() => { setShowDatasetSelector(true); loadDatasets(); }}
          >
            <Database className="h-4 w-4 mr-1" />
            更换数据集
          </Button>
        </div>
        <div className="flex items-center gap-2">
          {/* 加载模板 */}
          {templates.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">加载模板:</span>
              <select
                className="text-sm border rounded px-2 py-1"
                onChange={(e) => handleLoadTemplate(e.target.value)}
                value=""
                disabled={isExecuting}
              >
                <option value="">选择模板...</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} {t.is_preset ? '(预设)' : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* 保存模板 */}
          <Button
            variant="outline"
            size="sm"
            disabled={pipeline.length === 0 || isExecuting}
            onClick={() => setShowTemplateDialog(true)}
          >
            <Save className="h-4 w-4 mr-1" />
            保存模板
          </Button>

          {/* 帮助 */}
          <Button variant="ghost" size="icon">
            <HelpCircle className="h-5 w-5" />
          </Button>
        </div>
      </div>

      {/* 三栏布局 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧：操作列表 */}
        <div className="w-64 flex-shrink-0 border-r bg-white">
          <OperationList
            operations={operations}
            categories={categories}
            onDragStart={handleDragStart}
          />
        </div>

        {/* 中间：流水线编排 */}
        <div
          className="flex-1 min-w-0 border-r"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          <PipelineEditor
            pipeline={pipeline}
            operations={operations}
            onPipelineChange={handlePipelineChange}
            disabled={isExecuting}
          />
        </div>

        {/* 右侧：预览与执行 */}
        <div className="w-96 flex-shrink-0 flex flex-col bg-white overflow-y-auto">
          {/* 预览区域 - 自适应高度但有最小高度 */}
          <div className="border-b">
            <PreviewPanel
              dataset={dataset}
              pipelineConfig={pipeline}
              disabled={isExecuting}
            />
          </div>

          {/* 执行区域 - 固定高度 */}
          <div className="h-auto">
            <ExecutionPanel dataset={dataset} pipelineConfig={pipeline} />
          </div>
        </div>
      </div>

      {/* 数据集选择对话框 */}
      <Dialog open={showDatasetSelector} onOpenChange={setShowDatasetSelector}>
        <DialogContent className="max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>选择数据集</DialogTitle>
            <DialogDescription>
              选择要进行数据增强的数据集
            </DialogDescription>
          </DialogHeader>
          
          {/* 搜索 */}
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
            <Input
              placeholder="搜索数据集..."
              value={datasetSearch}
              onChange={(e) => setDatasetSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* 数据集列表 */}
          <ScrollArea className="h-[400px]">
            {datasetsLoading ? (
              <div className="flex items-center justify-center h-32">
                <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              </div>
            ) : filteredDatasets.length === 0 ? (
              <div className="text-center text-gray-500 py-8">
                <Database className="h-12 w-12 mx-auto mb-2 text-gray-300" />
                <p>没有找到数据集</p>
                <Button 
                  variant="outline" 
                  className="mt-2"
                  onClick={() => navigate('/admin/datasets/upload')}
                >
                  上传数据集
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredDatasets.map((d) => (
                  <div
                    key={d.id}
                    className={`flex items-center justify-between p-3 border rounded-lg cursor-pointer transition-colors ${
                      d.id === datasetId ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'
                    }`}
                    onClick={() => handleSelectDataset(d.id)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{d.name}</div>
                      <div className="text-sm text-gray-500">
                        {d.total_images} 张图像 · {d.format} · {d.class_names?.length || 0} 个类别
                      </div>
                      {d.description && (
                        <div className="text-xs text-gray-400 truncate mt-1">
                          {d.description}
                        </div>
                      )}
                    </div>
                    {d.id === datasetId ? (
                      <span className="text-xs text-blue-600 font-medium">当前</span>
                    ) : (
                      <ArrowRight className="h-5 w-5 text-gray-400" />
                    )}
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDatasetSelector(false)}>
              取消
            </Button>
            <Button onClick={() => navigate('/admin/datasets')}>
              管理数据集
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 保存模板对话框 */}
      <Dialog open={showTemplateDialog} onOpenChange={setShowTemplateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>保存为模板</DialogTitle>
            <DialogDescription>
              将当前流水线配置保存为模板，方便下次使用
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>模板名称</Label>
              <Input
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="输入模板名称"
              />
            </div>
            <div className="space-y-2">
              <Label>描述（可选）</Label>
              <Input
                value={templateDescription}
                onChange={(e) => setTemplateDescription(e.target.value)}
                placeholder="输入模板描述"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowTemplateDialog(false)}
            >
              取消
            </Button>
            <Button
              onClick={handleSaveTemplate}
              disabled={!templateName.trim() || isSaving}
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Save className="h-4 w-4 mr-1" />
              )}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AugmentationPage;
