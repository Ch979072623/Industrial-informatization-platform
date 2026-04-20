/**
 * ModelBuilder Zustand Store（含 localStorage 持久化）
 *
 * 功能：
 * 1. 画布 nodes/edges 唯一真相源（单向数据流）
 * 2. persist middleware 自动同步到 localStorage（防刷新丢失）
 * 3. 支持撤销/重做历史
 * 4. 模块 schema 运行时缓存（不持久化）
 *
 * React Flow 官方推荐模式：
 * https://reactflow.dev/learn/advanced-use/state-management
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { applyNodeChanges, applyEdgeChanges, type NodeChange, type EdgeChange, type Viewport } from '@xyflow/react';
import { mlModuleApi } from '@/services/api';
import type { RFNode, RFEdge, ModuleSchemaDetail, SubNode, SubEdge } from '@/types/mlModule';

interface ModelBuilderState {
  nodes: RFNode[];
  edges: RFEdge[];
  viewport: Viewport | undefined;
  selectedNodeId: string | null;
  history: { nodes: RFNode[]; edges: RFEdge[] }[];
  historyIndex: number;

  /** 模块 schema 运行时缓存（key = moduleType） */
  moduleSchemas: Record<string, ModuleSchemaDetail>;
  moduleSchemaLoading: Record<string, boolean>;
  moduleSchemaError: Record<string, string | null>;

  /** React Flow 内部变化（拖动、选中、删除等）——走 applyChanges */
  onNodesChange: (changes: NodeChange[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;

  /** 直接赋值（加载配置、撤销重做、清空画布等）——不走 applyChanges */
  setNodes: (nodes: RFNode[] | ((prev: RFNode[]) => RFNode[])) => void;
  setEdges: (edges: RFEdge[] | ((prev: RFEdge[]) => RFEdge[])) => void;

  setSelectedNodeId: (id: string | null) => void;
  setViewport: (viewport: Viewport) => void;
  saveHistory: () => void;
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  clearCanvas: () => void;

  toggleCollapse: (nodeId: string) => void;
  markSubLoaded: (nodeId: string) => void;

  getOrLoadModuleSchema: (moduleType: string) => Promise<ModuleSchemaDetail | null>;
  clearModuleSchemaError: (moduleType: string) => void;

  /** React Flow updateNodeInternals 函数引用（由 ModelCanvas 注入，不持久化） */
  updateNodeInternalsRef: ((nodeId: string) => void) | null;
  setUpdateNodeInternalsRef: (ref: ((nodeId: string) => void) | null) => void;
}

const MAX_HISTORY = 20;

export const useModelBuilderStore = create<ModelBuilderState>()(
  persist(
    (set, get) => ({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      history: [],
      historyIndex: -1,
      moduleSchemas: {},
      moduleSchemaLoading: {},
      moduleSchemaError: {},
      updateNodeInternalsRef: null,
      viewport: undefined,

      onNodesChange: (changes) =>
        set((state) => ({
          nodes: applyNodeChanges(changes, state.nodes) as RFNode[],
        })),

      onEdgesChange: (changes) =>
        set((state) => ({
          edges: applyEdgeChanges(changes, state.edges) as RFEdge[],
        })),

      setNodes: (nodes) =>
        set((state) => ({
          nodes: typeof nodes === 'function' ? nodes(state.nodes) : nodes,
        })),

      setEdges: (edges) =>
        set((state) => ({
          edges: typeof edges === 'function' ? edges(state.edges) : edges,
        })),

      setSelectedNodeId: (id) => set({ selectedNodeId: id }),

      setViewport: (viewport) => set({ viewport }),

      saveHistory: () =>
        set((state) => {
          const newHistory = state.history.slice(0, state.historyIndex + 1);
          newHistory.push({
            nodes: JSON.parse(JSON.stringify(state.nodes)),
            edges: JSON.parse(JSON.stringify(state.edges)),
          });
          return {
            history: newHistory.slice(-MAX_HISTORY),
            historyIndex: Math.min(newHistory.length - 1, MAX_HISTORY - 1),
          };
        }),

      undo: () =>
        set((state) => {
          if (state.historyIndex <= 0) return state;
          const newIndex = state.historyIndex - 1;
          const snap = state.history[newIndex];
          return {
            historyIndex: newIndex,
            nodes: JSON.parse(JSON.stringify(snap.nodes)),
            edges: JSON.parse(JSON.stringify(snap.edges)),
          };
        }),

      redo: () =>
        set((state) => {
          if (state.historyIndex >= state.history.length - 1) return state;
          const newIndex = state.historyIndex + 1;
          const snap = state.history[newIndex];
          return {
            historyIndex: newIndex,
            nodes: JSON.parse(JSON.stringify(snap.nodes)),
            edges: JSON.parse(JSON.stringify(snap.edges)),
          };
        }),

      canUndo: () => get().historyIndex > 0,
      canRedo: () => get().historyIndex < get().history.length - 1,

      clearCanvas: () =>
        set({
          nodes: [],
          edges: [],
          selectedNodeId: null,
          history: [],
          historyIndex: -1,
        }),

      setUpdateNodeInternalsRef: (ref) =>
        set({ updateNodeInternalsRef: ref }),

      toggleCollapse: (nodeId) =>
        set((state) => {
          const targetNode = state.nodes.find((n) => n.id === nodeId);
          if (!targetNode || targetNode.data.isComposite !== true) {
            return state;
          }

          const ref = state.updateNodeInternalsRef;
          if (ref) {
            queueMicrotask(() => ref(nodeId));
          }

          return {
            nodes: state.nodes.map((n) =>
              n.id === nodeId
                ? {
                    ...n,
                    data: {
                      ...n.data,
                      collapsed: n.data.collapsed === false,
                    },
                  }
                : n
            ),
          };
        }),

      markSubLoaded: (nodeId) =>
        set((state) => {
          const targetNode = state.nodes.find((n) => n.id === nodeId);
          if (!targetNode) {
            return state;
          }
          return {
            nodes: state.nodes.map((n) =>
              n.id === nodeId
                ? {
                    ...n,
                    data: {
                      ...n.data,
                      subLoaded: true,
                    },
                  }
                : n
            ),
          };
        }),

      getOrLoadModuleSchema: async (moduleType) => {
        const state = get();
        const cached = state.moduleSchemas[moduleType];
        if (cached) {
          return cached;
        }

        set((s) => ({
          moduleSchemaLoading: { ...s.moduleSchemaLoading, [moduleType]: true },
        }));

        try {
          const response = await mlModuleApi.getModule(moduleType);
          const detail = response.data.data;
          const { schema_json, ...rest } = detail;
          const schema: ModuleSchemaDetail = {
            ...rest,
            sub_nodes: schema_json?.sub_nodes as SubNode[] | undefined,
            sub_edges: schema_json?.sub_edges as SubEdge[] | undefined,
          };

          set((s) => ({
            moduleSchemas: { ...s.moduleSchemas, [moduleType]: schema },
            moduleSchemaLoading: { ...s.moduleSchemaLoading, [moduleType]: false },
            moduleSchemaError: { ...s.moduleSchemaError, [moduleType]: null },
          }));

          return schema;
        } catch (err) {
          const message = err instanceof Error ? err.message : '加载失败';
          set((s) => ({
            moduleSchemaLoading: { ...s.moduleSchemaLoading, [moduleType]: false },
            moduleSchemaError: { ...s.moduleSchemaError, [moduleType]: message },
          }));
          return null;
        }
      },

      clearModuleSchemaError: (moduleType) =>
        set((s) => ({
          moduleSchemaError: { ...s.moduleSchemaError, [moduleType]: null },
        })),
    }),
    {
      name: 'model-builder-draft',
      partialize: (state) => ({
        nodes: state.nodes.map((n) => {
          const { collapsed: _c, subLoaded: _s, ...rest } = n.data;
          void _c;
          void _s;
          return { ...n, data: rest };
        }),
        edges: state.edges,
        viewport: state.viewport,
      }),
    }
  )
);
