/**
 * 模型构建器主页面（单向数据流版）
 *
 * 布局：
 * - 左侧：模块库面板
 * - 中间：画布区域
 * - 右侧：参数配置面板
 *
 * 所有画布状态（nodes/edges）统一在 zustand store 管理，
 * ModelCanvas 只做渲染+交互。
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useToast } from '@/hooks/use-toast';
import type { ReactFlowInstance } from '@xyflow/react';
import { ModuleLibrary } from '@/components/model-builder/ModuleLibrary';
import { ModelCanvas } from '@/components/model-builder/ModelCanvas';
import { NodeConfigPanel } from '@/components/model-builder/NodeConfigPanel';
import { NewCanvasDialog } from '@/components/model-builder/NewCanvasDialog';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { mlModuleApi, modelBuilderApi } from '@/services/api';
import { useModelBuilderStore } from '@/stores/modelBuilderStore';
import type {
  ModuleDefinition,
  ModuleDefinitionDetail,
  RFNode,
  RFEdge,
  ModelBuilderConfig,
  ModelBuilderConfigCreate,
  ModelNode,
  ModelEdge,
} from '@/types/mlModule';

export default function ModelBuilder() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const configId = searchParams.get('id');
  const { toast } = useToast();

  // Zustand store（唯一真相源）
  const nodes = useModelBuilderStore((s) => s.nodes);
  const edges = useModelBuilderStore((s) => s.edges);
  const setNodes = useModelBuilderStore((s) => s.setNodes);
  const setEdges = useModelBuilderStore((s) => s.setEdges);
  const setMode = useModelBuilderStore((s) => s.setMode);
  const mode = useModelBuilderStore((s) => s.mode);

  // React Flow instance（用于 fitView）
  const reactFlowInstanceRef = useRef<ReactFlowInstance | null>(null);

  // 选中节点和模块详情
  const [selectedNode, setSelectedNode] = useState<RFNode | null>(null);
  const [selectedModuleDetails, setSelectedModuleDetails] = useState<ModuleDefinitionDetail | null>(null);

  // 保存对话框
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveFormData, setSaveFormData] = useState({ name: '', description: '' });
  const [saving, setSaving] = useState(false);

  // 加载对话框
  const [loadDialogOpen, setLoadDialogOpen] = useState(false);
  const [savedConfigs, setSavedConfigs] = useState<ModelBuilderConfig[]>([]);
  const [loadingConfigs, setLoadingConfigs] = useState(false);

  // 新建画布弹窗
  const [newCanvasDialogOpen, setNewCanvasDialogOpen] = useState(false);

  // 从 URL 加载配置
  useEffect(() => {
    if (configId) loadConfig(configId);
  }, [configId]);

  const loadConfig = useCallback(async (id: string) => {
    try {
      console.log('[DEBUG] loadConfig start, id:', id);
      const response = await modelBuilderApi.getConfig(id);
      console.log('[DEBUG] loadConfig response:', JSON.stringify(response.data, null, 2));
      if (response.data.success && response.data.data) {
        const config = response.data.data;
        console.log('[DEBUG] architecture_json raw:', config.architecture_json);
        console.log('[DEBUG] typeof architecture_json:', typeof config.architecture_json);

        // 清除 localStorage 草稿，避免 zustand persist 竞争
        localStorage.removeItem('model-builder-draft');

        const arch = typeof config.architecture_json === 'string'
          ? JSON.parse(config.architecture_json)
          : config.architecture_json;

        console.log('[DEBUG] parsed arch:', JSON.stringify(arch, null, 2));
        console.log('[DEBUG] nodes before set:', arch?.nodes?.length);
        console.log('[DEBUG] edges before set:', arch?.edges?.length);

        // 向后兼容：旧数据没有 mode 时默认 'architecture'
        const loadedMode = arch?.metadata?.mode || 'architecture';
        setMode(loadedMode);

        const loadedNodes = (arch?.nodes || []).map((node: ModelNode) => ({
          ...node,
          // 向后兼容：旧数据节点 type 可能缺失，默认 'module'
          type: node.type || 'module',
        })) as unknown as RFNode[];
        const loadedEdges = (arch?.edges || []) as unknown as RFEdge[];

        setNodes(loadedNodes);
        setEdges(loadedEdges);

        console.log('[DEBUG] loadConfig done, nodes:', loadedNodes.length, 'edges:', loadedEdges.length);
        toast({ title: '加载成功', description: `已加载配置: ${config.name}` });

        // 等 React 渲染一轮后 fitView，把节点缩放到可视区域
        requestAnimationFrame(() => {
          setTimeout(() => {
            reactFlowInstanceRef.current?.fitView({ padding: 0.2, duration: 300 });
          }, 50);
        });
      }
    } catch (error) {
      console.error('加载配置失败:', error);
      toast({ title: '加载失败', description: '无法加载模型配置', variant: 'destructive' });
    }
  }, [toast, setNodes, setEdges]);

  const handleModuleDragStart = useCallback((module: ModuleDefinition) => {
    console.log('拖拽模块:', module.type);
  }, []);

  const handleNodeSelect = useCallback(async (node: RFNode | null) => {
    setSelectedNode(node);

    if (node) {
      // Port 节点没有 ModuleDefinition，跳过拉取
      if (node.type === 'input_port' || node.type === 'output_port') {
        setSelectedModuleDetails(null);
        return;
      }
      try {
        const moduleType = node.data.moduleType as string;
        if (!moduleType) {
          console.warn('节点缺少 moduleType');
          setSelectedModuleDetails(null);
          return;
        }
        const response = await mlModuleApi.getModule(moduleType);
        if (response.data.success && response.data.data) {
          const detail = response.data.data as ModuleDefinitionDetail;
          setSelectedModuleDetails(detail);

          // 提取默认值
          const defaults: Record<string, unknown> = {};
          for (const param of detail.params_schema) {
            if (param.default !== undefined) defaults[param.name] = param.default;
          }

          // 如果节点参数为空，填充默认值
          const currentParams = (node.data.parameters as Record<string, unknown>) || {};
          if (Object.keys(currentParams).length === 0) {
            setNodes((prev) =>
              prev.map((n) =>
                n.id === node.id
                  ? { ...n, data: { ...n.data, parameters: defaults } }
                  : n
              )
            );
          }

          // 更新端口
          const newInputPorts = detail.proxy_inputs.map((p) => ({ name: p.name, type: 'tensor' as const }));
          const newOutputPorts = detail.proxy_outputs.map((p) => ({ name: p.name, type: 'tensor' as const }));
          setNodes((prev) =>
            prev.map((n) =>
              n.id === node.id
                ? { ...n, data: { ...n.data, inputPorts: newInputPorts, outputPorts: newOutputPorts } }
                : n
            )
          );
        }
      } catch (error) {
        console.error('加载模块详情失败:', error);
        setSelectedModuleDetails(null);
      }
    } else {
      setSelectedModuleDetails(null);
    }
  }, [setNodes]);

  const handleNodeDoubleClick = useCallback((node: RFNode) => {
    setSelectedNode(node);
  }, []);

  const handleParamChange = useCallback((nodeId: string, params: Record<string, unknown>) => {
    setNodes((prev) =>
      prev.map((node) =>
        node.id === nodeId ? { ...node, data: { ...node.data, parameters: params } } : node
      )
    );
    if (selectedNode && selectedNode.id === nodeId) {
      setSelectedNode((prev) =>
        prev ? { ...prev, data: { ...prev.data, parameters: params } } : null
      );
    }
  }, [selectedNode, setNodes]);

  const handleSave = useCallback(async () => {
    if (nodes.length === 0) {
      toast({ title: '保存失败', description: '画布为空，无法保存', variant: 'destructive' });
      return;
    }
    setSaveFormData({ name: '', description: '' });
    setSaveDialogOpen(true);
  }, [nodes.length, toast]);

  const confirmSave = useCallback(async () => {
    if (!saveFormData.name.trim()) {
      toast({ title: '保存失败', description: '请输入配置名称', variant: 'destructive' });
      return;
    }
    try {
      setSaving(true);
      const mode = useModelBuilderStore.getState().mode;
      const configData: ModelBuilderConfigCreate = {
        name: saveFormData.name,
        description: saveFormData.description || undefined,
        architecture_json: { nodes: nodes as unknown as ModelNode[], edges: edges as unknown as ModelEdge[], metadata: { description: saveFormData.description || undefined, mode } },
        is_public: false,
      };
      const response = await modelBuilderApi.createConfig(configData);
      if (response.data.success) {
        toast({ title: '保存成功', description: '模型配置已保存到数据库' });
        setSaveDialogOpen(false);
      }
    } catch (error) {
      console.error('保存配置失败:', error);
      toast({ title: '保存失败', description: '无法保存模型配置', variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  }, [saveFormData, nodes, edges, toast]);

  const handleLoad = useCallback(async () => {
    try {
      setLoadingConfigs(true);
      setLoadDialogOpen(true);
      const response = await modelBuilderApi.getConfigs({ page: 1, page_size: 50 });
      if (response.data.success && response.data.data) {
        setSavedConfigs(response.data.data.items as unknown as ModelBuilderConfig[]);
      }
    } catch (error) {
      console.error('加载配置列表失败:', error);
      toast({ title: '加载失败', description: '无法加载配置列表', variant: 'destructive' });
    } finally {
      setLoadingConfigs(false);
    }
  }, [toast]);

  const handleSelectConfig = useCallback((config: ModelBuilderConfig) => {
    navigate(`/admin/model-builder?id=${config.id}`);
    setLoadDialogOpen(false);
  }, [navigate]);

  const handleNewCanvas = useCallback(() => {
    // 若画布非空，二次确认
    if (nodes.length > 0 || edges.length > 0) {
      if (!window.confirm('当前画布有未保存的内容，是否放弃并创建新画布？')) {
        return;
      }
    }
    setNewCanvasDialogOpen(true);
  }, [nodes.length, edges.length]);

  const confirmNewCanvas = useCallback((mode: import('@/types/mlModule').CanvasMode) => {
    const { setMode, initializeModuleCanvas, initializeArchitectureCanvas } = useModelBuilderStore.getState();
    setMode(mode);
    if (mode === 'module') {
      initializeModuleCanvas();
    } else {
      initializeArchitectureCanvas();
    }
    setSelectedNode(null);
    setSelectedModuleDetails(null);
    toast({ title: '新建画布', description: mode === 'module' ? '已切换到模块编辑模式' : '已切换到架构编辑模式' });
  }, [toast]);

  const handleExport = useCallback(() => {
    const exportData = { nodes, edges, exported_at: new Date().toISOString() };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `model-config-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast({ title: '导出成功', description: '模型配置已导出为 JSON 文件' });
  }, [nodes, edges, toast]);

  const handleCloseConfigPanel = useCallback(() => {
    setSelectedNode(null);
    setSelectedModuleDetails(null);
  }, []);

  const handleInit = useCallback((instance: ReactFlowInstance) => {
    reactFlowInstanceRef.current = instance;
  }, []);

  return (
    <ErrorBoundary>
      <div className="flex h-[calc(100vh-4rem)]">
        <ModuleLibrary mode={mode} onModuleDragStart={handleModuleDragStart} className="w-72 flex-shrink-0" />

        <ModelCanvas
          onNodeSelect={handleNodeSelect}
          onNodeDoubleClick={handleNodeDoubleClick}
          onSave={handleSave}
          onLoad={handleLoad}
          onExport={handleExport}
          onNewCanvas={handleNewCanvas}
          onInit={handleInit}
          className="flex-1"
        />

        <NodeConfigPanel
          node={selectedNode}
          moduleDetails={selectedModuleDetails}
          onParamChange={handleParamChange}
          onClose={handleCloseConfigPanel}
          className="flex-shrink-0"
        />

        {/* 新建画布弹窗 */}
        <NewCanvasDialog
          open={newCanvasDialogOpen}
          onOpenChange={setNewCanvasDialogOpen}
          onConfirm={confirmNewCanvas}
        />

        {/* 保存对话框 */}
        <Dialog open={saveDialogOpen} onOpenChange={setSaveDialogOpen}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>保存模型配置</DialogTitle>
              <DialogDescription>将当前模型架构保存到数据库</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">配置名称 *</Label>
                <Input
                  id="name"
                  placeholder="例如：YOLO11 改进模型"
                  value={saveFormData.name}
                  onChange={(e) => setSaveFormData((p) => ({ ...p, name: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">配置描述</Label>
                <Textarea
                  id="description"
                  placeholder="描述这个模型的特点和用途..."
                  value={saveFormData.description}
                  onChange={(e) => setSaveFormData((p) => ({ ...p, description: e.target.value }))}
                  rows={3}
                />
              </div>
              <div className="text-sm text-muted-foreground">
                <p>节点数量: {nodes.length}</p>
                <p>连接数量: {edges.length}</p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setSaveDialogOpen(false)}>取消</Button>
              <Button onClick={confirmSave} disabled={saving}>{saving ? '保存中...' : '保存'}</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* 加载对话框 */}
        <Dialog open={loadDialogOpen} onOpenChange={setLoadDialogOpen}>
          <DialogContent className="sm:max-w-[600px]">
            <DialogHeader>
              <DialogTitle>加载模型配置</DialogTitle>
              <DialogDescription>选择要加载的已保存配置</DialogDescription>
            </DialogHeader>
            <ScrollArea className="h-[300px] mt-4">
              {loadingConfigs ? (
                <div className="flex items-center justify-center h-32">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                </div>
              ) : savedConfigs.length > 0 ? (
                <div className="space-y-2 pr-4">
                  {savedConfigs.map((config) => (
                    <div
                      key={config.id}
                      onClick={() => handleSelectConfig(config)}
                      className="p-3 rounded-lg border cursor-pointer hover:bg-accent transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div className="font-medium">{config.name}</div>
                        <div className="text-xs text-muted-foreground">v{config.version}</div>
                      </div>
                      {config.description && (
                        <div className="text-sm text-muted-foreground mt-1">{config.description}</div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-muted-foreground py-8">暂无保存的配置</div>
              )}
            </ScrollArea>
            <DialogFooter>
              <Button variant="outline" onClick={() => setLoadDialogOpen(false)}>关闭</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </ErrorBoundary>
  );
}
