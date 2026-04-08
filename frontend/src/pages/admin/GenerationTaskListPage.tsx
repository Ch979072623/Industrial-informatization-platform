/**
 * 生成任务列表页面
 * 
 * 显示所有数据生成任务，支持删除操作
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { generationApi } from '@/services/api';
import type { GenerationJob } from '@/types/generation';

// UI 组件
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

// 图标
import { 
  Trash2, 
  RotateCcw, 
  AlertCircle,
  Loader2,
  CheckCircle2,
  Pause,
  Play,
  X,
  List,
  Database
} from 'lucide-react';

export default function GenerationTaskListPage() {
  const navigate = useNavigate();
  
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  
  // 删除对话框状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [jobToDelete, setJobToDelete] = useState<GenerationJob | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // 批量删除对话框状态
  const [batchDeleteDialogOpen, setBatchDeleteDialogOpen] = useState(false);
  const [batchDeleteType, setBatchDeleteType] = useState<'completed' | 'failed' | 'cancelled' | 'all'>('completed');
  const [isBatchDeleting, setIsBatchDeleting] = useState(false);

  // 加载任务列表
  const loadJobs = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = { page: 1, page_size: 100 };
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      
      const response = await generationApi.getJobs(params);
      if (response.data.success) {
        setJobs(response.data.data.items);
      }
    } catch (err) {
      setError('加载任务列表失败');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadJobs();
    // 每5秒刷新一次
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  // 删除单个任务
  const handleDelete = async () => {
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

  // 批量删除任务
  const handleBatchDelete = async () => {
    setIsBatchDeleting(true);
    try {
      if (batchDeleteType === 'all') {
        // 删除所有可删除的任务
        const response = await generationApi.deleteJobs({ status: undefined });
        if (response.data.success) {
          setJobs(jobs.filter(j => !['completed', 'failed', 'cancelled'].includes(j.status)));
        }
      } else {
        const response = await generationApi.deleteJobs({ status: batchDeleteType });
        if (response.data.success) {
          setJobs(jobs.filter(j => j.status !== batchDeleteType));
        }
      }
      
      setBatchDeleteDialogOpen(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || '批量删除任务失败');
    } finally {
      setIsBatchDeleting(false);
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

  // 获取状态文本
  const getStatusText = (status: string) => {
    const statusMap: Record<string, string> = {
      'pending': '待执行',
      'running': '执行中',
      'paused': '已暂停',
      'completed': '已完成',
      'failed': '失败',
      'cancelled': '已取消'
    };
    return statusMap[status] || status;
  };

  if (loading && jobs.length === 0) {
    return (
      <div className="container mx-auto p-6 flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <List className="h-8 w-8 text-primary" />
            生成任务列表
          </h1>
          <p className="text-muted-foreground mt-1">
            查看和管理所有数据生成任务
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => navigate('/admin/generation')}>
            返回数据生成
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* 筛选和批量操作 */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="筛选状态" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="pending">待执行</SelectItem>
                  <SelectItem value="running">执行中</SelectItem>
                  <SelectItem value="completed">已完成</SelectItem>
                  <SelectItem value="failed">失败</SelectItem>
                  <SelectItem value="cancelled">已取消</SelectItem>
                </SelectContent>
              </Select>
              <span className="text-sm text-muted-foreground">
                共 {jobs.length} 个任务
              </span>
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setBatchDeleteDialogOpen(true)}
                disabled={jobs.length === 0}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                批量删除
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={loadJobs}
              >
                <RotateCcw className="h-4 w-4 mr-2" />
                刷新
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 任务列表 */}
      <div className="space-y-4">
        {jobs.length === 0 ? (
          <Card>
            <CardContent className="p-12 text-center text-muted-foreground">
              <Database className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>暂无生成任务</p>
              <Button 
                variant="link" 
                onClick={() => navigate('/admin/generation')}
              >
                创建新任务
              </Button>
            </CardContent>
          </Card>
        ) : (
          jobs.map((job) => (
            <Card key={job.id}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h4 className="font-medium truncate">{job.name}</h4>
                      <Badge className={getStatusColor(job.status)}>
                        {getStatusText(job.status)}
                      </Badge>
                    </div>
                    
                    <div className="text-sm text-muted-foreground space-y-1">
                      <p>生成器: {job.generator_name}</p>
                      <p>格式: {job.annotation_format.toUpperCase()}</p>
                      <p>创建时间: {new Date(job.created_at).toLocaleString()}</p>
                    </div>

                    <div className="mt-3 space-y-2">
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

                    {job.status === 'completed' && job.output_dataset_id && (
                      <div className="flex items-center gap-2 mt-3">
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

                    {job.error_message && (
                      <div className="flex items-center gap-2 mt-3 text-red-500">
                        <AlertCircle className="h-4 w-4" />
                        <span className="text-sm truncate">{job.error_message}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 ml-4">
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
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setJobToDelete(job);
                        setDeleteDialogOpen(true);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* 删除确认对话框 */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              {`确定要删除任务 "${jobToDelete?.name || ''}" 吗？此操作不可恢复。`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : '删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 批量删除对话框 */}
      <Dialog open={batchDeleteDialogOpen} onOpenChange={setBatchDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>批量删除任务</DialogTitle>
            <DialogDescription>
              选择要删除的任务类型：
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Select value={batchDeleteType} onValueChange={(v) => setBatchDeleteType(v as any)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="completed">已完成的任务</SelectItem>
                <SelectItem value="failed">失败的任务</SelectItem>
                <SelectItem value="cancelled">已取消的任务</SelectItem>
                <SelectItem value="all">所有任务（谨慎使用）</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBatchDeleteDialogOpen(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleBatchDelete} disabled={isBatchDeleting}>
              {isBatchDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : '批量删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
