/**
 * 模型画布组件（单向数据流版）
 *
 * State 全在 zustand store，本组件只做渲染+交互。
 * 参见 https://reactflow.dev/learn/advanced-use/state-management
 *
 * 功能：
 * 1. 接收拖拽的模块并创建节点
 * 2. 支持节点拖动、选中、删除
 * 3. 支持节点间连线（连线规则验证）
 * 4. 缩放和平移画布
 * 5. 节点双击打开参数配置面板
 */
import { useCallback, useRef, useState, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useReactFlow,
  ReactFlowProvider,
  useUpdateNodeInternals,
  type Connection,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
  Panel,
  addEdge,
  BackgroundVariant,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Undo2, Redo2, Trash2, Save, FolderOpen, Download, MousePointer2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/utils/cn';
import { useToast } from '@/hooks/use-toast';
import { useModelBuilderStore } from '@/stores/modelBuilderStore';
import AtomicNode from './AtomicNode';
import CompositeNode from './CompositeNode';
import type { ModuleDefinition, RFNode, RFEdge, ModelNodeData } from '@/types/mlModule';

/**
 * 校验连接合法性：禁止从 target handle（输入端口）开始拖线
 */
export function isValidConnection(nodes: RFNode[], edge: Connection | RFEdge): boolean {
  if (edge.source && edge.sourceHandle) {
    const sourceNode = nodes.find((n) => n.id === edge.source);
    if (sourceNode) {
      const data = sourceNode.data as unknown as ModelNodeData;
      const outputPortNames = new Set((data.outputPorts || []).map((p) => p.name));
      if (!outputPortNames.has(edge.sourceHandle)) {
        return false;
      }
    }
  }
  return true;
}

// 节点类型路由：根据 isComposite 分发到原子/复合节点组件
function ModuleNode(props: NodeProps) {
  const data = props.data as { isComposite?: boolean } | undefined;
  return data?.isComposite
    ? <CompositeNode {...props} />
    : <AtomicNode {...props} />;
}

// 节点类型注册（保持 'module' 键名不变，兼容已持久化数据）
const nodeTypes = {
  module: ModuleNode,
};

interface ModelCanvasProps {
  /** 节点选中回调 */
  onNodeSelect?: (node: RFNode | null) => void;
  /** 节点双击回调 */
  onNodeDoubleClick?: (node: RFNode) => void;
  /** 保存回调 */
  onSave?: () => void;
  /** 加载回调 */
  onLoad?: () => void;
  /** 导出回调 */
  onExport?: () => void;
  /** React Flow 初始化完成回调（用于外部调 fitView 等） */
  onInit?: (instance: ReactFlowInstance) => void;
  /** 自定义类名 */
  className?: string;
}

/**
 * 模型画布内部组件
 *
 * 包含 React Flow 的实际逻辑
 */
function ModelCanvasInner({
  onNodeSelect,
  onNodeDoubleClick,
  onSave,
  onLoad,
  onExport,
  onInit,
  className,
}: ModelCanvasProps) {
  // React Flow 实例
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

  // 从 zustand store 读取唯一真相源
  const nodes = useModelBuilderStore((s) => s.nodes);
  const edges = useModelBuilderStore((s) => s.edges);
  const onNodesChange = useModelBuilderStore((s) => s.onNodesChange);
  const onEdgesChange = useModelBuilderStore((s) => s.onEdgesChange);
  const setNodes = useModelBuilderStore((s) => s.setNodes);
  const setEdges = useModelBuilderStore((s) => s.setEdges);
  const saveHistory = useModelBuilderStore((s) => s.saveHistory);
  const viewport = useModelBuilderStore((s) => s.viewport);
  const setViewport = useModelBuilderStore((s) => s.setViewport);
  const undo = useModelBuilderStore((s) => s.undo);
  const redo = useModelBuilderStore((s) => s.redo);
  const canUndo = useModelBuilderStore((s) => s.canUndo);
  const canRedo = useModelBuilderStore((s) => s.canRedo);
  const setUpdateNodeInternalsRef = useModelBuilderStore((s) => s.setUpdateNodeInternalsRef);

  const updateNodeInternals = useUpdateNodeInternals();

  useEffect(() => {
    setUpdateNodeInternalsRef(updateNodeInternals);
    return () => setUpdateNodeInternalsRef(null);
  }, [updateNodeInternals, setUpdateNodeInternalsRef]);

  // 选中的节点（本地 UI 状态）
  const [selectedNode, setSelectedNode] = useState<RFNode | null>(null);

  const { toast } = useToast();

  // 把 React Flow instance 传出去（供外部 fitView 等）
  const reactFlowInstance = useReactFlow();
  useEffect(() => {
    onInit?.(reactFlowInstance);
  }, [onInit, reactFlowInstance]);

  // 恢复或初始化 viewport
  const hasRestoredViewport = useRef(false);
  useEffect(() => {
    if (hasRestoredViewport.current) return;
    hasRestoredViewport.current = true;

    if (viewport) {
      reactFlowInstance.setViewport(viewport);
    } else {
      reactFlowInstance.fitView();
    }
  }, [reactFlowInstance, viewport]);

  // 处理拖拽放置
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect();
      if (!reactFlowBounds) return;

      const moduleData = event.dataTransfer.getData('application/reactflow');
      if (!moduleData) return;

      try {
        const module: ModuleDefinition = JSON.parse(moduleData);

        // 计算画布坐标（RF12 screenToFlowPosition 期望屏幕坐标）
        const position = screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });

        // 创建新节点
        const newNode: RFNode = {
          id: `node_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: 'module',
          position,
          data: {
            moduleType: module.type,
            moduleName: module.type,
            displayName: module.display_name,
            parameters: {}, // 默认参数会在后续从模块详情加载
            inputPorts: (module.proxy_inputs || []).map((p) => ({ name: p.name, type: 'tensor' })),
            outputPorts: (module.proxy_outputs || []).map((p) => ({ name: p.name, type: 'tensor' })),
            inputPortsDynamic: module.input_ports_dynamic === true,
            icon: module.is_composite ? 'Network' : 'Layers',
            isComposite: module.is_composite,
          },
        };

        setNodes((nds) => [...nds, newNode]);
        saveHistory();

        toast({
          title: '添加成功',
          description: `已添加 ${module.display_name}`,
        });
      } catch (error) {
        console.error('创建节点失败:', error);
        toast({
          title: '添加失败',
          description: '无法创建节点',
          variant: 'destructive',
        });
      }
    },
    [screenToFlowPosition, setNodes, saveHistory, toast]
  );

  // 处理连接（连线）
  const isValidConnectionCb = useCallback(
    (edge: Connection | RFEdge) => isValidConnection(nodes, edge),
    [nodes]
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      // 验证连接
      if (connection.source === connection.target) {
        toast({
          title: '无效连接',
          description: '不能将节点连接到自己',
          variant: 'destructive',
        });
        return;
      }

      // 检查输入端口是否已被占用
      const existingEdge = edges.find(
        (e) => e.target === connection.target && e.targetHandle === connection.targetHandle
      );
      if (existingEdge) {
        toast({
          title: '无效连接',
          description: '该输入端口已被占用',
          variant: 'destructive',
        });
        return;
      }

      // 检查是否形成环
      const wouldCreateCycle = (src: string, tgt: string): boolean => {
        const adjacency = new Map<string, Set<string>>();

        // 构建邻接表（包含新边）
        nodes.forEach((node) => adjacency.set(node.id, new Set()));
        edges.forEach((edge) => {
          adjacency.get(edge.source)?.add(edge.target);
        });
        adjacency.get(src)?.add(tgt);

        // DFS 检测环
        const visited = new Set<string>();
        const recStack = new Set<string>();

        const hasCycle = (nodeId: string): boolean => {
          visited.add(nodeId);
          recStack.add(nodeId);

          for (const neighbor of adjacency.get(nodeId) || []) {
            if (!visited.has(neighbor)) {
              if (hasCycle(neighbor)) return true;
            } else if (recStack.has(neighbor)) {
              return true;
            }
          }

          recStack.delete(nodeId);
          return false;
        };

        for (const nodeId of adjacency.keys()) {
          if (!visited.has(nodeId)) {
            if (hasCycle(nodeId)) return true;
          }
        }
        return false;
      };

      if (connection.source && connection.target) {
        if (wouldCreateCycle(connection.source, connection.target)) {
          toast({
            title: '无效连接',
            description: '不能形成环路，模型必须是 DAG（有向无环图）',
            variant: 'destructive',
          });
          return;
        }
      }

      // 添加边
      setEdges((eds) => addEdge(connection, eds));
      saveHistory();
    },
    [edges, nodes, setEdges, saveHistory, toast]
  );

  // 处理节点选择
  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedNode(node as RFNode);
      onNodeSelect?.(node as RFNode);
    },
    [onNodeSelect]
  );

  // 处理节点双击
  const onNodeDoubleClickHandler = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeDoubleClick?.(node as RFNode);
    },
    [onNodeDoubleClick]
  );

  // 处理背景点击（取消选择）
  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
    onNodeSelect?.(null);
  }, [onNodeSelect]);

  // 删除选中的节点
  const deleteSelectedNode = useCallback(() => {
    if (selectedNode) {
      const deletedName = (selectedNode.data?.displayName as string)
        || (selectedNode.data?.moduleName as string)
        || selectedNode.id;
      setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
      setEdges((eds) => eds.filter(
        (e) => e.source !== selectedNode.id && e.target !== selectedNode.id
      ));
      setSelectedNode(null);
      onNodeSelect?.(null);
      saveHistory();
      toast({ title: `已删除节点: ${deletedName}` });
    }
  }, [selectedNode, setNodes, setEdges, onNodeSelect, saveHistory, toast]);

  // 删除选中的连线（供键盘和工具栏复用）
  const deleteSelectedEdges = useCallback(() => {
    const selectedEdgeIds = edges.filter((e) => e.selected).map((e) => e.id);
    if (selectedEdgeIds.length > 0) {
      setEdges((eds) => eds.filter((e) => !selectedEdgeIds.includes(e.id)));
      saveHistory();
      toast({ title: `已删除 ${selectedEdgeIds.length} 条连线` });
    }
  }, [edges, setEdges, saveHistory, toast]);

  // 统一删除入口：节点优先，其次 edge
  const handleDeleteSelected = useCallback(() => {
    if (selectedNode) {
      deleteSelectedNode();
    } else {
      deleteSelectedEdges();
    }
  }, [selectedNode, deleteSelectedNode, deleteSelectedEdges]);

  // window 级快捷键监听
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Guard：避免在输入框/可编辑区域触发全局快捷键
      const target = event.target as HTMLElement | null;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable
      ) {
        return;
      }

      if (event.key === 'Delete' || event.key === 'Backspace') {
        if (selectedNode) {
          deleteSelectedNode();
        } else {
          deleteSelectedEdges();
        }
      }
      if ((event.metaKey || event.ctrlKey) && event.key === 'z') {
        event.preventDefault();
        if (event.shiftKey) {
          redo();
        } else {
          undo();
        }
      }
      if ((event.metaKey || event.ctrlKey) && event.key === 's') {
        event.preventDefault();
        onSave?.();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedNode, deleteSelectedNode, deleteSelectedEdges, undo, redo, onSave]);

  return (
    <div
      ref={reactFlowWrapper}
      className={cn('flex-1 h-full', className)}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onNodeDoubleClick={onNodeDoubleClickHandler}
        onPaneClick={onPaneClick}
        onDragOver={onDragOver}
        onDrop={onDrop}
        onMoveEnd={(_, vp) => setViewport(vp)}
        isValidConnection={isValidConnectionCb}
        nodeTypes={nodeTypes}
        attributionPosition="bottom-left"
        deleteKeyCode={['Backspace', 'Delete']}
        selectionKeyCode={['Shift']}
        multiSelectionKeyCode={['Meta', 'Ctrl']}
      >
        {/* 网格背景 */}
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="#e5e7eb"
        />

        {/* 控制按钮 */}
        <Controls className="bg-card border shadow-sm" />

        {/* 缩略图 */}
        <MiniMap
          className="bg-card border shadow-sm"
          nodeColor={(node) => {
            return node.selected ? '#3b82f6' : '#9ca3af';
          }}
          maskColor="rgba(0, 0, 0, 0.1)"
        />

        {/* 顶部工具栏 */}
        <Panel position="top-center" className="m-2">
          <div className="flex items-center gap-1 bg-card border rounded-lg shadow-sm p-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={undo}
              disabled={!canUndo()}
              title="撤销 (Ctrl+Z)"
            >
              <Undo2 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={redo}
              disabled={!canRedo()}
              title="重做 (Ctrl+Shift+Z)"
            >
              <Redo2 className="h-4 w-4" />
            </Button>
            <div className="w-px h-4 bg-border mx-1" />
            <Button
              variant="ghost"
              size="icon"
              onClick={handleDeleteSelected}
              disabled={!selectedNode && !edges.some((e) => e.selected)}
              title="删除选中 (Delete)"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
            <div className="w-px h-4 bg-border mx-1" />
            <Button
              variant="ghost"
              size="icon"
              onClick={onSave}
              title="保存 (Ctrl+S)"
            >
              <Save className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onLoad}
              title="加载"
            >
              <FolderOpen className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onExport}
              title="导出"
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>
        </Panel>

        {/* 底部提示 */}
        <Panel position="bottom-center" className="m-2">
          <div className="flex items-center gap-4 text-xs text-muted-foreground bg-card/80 border rounded-lg px-3 py-1.5">
            <span className="flex items-center gap-1">
              <MousePointer2 className="h-3 w-3" />
              拖拽模块到画布
            </span>
            <span>双击节点编辑参数</span>
            <span>Ctrl+点击多选</span>
            <span>滚轮缩放</span>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}

/**
 * 模型画布组件
 *
 * 包裹 ReactFlowProvider 的对外接口
 */
export function ModelCanvas(props: ModelCanvasProps) {
  return (
    <ReactFlowProvider>
      <ModelCanvasInner {...props} />
    </ReactFlowProvider>
  );
}

export default ModelCanvas;
