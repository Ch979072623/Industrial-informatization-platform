import { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { datasetApi } from '@/services/api';
import { cn } from '@/utils/cn';
import {
  Upload,
  FileArchive,
  X,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ArrowLeft,
  Plus,
  Trash2,
} from 'lucide-react';

interface UploadState {
  status: 'idle' | 'dragging' | 'uploading' | 'processing' | 'success' | 'error';
  progress: number;
  message: string;
}

export function DatasetUploadPage() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [format, setFormat] = useState<string>('auto');
  const [classNames, setClassNames] = useState<string[]>(['']);
  const [uploadState, setUploadState] = useState<UploadState>({
    status: 'idle',
    progress: 0,
    message: '',
  });

  const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500MB

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setUploadState(prev => ({ ...prev, status: 'dragging' }));
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setUploadState(prev => ({ ...prev, status: 'idle' }));
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setUploadState(prev => ({ ...prev, status: 'idle' }));

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      validateAndSetFile(droppedFile);
    }
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      validateAndSetFile(selectedFile);
    }
  }, []);

  const validateAndSetFile = (file: File) => {
    // 检查文件类型
    if (!file.name.endsWith('.zip')) {
      setUploadState({
        status: 'error',
        progress: 0,
        message: '只支持 ZIP 格式的压缩包',
      });
      return;
    }

    // 检查文件大小
    if (file.size > MAX_FILE_SIZE) {
      setUploadState({
        status: 'error',
        progress: 0,
        message: `文件大小超过限制（最大 ${MAX_FILE_SIZE / 1024 / 1024}MB）`,
      });
      return;
    }

    setFile(file);
    // 自动填充名称（去掉扩展名）
    if (!name) {
      setName(file.name.replace('.zip', ''));
    }
    setUploadState({ status: 'idle', progress: 0, message: '' });
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

  const simulateProgress = () => {
    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 15;
      if (progress >= 90) {
        progress = 90;
        clearInterval(interval);
      }
      setUploadState(prev => ({ ...prev, progress: Math.min(progress, 90) }));
    }, 500);
    return interval;
  };

  const handleUpload = async () => {
    if (!file) {
      setUploadState({
        status: 'error',
        progress: 0,
        message: '请选择要上传的文件',
      });
      return;
    }

    if (!name.trim()) {
      setUploadState({
        status: 'error',
        progress: 0,
        message: '请输入数据集名称',
      });
      return;
    }

    try {
      setUploadState({ status: 'uploading', progress: 0, message: '正在上传...' });
      const progressInterval = simulateProgress();

      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', name);
      formData.append('description', description || '');
      formData.append('format', format);
      formData.append('production_line_id', ''); // 可选字段，传空字符串
      
      // 过滤空类别名
      const validClassNames = classNames.filter(c => c.trim());
      if (validClassNames.length > 0) {
        formData.append('class_names', JSON.stringify(validClassNames));
      }

      const response = await datasetApi.uploadDataset(formData);
      clearInterval(progressInterval);

      if (response.data.success) {
        setUploadState({
          status: 'success',
          progress: 100,
          message: '上传成功！正在跳转到数据集列表...',
        });
        setTimeout(() => {
          navigate('/admin/datasets');
        }, 1500);
      } else {
        setUploadState({
          status: 'error',
          progress: 0,
          message: response.data.message || '上传失败',
        });
      }
    } catch (error: any) {
      setUploadState({
        status: 'error',
        progress: 0,
        message: error.response?.data?.message || '上传失败，请稍后重试',
      });
    }
  };

  const clearFile = () => {
    setFile(null);
    setUploadState({ status: 'idle', progress: 0, message: '' });
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* 返回按钮 */}
      <Button
        variant="ghost"
        onClick={() => navigate('/admin/datasets')}
        className="-ml-4"
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        返回列表
      </Button>

      {/* 页面标题 */}
      <div>
        <h2 className="text-3xl font-bold tracking-tight">上传数据集</h2>
        <p className="text-muted-foreground">
          支持 YOLO、COCO、VOC 格式的 ZIP 压缩包
        </p>
      </div>

      {/* 上传区域 */}
      <Card>
        <CardHeader>
          <CardTitle>选择文件</CardTitle>
          <CardDescription>
            拖拽文件到下方区域，或点击选择文件。支持 ZIP 格式，最大 500MB。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'relative border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-all duration-200',
              uploadState.status === 'dragging'
                ? 'border-primary bg-primary/5'
                : 'border-muted-foreground/25 hover:border-muted-foreground/50',
              file && 'border-solid border-border bg-muted/50'
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".zip"
              onChange={handleFileSelect}
              className="hidden"
            />

            {file ? (
              <div className="flex items-center justify-center gap-4">
                <FileArchive className="h-12 w-12 text-primary" />
                <div className="text-left">
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatFileSize(file.size)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="ml-4"
                  onClick={(e) => {
                    e.stopPropagation();
                    clearFile();
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <>
                <Upload className={cn(
                  'h-12 w-12 mx-auto mb-4 transition-colors',
                  uploadState.status === 'dragging' ? 'text-primary' : 'text-muted-foreground'
                )} />
                <p className="text-lg font-medium mb-1">
                  {uploadState.status === 'dragging' ? '释放以上传文件' : '点击或拖拽上传'}
                </p>
                <p className="text-sm text-muted-foreground">
                  支持 ZIP 格式，最大 500MB
                </p>
              </>
            )}
          </div>

          {/* 错误提示 */}
          {uploadState.status === 'error' && (
            <Alert variant="destructive" className="mt-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{uploadState.message}</AlertDescription>
            </Alert>
          )}

          {/* 成功提示 */}
          {uploadState.status === 'success' && (
            <Alert className="mt-4 border-green-500 text-green-700">
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>{uploadState.message}</AlertDescription>
            </Alert>
          )}

          {/* 进度条 */}
          {(uploadState.status === 'uploading' || uploadState.status === 'processing') && (
            <div className="mt-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span>{uploadState.message}</span>
                <span>{Math.round(uploadState.progress)}%</span>
              </div>
              <Progress value={uploadState.progress} className="h-2" />
            </div>
          )}
        </CardContent>
      </Card>

      {/* 数据集信息表单 */}
      <Card>
        <CardHeader>
          <CardTitle>数据集信息</CardTitle>
          <CardDescription>
            填写数据集的基本信息和类别定义
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 名称 */}
          <div className="space-y-2">
            <Label htmlFor="name">数据集名称 *</Label>
            <Input
              id="name"
              placeholder="输入数据集名称"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={uploadState.status === 'uploading' || uploadState.status === 'processing'}
            />
          </div>

          {/* 描述 */}
          <div className="space-y-2">
            <Label htmlFor="description">描述</Label>
            <Textarea
              id="description"
              placeholder="输入数据集描述（可选）"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              disabled={uploadState.status === 'uploading' || uploadState.status === 'processing'}
            />
          </div>

          {/* 格式选择 */}
          <div className="space-y-2">
            <Label htmlFor="format">数据格式</Label>
            <Select
              value={format}
              onValueChange={setFormat}
              disabled={uploadState.status === 'uploading' || uploadState.status === 'processing'}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择格式" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">自动检测</SelectItem>
                <SelectItem value="YOLO">YOLO</SelectItem>
                <SelectItem value="COCO">COCO</SelectItem>
                <SelectItem value="VOC">VOC</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 类别名称 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>类别名称（可选）</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddClass}
                disabled={uploadState.status === 'uploading' || uploadState.status === 'processing'}
              >
                <Plus className="h-4 w-4 mr-1" />
                添加类别
              </Button>
            </div>
            <div className="space-y-2">
              {classNames.map((className, index) => (
                <div key={index} className="flex gap-2">
                  <Input
                    placeholder={`类别 ${index + 1}`}
                    value={className}
                    onChange={(e) => handleClassNameChange(index, e.target.value)}
                    disabled={uploadState.status === 'uploading' || uploadState.status === 'processing'}
                  />
                  {classNames.length > 1 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => handleRemoveClass(index)}
                      disabled={uploadState.status === 'uploading' || uploadState.status === 'processing'}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 提交按钮 */}
      <div className="flex justify-end gap-4">
        <Button
          variant="outline"
          onClick={() => navigate('/admin/datasets')}
          disabled={uploadState.status === 'uploading' || uploadState.status === 'processing'}
        >
          取消
        </Button>
        <Button
          onClick={handleUpload}
          disabled={!file || uploadState.status === 'uploading' || uploadState.status === 'processing'}
        >
          {uploadState.status === 'uploading' || uploadState.status === 'processing' ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              上传中...
            </>
          ) : (
            <>
              <Upload className="mr-2 h-4 w-4" />
              开始上传
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

export default DatasetUploadPage;
