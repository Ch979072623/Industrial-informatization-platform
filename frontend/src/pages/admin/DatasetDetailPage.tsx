import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ThumbnailImage } from '@/components/ui/thumbnail-image';
import { datasetApi } from '@/services/api';
import { DatasetStatisticsCharts } from '@/components/dataset';
import type { Dataset, DatasetImage } from '@/types';
import { cn } from '@/utils/cn';
import {
  ArrowLeft,
  Database,
  Image as ImageIcon,
  Tag,
  Calendar,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Split,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Download,
} from 'lucide-react';

// 统计卡片组件
interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  description?: string;
}

const StatCard = ({ title, value, icon, description }: StatCardProps) => (
  <Card>
    <CardContent className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {description && (
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
          )}
        </div>
        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
          {icon}
        </div>
      </div>
    </CardContent>
  </Card>
);

// 图片预览对话框
interface ImagePreviewDialogProps {
  image: DatasetImage | null;
  datasetId: string;
  open: boolean;
  onClose: () => void;
}

const ImagePreviewDialog = ({ image, datasetId, open, onClose }: ImagePreviewDialogProps) => {
  const [annotatedUrl, setAnnotatedUrl] = useState<string>('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (image && open) {
      setLoading(true);
      datasetApi.getAnnotatedImage(datasetId, image.id)
        .then(response => {
          const url = URL.createObjectURL(response.data);
          setAnnotatedUrl(url);
        })
        .finally(() => setLoading(false));
    }
    return () => {
      if (annotatedUrl) {
        URL.revokeObjectURL(annotatedUrl);
      }
    };
  }, [image, datasetId, open]);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>{image?.filename}</DialogTitle>
        </DialogHeader>
        <div className="flex items-center justify-center bg-muted rounded-lg overflow-hidden min-h-[400px]">
          {loading ? (
            <Loader2 className="h-8 w-8 animate-spin" />
          ) : annotatedUrl ? (
            <img
              src={annotatedUrl}
              alt={image?.filename}
              className="max-w-full max-h-[70vh] object-contain"
            />
          ) : (
            <div className="text-muted-foreground">加载失败</div>
          )}
        </div>
        {image && (
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>尺寸: {image.width} x {image.height}</span>
            <span>划分: {image.split}</span>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export function DatasetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [dataset, setDataset] = useState<Dataset | null>(null);

  const [images, setImages] = useState<DatasetImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  
  // 图片浏览状态
  const [imagePage, setImagePage] = useState(1);
  const [imagePageSize, setImagePageSize] = useState(20);
  const [imageTotal, setImageTotal] = useState(0);
  const [imageFilter, setImageFilter] = useState<string>('all');
  const [selectedImage, setSelectedImage] = useState<DatasetImage | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);

  // 划分状态 (使用整数百分比)
  const [splitRatio, setSplitRatio] = useState<{train: number; val: number; test: number}>({
    train: 70,
    val: 20,
    test: 10,
  });
  const [splitting, setSplitting] = useState(false);
  const [splitSuccess, setSplitSuccess] = useState(false);

  // 转换状态
  const [targetFormat, setTargetFormat] = useState<string>('');
  const [converting, setConverting] = useState(false);

  // 导出状态
  const [exporting, setExporting] = useState(false);
  
  // 错误提示状态
  const [error, setError] = useState<string | null>(null);
  const [splitError, setSplitError] = useState<string | null>(null);
  const [convertError, setConvertError] = useState<string | null>(null);

  const fetchDataset = useCallback(async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const response = await datasetApi.getDataset(id);
      if (response.data.success) {
        setDataset(response.data.data);
      } else {
        setError(response.data.message || '获取数据集详情失败');
      }
    } catch (error: any) {
      console.error('获取数据集详情失败:', error);
      setError(error.response?.data?.message || '获取数据集详情失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }, [id]);



  const fetchImages = useCallback(async () => {
    if (!id) return;
    try {
      const params: any = {
        page: imagePage,
        page_size: imagePageSize,
      };
      if (imageFilter !== 'all') {
        params.split = imageFilter;
      }
      const response = await datasetApi.getDatasetImages(id, params);
      if (response.data.success) {
        setImages(response.data.data.items || []);
        setImageTotal(response.data.data.total || 0);
      }
    } catch (error) {
      console.error('获取图片列表失败:', error);
    }
  }, [id, imagePage, imagePageSize, imageFilter]);

  useEffect(() => {
    fetchDataset();
  }, [fetchDataset]);

  useEffect(() => {
    fetchImages();
  }, [fetchImages]);

  const handleSplit = async () => {
    if (!id) return;
    try {
      setSplitting(true);
      setSplitSuccess(false);
      setSplitError(null);
      // 转换整数百分比为小数比例，并确保总和为1
      const splitData = {
        train_ratio: splitRatio.train / 100,
        val_ratio: splitRatio.val / 100,
        test_ratio: splitRatio.test / 100,
      };
      console.log('执行划分，比例:', splitData, '原始百分比:', splitRatio);
      const response = await datasetApi.splitDataset(id, splitData);
      if (response.data.success) {
        setSplitSuccess(true);
        fetchDataset();
      } else {
        setSplitError(response.data.message || '数据集划分失败');
      }
    } catch (error: any) {
      console.error('划分失败:', error);
      setSplitError(error.response?.data?.message || '数据集划分失败，请稍后重试');
    } finally {
      setSplitting(false);
    }
  };

  const handleConvert = async () => {
    if (!id || !targetFormat) return;
    try {
      setConverting(true);
      setConvertError(null);
      const response = await datasetApi.convertDataset(id, {
        target_format: targetFormat,
        preserve_original: true,
      });
      if (response.data.success) {
        fetchDataset();
      } else {
        setConvertError(response.data.message || '格式转换失败');
      }
    } catch (error: any) {
      console.error('转换失败:', error);
      setConvertError(error.response?.data?.message || '格式转换失败，请稍后重试');
    } finally {
      setConverting(false);
    }
  };

  const handleImageClick = (image: DatasetImage) => {
    setSelectedImage(image);
    setPreviewOpen(true);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('zh-CN');
  };

  const totalPages = Math.ceil(imageTotal / imagePageSize);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!dataset) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>数据集不存在或已被删除</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* 返回按钮 */}
      <Button
        variant="ghost"
        onClick={() => navigate('/admin/datasets')}
        className="-ml-4"
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        返回列表
      </Button>

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

      {/* 页面标题 */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">{dataset.name}</h2>
          <p className="text-muted-foreground mt-1">
            {dataset.description || '暂无描述'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            disabled={exporting}
            onClick={async () => {
              try {
                setExporting(true);
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
              } catch (error) {
                console.error('导出数据集失败:', error);
                alert('导出失败，请重试');
              } finally {
                setExporting(false);
              }
            }}
          >
            {exporting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            {exporting ? '导出中...' : '导出'}
          </Button>
          <span className={cn(
            'px-3 py-1 rounded-full text-sm font-medium flex items-center',
            dataset.format === 'YOLO' && 'bg-blue-100 text-blue-800',
            dataset.format === 'COCO' && 'bg-green-100 text-green-800',
            dataset.format === 'VOC' && 'bg-purple-100 text-purple-800'
          )}>
            {dataset.format}
          </span>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="总图片数"
          value={dataset.total_images}
          icon={<ImageIcon className="h-5 w-5 text-primary" />}
        />
        <StatCard
          title="类别数"
          value={dataset.class_names?.length || 0}
          icon={<Tag className="h-5 w-5 text-primary" />}
          description={dataset.class_names?.join(', ')}
        />
        <StatCard
          title="总标注数"
          value={dataset.total_annotations || 0}
          icon={<Database className="h-5 w-5 text-primary" />}
          description="标注框总数"
        />
        <StatCard
          title="创建时间"
          value={formatDate(dataset.created_at).split(' ')[0]}
          icon={<Calendar className="h-5 w-5 text-primary" />}
        />
      </div>

      {/* 标签页内容 */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4 lg:w-[400px]">
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="statistics">统计图表</TabsTrigger>
          <TabsTrigger value="images">图片浏览</TabsTrigger>
          <TabsTrigger value="settings">设置</TabsTrigger>
        </TabsList>

        {/* 概览标签 */}
        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>基本信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label className="text-muted-foreground">数据集ID</Label>
                  <p className="font-mono text-sm">{dataset.id}</p>
                </div>
                <div className="space-y-1">
                  <Label className="text-muted-foreground">格式</Label>
                  <p>{dataset.format}</p>
                </div>
                <div className="space-y-1">
                  <Label className="text-muted-foreground">存储路径</Label>
                  <p className="font-mono text-sm truncate">{dataset.path}</p>
                </div>
                <div className="space-y-1">
                  <Label className="text-muted-foreground">状态</Label>
                  <p className={cn(
                    'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium',
                    dataset.status === 'ready' && 'bg-green-100 text-green-800',
                    dataset.status === 'processing' && 'bg-yellow-100 text-yellow-800',
                    dataset.status === 'error' && 'bg-red-100 text-red-800'
                  )}>
                    {dataset.status === 'ready' && '就绪'}
                    {dataset.status === 'processing' && '处理中'}
                    {dataset.status === 'error' && '错误'}
                  </p>
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-muted-foreground">类别列表</Label>
                <div className="flex flex-wrap gap-2 mt-2">
                  {dataset.class_names?.map((name, index) => (
                    <span
                      key={index}
                      className="px-2 py-1 bg-muted rounded-md text-sm"
                    >
                      {index}: {name}
                    </span>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

        </TabsContent>

        {/* 统计图表标签 */}
        <TabsContent value="statistics" className="space-y-6">
          {id && <DatasetStatisticsCharts datasetId={id} onRefresh={fetchDataset} />}
        </TabsContent>

        {/* 图片浏览标签 */}
        <TabsContent value="images" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <CardTitle>图片列表</CardTitle>
                  <CardDescription>共 {imageTotal} 张图片</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Select value={imageFilter} onValueChange={setImageFilter}>
                    <SelectTrigger className="w-[120px]">
                      <SelectValue placeholder="筛选" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部</SelectItem>
                      <SelectItem value="train">训练集</SelectItem>
                      <SelectItem value="val">验证集</SelectItem>
                      <SelectItem value="test">测试集</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={String(imagePageSize)} onValueChange={(v) => setImagePageSize(Number(v))}>
                    <SelectTrigger className="w-[100px]">
                      <SelectValue placeholder="每页" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="20">20条</SelectItem>
                      <SelectItem value="50">50条</SelectItem>
                      <SelectItem value="100">100条</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {/* 图片网格 */}
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                {images.map((image) => (
                  <div
                    key={image.id}
                    className="group relative aspect-square bg-muted rounded-lg overflow-hidden cursor-pointer hover:ring-2 hover:ring-primary transition-all"
                    onClick={() => handleImageClick(image)}
                  >
                    <ThumbnailImage
                      datasetId={id || ''}
                      imageId={image.id}
                      alt={image.filename}
                      width={200}
                      height={200}
                      className="w-full h-full object-cover"
                      lazy={true}
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
                    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <p className="text-white text-xs truncate">{image.filename}</p>
                      <p className="text-white/80 text-xs">{image.split}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* 分页 */}
              {totalPages > 1 && (
                <div className="flex items-center justify-center gap-4 mt-6">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setImagePage(p => Math.max(1, p - 1))}
                    disabled={imagePage === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    {imagePage} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setImagePage(p => Math.min(totalPages, p + 1))}
                    disabled={imagePage === totalPages}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 设置标签 */}
        <TabsContent value="settings" className="space-y-6">
          {/* 数据集划分 */}
          <Card>
            <CardHeader>
              <CardTitle>数据集划分</CardTitle>
              <CardDescription>设置训练/验证/测试集的比例</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {splitSuccess && (
                <Alert className="border-green-500 text-green-700">
                  <CheckCircle2 className="h-4 w-4" />
                  <AlertDescription>划分成功！</AlertDescription>
                </Alert>
              )}

              {splitError && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="flex items-center justify-between">
                    <span>{splitError}</span>
                    <Button variant="outline" size="sm" onClick={() => setSplitError(null)}>
                      关闭
                    </Button>
                  </AlertDescription>
                </Alert>
              )}

              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>训练集比例</Label>
                    <span className="text-sm text-muted-foreground">{splitRatio.train}%</span>
                  </div>
                  <Input
                    type="range"
                    min="0"
                    max="100"
                    value={splitRatio.train}
                    onChange={(e) => {
                      const train = Number(e.target.value);
                      const remaining = 100 - train;
                      // 剩余比例平均分配给 val 和 test
                      setSplitRatio({
                        train,
                        val: Math.round(remaining / 2),
                        test: Math.round(remaining / 2),
                      });
                    }}
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>验证集比例</Label>
                    <span className="text-sm text-muted-foreground">{splitRatio.val}%</span>
                  </div>
                  <Input
                    type="range"
                    min="0"
                    max="100"
                    value={splitRatio.val}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      // 确保三个比例之和为100
                      const maxVal = 100 - splitRatio.train;
                      const clampedVal = Math.min(val, maxVal);
                      setSplitRatio({
                        train: splitRatio.train,
                        val: clampedVal,
                        test: 100 - splitRatio.train - clampedVal,
                      });
                    }}
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>测试集比例</Label>
                    <span className="text-sm text-muted-foreground">{splitRatio.test}%</span>
                  </div>
                  <Input
                    type="range"
                    min="0"
                    max="100"
                    value={splitRatio.test}
                    disabled
                  />
                </div>
              </div>

              <Button
                onClick={handleSplit}
                disabled={splitting}
                className="w-full"
              >
                {splitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    划分中...
                  </>
                ) : (
                  <>
                    <Split className="mr-2 h-4 w-4" />
                    执行划分
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* 格式转换 */}
          <Card>
            <CardHeader>
              <CardTitle>格式转换</CardTitle>
              <CardDescription>将数据集转换为其他格式</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {convertError && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription className="flex items-center justify-between">
                    <span>{convertError}</span>
                    <Button variant="outline" size="sm" onClick={() => setConvertError(null)}>
                      关闭
                    </Button>
                  </AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label>目标格式</Label>
                <Select value={targetFormat} onValueChange={setTargetFormat}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择目标格式" />
                  </SelectTrigger>
                  <SelectContent>
                    {dataset.format !== 'YOLO' && <SelectItem value="YOLO">YOLO</SelectItem>}
                    {dataset.format !== 'COCO' && <SelectItem value="COCO">COCO</SelectItem>}
                    {dataset.format !== 'VOC' && <SelectItem value="VOC">VOC</SelectItem>}
                  </SelectContent>
                </Select>
              </div>

              <Button
                onClick={handleConvert}
                disabled={!targetFormat || converting}
                className="w-full"
              >
                {converting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    转换中...
                  </>
                ) : (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4" />
                    开始转换
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 图片预览对话框 */}
      <ImagePreviewDialog
        image={selectedImage}
        datasetId={id || ''}
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
      />
    </div>
  );
}

export default DatasetDetailPage;
