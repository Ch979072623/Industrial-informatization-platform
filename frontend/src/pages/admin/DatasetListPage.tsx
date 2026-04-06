import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { datasetApi } from '@/services/api';
import type { Dataset, DatasetCardInfo, DatasetListQuery } from '@/types';
import { 
  Plus, 
  Search, 
  Trash2, 
  Database, 
  Image as ImageIcon, 
  Tag,
  Calendar,
  AlertTriangle,
  FileArchive,
  Loader2,
  Edit3,
  Eye,
  BarChart3,
  Upload,
  X,
  Check,
  AlertCircle,
  FolderOpen,
  Download
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { ThumbnailImage } from '@/components/ui/thumbnail-image';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { cn } from '@/utils/cn';

// 数据集卡片组件
interface DatasetCardProps {
  dataset: DatasetCardInfo;
  onClick: () => void;
  onDelete: (e: React.MouseEvent) => void;
  onEditLabels: (e: React.MouseEvent) => void;
  onExport: (e: React.MouseEvent) => void;
}

const DatasetCard = ({ dataset, onClick, onDelete, onEditLabels, onExport }: DatasetCardProps) => {
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getFormatColor = (format: string) => {
    switch (format.toUpperCase()) {
      case 'YOLO':
        return 'bg-blue-100 text-blue-800';
      case 'COCO':
        return 'bg-green-100 text-green-800';
      case 'VOC':
        return 'bg-purple-100 text-purple-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  // 获取预览图片（最多显示4张）
  const previewImages = dataset.preview_images?.slice(0, 4) || [];
  const hasPreview = previewImages.length > 0;

  return (
    <Card className="group hover:shadow-lg transition-all duration-300 overflow-hidden flex flex-col">
      {/* 预览图片网格 */}
      <div 
        className="relative cursor-pointer"
        onClick={onClick}
      >
        {hasPreview ? (
          <div className="grid grid-cols-2 gap-0.5 aspect-video bg-muted">
            {previewImages.map((img, idx) => (
              <div key={img.id} className="relative overflow-hidden">
                <ThumbnailImage
                  datasetId={dataset.id}
                  imageId={img.id}
                  alt={img.filename}
                  width={200}
                  height={200}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  lazy={true}
                />
                {/* 显示更多图片提示 */}
                {idx === 3 && dataset.preview_images && dataset.preview_images.length > 4 && (
                  <div className="absolute inset-0 bg-black/60 flex items-center justify-center text-white text-sm font-medium">
                    +{dataset.preview_images.length - 4}
                  </div>
                )}
              </div>
            ))}
            {/* 填充空位 */}
            {previewImages.length < 4 && 
              Array(4 - previewImages.length).fill(0).map((_, idx) => (
                <div key={`empty-${idx}`} className="bg-muted flex items-center justify-center">
                  <ImageIcon className="h-6 w-6 text-muted-foreground/30" />
                </div>
              ))
            }
          </div>
        ) : (
          <div className="aspect-video bg-muted flex items-center justify-center">
            <FileArchive className="h-16 w-16 text-muted-foreground/30" />
          </div>
        )}
        
        {/* 格式标签 */}
        <div className="absolute top-2 right-2">
          <span className={cn(
            'px-2 py-1 rounded-md text-xs font-medium shadow-sm',
            getFormatColor(dataset.format)
          )}>
            {dataset.format}
          </span>
        </div>
        
        {/* 悬停遮罩 */}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300 pointer-events-none" />
      </div>

      <CardHeader className="pb-2 cursor-pointer" onClick={onClick}>
        <CardTitle className="text-lg truncate">{dataset.name}</CardTitle>
        <CardDescription className="line-clamp-1">
          {dataset.description || '暂无描述'}
        </CardDescription>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col">
        {/* 统计信息 */}
        <div className="grid grid-cols-2 gap-2 text-sm mb-3">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <ImageIcon className="h-4 w-4" />
            <span>{dataset.total_images || 0} 张图片</span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Tag className="h-4 w-4" />
            <span>{dataset.class_count || 0} 个类别</span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Calendar className="h-4 w-4" />
            <span>{formatDate(dataset.created_at)}</span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <BarChart3 className="h-4 w-4" />
            <span>{Object.values(dataset.annotations_per_class || {}).reduce((a, b) => a + b, 0)} 个标注</span>
          </div>
        </div>

        {/* 类别标签 */}
        {dataset.class_names && dataset.class_names.length > 0 && (
          <div className="mb-3">
            <div className="flex flex-wrap gap-1">
              {dataset.class_names.slice(0, 3).map((name, idx) => (
                <span 
                  key={idx}
                  className="px-2 py-0.5 bg-secondary text-secondary-foreground text-xs rounded-full"
                >
                  {name}
                </span>
              ))}
              {dataset.class_names.length > 3 && (
                <span className="px-2 py-0.5 bg-secondary text-secondary-foreground text-xs rounded-full">
                  +{dataset.class_names.length - 3}
                </span>
              )}
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-2 mt-auto pt-3 border-t">
          <Button
            variant="ghost"
            size="sm"
            className="flex-1"
            onClick={(e) => {
              e.stopPropagation();
              onExport(e);
            }}
          >
            <Download className="h-4 w-4 mr-1" />
            导出
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="flex-1"
            onClick={(e) => {
              e.stopPropagation();
              onEditLabels(e);
            }}
          >
            <Edit3 className="h-4 w-4 mr-1" />
            标签
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="flex-1 text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={onDelete}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            删除
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

// 标签编辑对话框
interface LabelEditDialogProps {
  dataset: DatasetCardInfo | null;
  open: boolean;
  onClose: () => void;
  onSave: (classNames: string[], method: 'manual' | 'yaml') => void;
}

const LabelEditDialog = ({ dataset, open, onClose, onSave }: LabelEditDialogProps) => {
  const [activeTab, setActiveTab] = useState<'manual' | 'yaml'>('manual');
  const [classNames, setClassNames] = useState<string[]>(['']);
  const [yamlContent, setYamlContent] = useState('');
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (dataset && open) {
      // 加载标签分析
      loadLabelAnalysis();
    }
  }, [dataset, open]);

  const loadLabelAnalysis = async () => {
    if (!dataset) return;
    try {
      setLoading(true);
      const response = await datasetApi.getDatasetLabels(dataset.id);
      if (response.data.success) {
        const data = response.data.data;
        setAnalysis(data);
        // 初始化类别名称
        if (data.class_names && data.class_names.length > 0) {
          setClassNames(data.class_names);
        } else {
          // 如果没有类别名称，创建默认空列表（根据检测到的类别数量）
          const detectedClasses = Object.keys(data.annotations_per_class || {});
          setClassNames(detectedClasses.length > 0 
            ? detectedClasses 
            : Array(data.class_count || 1).fill('').map((_, i) => `class_${i}`)
          );
        }
        // 如果有YAML配置，显示
        if (data.yaml_config) {
          setYamlContent(JSON.stringify(data.yaml_config, null, 2));
        }
      }
    } catch (error) {
      console.error('加载标签分析失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleAddClass = () => {
    setClassNames([...classNames, '']);
  };

  const handleRemoveClass = (index: number) => {
    setClassNames(classNames.filter((_, i) => i !== index));
  };

  const handleClassNameChange = (index: number, value: string) => {
    const newClassNames = [...classNames];
    newClassNames[index] = value;
    setClassNames(newClassNames);
  };

  const handleSave = () => {
    onSave(classNames, activeTab);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑标签 - {dataset?.name}</DialogTitle>
          <DialogDescription>
            管理数据集的类别名称和标签信息
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        ) : (
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'manual' | 'yaml')}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="manual">
                <Edit3 className="h-4 w-4 mr-2" />
                手动填写
              </TabsTrigger>
              <TabsTrigger value="yaml">
                <Upload className="h-4 w-4 mr-2" />
                YAML配置
              </TabsTrigger>
            </TabsList>

            {/* 标签统计信息 */}
            {analysis && (
              <div className="mt-4 p-4 bg-muted rounded-lg">
                <h4 className="font-medium mb-2">标签统计</h4>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">类别数</span>
                    <p className="text-2xl font-semibold">{analysis.class_count}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">总标注数</span>
                    <p className="text-2xl font-semibold">{analysis.total_annotations}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">YAML文件</span>
                    <p className="text-lg font-semibold">{analysis.has_yaml ? '已存在' : '未创建'}</p>
                  </div>
                </div>
                
                {/* 各类别分布 */}
                {analysis.annotations_per_class && Object.keys(analysis.annotations_per_class).length > 0 && (
                  <div className="mt-4">
                    <h5 className="text-sm font-medium mb-2">标注分布</h5>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {Object.entries(analysis.annotations_per_class).map(([className, count]: [string, any]) => (
                        <div key={className} className="flex justify-between text-sm">
                          <span>{className}</span>
                          <span className="text-muted-foreground">{count} 个</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <TabsContent value="manual" className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>类别名称列表</Label>
                  <Button type="button" variant="outline" size="sm" onClick={handleAddClass}>
                    <Plus className="h-4 w-4 mr-1" />
                    添加类别
                  </Button>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {classNames.map((name, index) => (
                    <div key={index} className="flex gap-2">
                      <span className="flex items-center justify-center w-8 h-10 text-sm text-muted-foreground bg-muted rounded">
                        {index}
                      </span>
                      <Input
                        placeholder={`类别 ${index + 1} 名称`}
                        value={name}
                        onChange={(e) => handleClassNameChange(index, e.target.value)}
                      />
                      {classNames.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRemoveClass(index)}
                        >
                          <X className="h-4 w-4 text-destructive" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="yaml" className="space-y-4">
              <div className="space-y-2">
                <Label>YAML配置内容</Label>
                <Textarea
                  placeholder={`names:\n  0: defect_type_1\n  1: defect_type_2\n  2: defect_type_3\npath: .\ntrain: images/train\nval: images/val`}
                  value={yamlContent}
                  onChange={(e) => setYamlContent(e.target.value)}
                  rows={12}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  支持YOLO格式的data.yaml配置。names字段可以是列表或字典（class_id: class_name）。
                </p>
              </div>
            </TabsContent>
          </Tabs>
        )}

        <div className="flex justify-end gap-2 mt-4">
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSave} disabled={loading}>
            {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            <Check className="h-4 w-4 mr-2" />
            保存
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

// 主页面组件
export function DatasetListPage() {
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState<DatasetCardInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [formatFilter, setFormatFilter] = useState<string>('all');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [datasetToDelete, setDatasetToDelete] = useState<DatasetCardInfo | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [labelEditOpen, setLabelEditOpen] = useState(false);
  const [datasetToEdit, setDatasetToEdit] = useState<DatasetCardInfo | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const fetchDatasets = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params: DatasetListQuery = {
        page: 1,
        page_size: 100,
        keyword: searchTerm || undefined,
        format: formatFilter === 'all' ? undefined : formatFilter,
      };
      
      // 先获取数据集列表
      const response = await datasetApi.getDatasets(params);
      if (response.data.success) {
        const basicDatasets = response.data.data.items || [];
        
        // 然后获取每个数据集的卡片详细信息（包含预览图和标签统计）
        const cardInfoPromises = basicDatasets.map(async (ds: Dataset) => {
          try {
            const cardResponse = await datasetApi.getDatasetCardInfo(ds.id);
            if (cardResponse.data.success) {
              return cardResponse.data.data;
            }
          } catch (error: any) {
            console.error(`获取数据集 ${ds.id} 卡片信息失败:`, error);
          }
          // 如果获取详细信息失败，使用基本信息
          return {
            ...ds,
            class_count: ds.class_names?.length || 0,
            preview_images: [],
            annotations_per_class: {}
          } as DatasetCardInfo;
        });
        
        const datasetsWithInfo = await Promise.all(cardInfoPromises);
        setDatasets(datasetsWithInfo);
      } else {
        setError(response.data.message || '获取数据集列表失败');
      }
    } catch (error: any) {
      console.error('获取数据集列表失败:', error);
      setError(error.response?.data?.message || '获取数据集列表失败，请检查网络连接后重试');
    } finally {
      setLoading(false);
    }
  }, [searchTerm, formatFilter]);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  const handleDeleteClick = (e: React.MouseEvent, dataset: DatasetCardInfo) => {
    e.stopPropagation();
    setDatasetToDelete(dataset);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!datasetToDelete) return;
    
    try {
      setDeleting(true);
      setError(null);
      const response = await datasetApi.deleteDataset(datasetToDelete.id);
      if (response.data.success) {
        setDatasets(prev => prev.filter(d => d.id !== datasetToDelete.id));
        setDeleteDialogOpen(false);
        setDatasetToDelete(null);
      } else {
        setError(response.data.message || '删除数据集失败');
      }
    } catch (error: any) {
      console.error('删除数据集失败:', error);
      setError(error.response?.data?.message || '删除数据集失败，请稍后重试');
    } finally {
      setDeleting(false);
    }
  };

  const handleEditLabels = (e: React.MouseEvent, dataset: DatasetCardInfo) => {
    e.stopPropagation();
    setDatasetToEdit(dataset);
    setLabelEditOpen(true);
  };

  const [exporting, setExporting] = useState(false);

  const handleExport = async (e: React.MouseEvent, dataset: DatasetCardInfo) => {
    e.stopPropagation();
    try {
      setExporting(true);
      setExportError(null);
      const response = await datasetApi.exportDataset(dataset.id, 'original');
      
      // 创建 Blob URL 并触发下载
      const blob = new Blob([response.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${dataset.name}_export.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error: any) {
      console.error('导出数据集失败:', error);
      setExportError(error.response?.data?.message || '导出失败，请稍后重试');
    } finally {
      setExporting(false);
    }
  };

  const handleSaveLabels = async (classNames: string[], method: 'manual' | 'yaml') => {
    if (!datasetToEdit) return;
    
    try {
      if (method === 'manual') {
        // 手动填写，过滤空名称
        const validNames = classNames.filter(n => n.trim());
        await datasetApi.updateDatasetLabels(datasetToEdit.id, {
          class_names: validNames,
          save_to_yaml: true
        });
      } else {
        // YAML配置
        // 这里需要通过表单上传YAML内容
        // 简化处理：直接使用手动填写的方式
        await datasetApi.updateDatasetLabels(datasetToEdit.id, {
          class_names: classNames,
          save_to_yaml: true
        });
      }
      
      // 刷新数据集列表
      await fetchDatasets();
      setLabelEditOpen(false);
      setDatasetToEdit(null);
    } catch (error) {
      console.error('保存标签失败:', error);
    }
  };

  const filteredDatasets = datasets.filter(dataset => {
    const matchesSearch = dataset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (dataset.description?.toLowerCase() || '').includes(searchTerm.toLowerCase());
    const matchesFormat = formatFilter === 'all' || dataset.format.toLowerCase() === formatFilter.toLowerCase();
    return matchesSearch && matchesFormat;
  });

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">数据集管理</h2>
          <p className="text-muted-foreground">
            管理训练数据集，支持 YOLO、COCO、VOC 格式，自动识别标签和预览图片
          </p>
        </div>
        <Button onClick={() => navigate('/admin/datasets/upload')}>
          <Plus className="mr-2 h-4 w-4" />
          上传数据集
        </Button>
      </div>

      {/* 全局错误提示 */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={() => setError(null)}>
              关闭
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* 导出错误提示 */}
      {exportError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex items-center justify-between">
            <span>{exportError}</span>
            <Button variant="outline" size="sm" onClick={() => setExportError(null)}>
              关闭
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* 搜索和筛选 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索数据集名称或描述..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8"
              />
            </div>
            <Select value={formatFilter} onValueChange={setFormatFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="筛选格式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部格式</SelectItem>
                <SelectItem value="YOLO">YOLO</SelectItem>
                <SelectItem value="COCO">COCO</SelectItem>
                <SelectItem value="VOC">VOC</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* 数据集列表 */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="ml-2 text-muted-foreground">加载中...</span>
        </div>
      ) : filteredDatasets.length === 0 ? (
        <Card className="py-20">
          <CardContent className="text-center">
            <FolderOpen className="h-12 w-12 mx-auto text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-2">
              {searchTerm || formatFilter !== 'all' ? '未找到匹配的数据集' : '暂无数据集'}
            </h3>
            <p className="text-muted-foreground mb-4">
              {searchTerm || formatFilter !== 'all' 
                ? '请尝试调整搜索条件或筛选器'
                : '点击上方按钮上传您的第一个数据集'}
            </p>
            {!searchTerm && formatFilter === 'all' && (
              <Button onClick={() => navigate('/admin/datasets/upload')}>
                <Plus className="mr-2 h-4 w-4" />
                上传数据集
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {filteredDatasets.map((dataset) => (
            <DatasetCard
              key={dataset.id}
              dataset={dataset}
              onClick={() => navigate(`/admin/datasets/${dataset.id}`)}
              onDelete={(e) => handleDeleteClick(e, dataset)}
              onEditLabels={(e) => handleEditLabels(e, dataset)}
              onExport={(e) => handleExport(e, dataset)}
            />
          ))}
        </div>
      )}

      {/* 删除确认对话框 */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              确认删除数据集
            </AlertDialogTitle>
            <AlertDialogDescription>
              您确定要删除数据集 <strong>"{datasetToDelete?.name}"</strong> 吗？
              <br />
              此操作将永久删除该数据集及其所有相关数据。
              <br />
              <span className="text-destructive font-medium">此操作不可撤销。</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              disabled={deleting}
              className="bg-destructive hover:bg-destructive/90"
            >
              {deleting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  删除中...
                </>
              ) : (
                <>
                  <Trash2 className="h-4 w-4 mr-2" />
                  确认删除
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 标签编辑对话框 */}
      <LabelEditDialog
        dataset={datasetToEdit}
        open={labelEditOpen}
        onClose={() => {
          setLabelEditOpen(false);
          setDatasetToEdit(null);
        }}
        onSave={handleSaveLabels}
      />
    </div>
  );
}

export default DatasetListPage;
