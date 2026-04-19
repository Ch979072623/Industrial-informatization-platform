/**
 * 机器学习模块类型定义（适配新 module_definitions 表）
 *
 * 模型可视化构建器相关的所有 TypeScript 类型
 */

// ==================== 端口定义 ====================

export interface PortDefinition {
  /** 端口名称 */
  name: string;
  /** 端口数据类型 */
  type: 'tensor' | 'feature' | 'image' | 'any';
  /** 张量形状 */
  shape?: string;
  /** 端口描述 */
  description?: string;
}

// ==================== 模块分类 ====================

export type ModuleCategory = 'atomic' | 'backbone' | 'neck' | 'head' | 'attention' | 'custom';

export interface ModuleCategoryInfo {
  key: ModuleCategory;
  label: string;
  icon: string;
  description?: string;
}

// ==================== 参数 Schema ====================

export interface ParamSchema {
  /** 参数名 */
  name: string;
  /** 参数类型: int/float/int[]/tuple/bool/string */
  type: string;
  /** 默认值 */
  default?: unknown;
  /** 最小值（数值型） */
  min?: number;
  /** 最大值（数值型） */
  max?: number;
  /** 参数描述 */
  description?: string;
}

// ==================== 代理端口 ====================

export interface ProxyPort {
  /** 目标子节点 ID */
  sub_node_id: string;
  /** 端口索引 */
  port_index: number;
  /** 端口名称 */
  name: string;
}

// ==================== 模块定义（列表轻量版） ====================

export interface ModuleDefinition {
  /** 模块ID */
  id: string;
  /** 模块类型标识符（如 Conv2d / PMSFA） */
  type: string;
  /** 显示名称（中文） */
  display_name: string;
  /** 分类 */
  category: ModuleCategory;
  /** 是否为复合模块 */
  is_composite: boolean;
  /** 来源 */
  source: string;
  /** 版本号 */
  version: number;
  /** 参数声明列表 */
  params_schema: ParamSchema[];
  /** 代理输入端口 */
  proxy_inputs: ProxyPort[];
  /** 代理输出端口 */
  proxy_outputs: ProxyPort[];
}

// ==================== 模块定义（详情完整版） ====================

export interface ModuleDefinitionDetail extends ModuleDefinition {
  /** 完整 schema_json */
  schema_json: {
    type: string;
    category: string;
    display_name: string;
    is_composite: boolean;
    params_schema: ParamSchema[];
    proxy_inputs: ProxyPort[];
    proxy_outputs: ProxyPort[];
    sub_nodes?: unknown[];
    sub_edges?: unknown[];
  };
  created_at?: string;
  updated_at?: string;
}

// ==================== 模型架构节点和边 ====================

export interface ModelNodeData {
  /** 模块类型（如 PMSFA） */
  moduleType: string;
  /** 模块名称（兼容旧字段） */
  moduleName: string;
  /** 显示名称 */
  displayName: string;
  /** 当前参数值 */
  parameters: Record<string, unknown>;
  /** 输入端口 */
  inputPorts: PortDefinition[];
  /** 输出端口 */
  outputPorts: PortDefinition[];
  /** 节点描述 */
  description?: string;
  /** 图标 */
  icon?: string;
  /** 是否为复合模块 */
  isComposite?: boolean;

  /** 运行时状态：复合节点是否折叠。undefined 视为 true（默认折叠）。不持久化。 */
  collapsed?: boolean;

  /** 运行时状态：该复合节点的完整 schema（含 sub_nodes/sub_edges）是否已加载。undefined 视为 false。不持久化。 */
  subLoaded?: boolean;
}

export interface ModelNode {
  /** 节点ID */
  id: string;
  /** 节点类型 */
  type: 'module';
  /** 节点位置 */
  position: {
    x: number;
    y: number;
  };
  /** 节点数据 */
  data: ModelNodeData;
}

export interface ModelEdge {
  /** 边ID */
  id: string;
  /** 源节点ID */
  source: string;
  /** 源端口ID */
  sourceHandle?: string;
  /** 目标节点ID */
  target: string;
  /** 目标端口ID */
  targetHandle?: string;
  /** 边类型 */
  type?: string;
}

// ==================== 模型元数据 ====================

export interface ModelMetadata {
  input_shape?: [number, number, number];
  num_classes?: number;
  description?: string;
}

export interface ModelViewport {
  x: number;
  y: number;
  zoom: number;
}

export interface ModelArchitecture {
  nodes: ModelNode[];
  edges: ModelEdge[];
  metadata: ModelMetadata;
  viewport?: ModelViewport;
}

// ==================== 模型构建器配置 ====================

export interface ModelBuilderConfig {
  id: string;
  name: string;
  description?: string;
  architecture_json: ModelArchitecture;
  code_snapshot?: string;
  input_shape?: [number, number, number];
  num_classes?: number;
  base_model?: string;
  production_line_id?: string;
  created_by: string;
  is_public: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

/** 配置列表项（简化版） */
export interface ModelBuilderConfigListItem {
  id: string;
  name: string;
  description?: string;
  base_model?: string;
  num_classes?: number;
  is_public: boolean;
  version: number;
  created_at: string;
}

// ==================== 创建/更新请求 ====================

export interface ModelBuilderConfigCreate {
  name: string;
  description?: string;
  architecture_json: ModelArchitecture;
  input_shape?: [number, number, number];
  num_classes?: number;
  base_model?: string;
  is_public: boolean;
}

export interface ModelBuilderConfigUpdate {
  name?: string;
  description?: string;
  architecture_json?: ModelArchitecture;
  input_shape?: [number, number, number];
  num_classes?: number;
  base_model?: string;
  is_public?: boolean;
  code_snapshot?: string;
}

// ==================== 验证相关 ====================

export interface ConnectionValidationResult {
  valid: boolean;
  reason?: string;
}

export interface ModelValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

// ==================== 查询参数 ====================

export interface MLModuleQuery {
  category?: ModuleCategory;
  search?: string;
}

export interface ModelBuilderConfigQuery {
  search?: string;
  include_public?: boolean;
}

// ==================== React Flow 扩展 ====================

import type { Node, Edge } from '@xyflow/react';

/** React Flow 节点类型 - 使用 Record<string, unknown> 以满足类型要求 */
export type RFNode = Node<Record<string, unknown>, 'module'>;

/** React Flow 边类型 */
export type RFEdge = Edge;
