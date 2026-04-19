# Backlog

## Phase 4b 清扫阶段完成记录（2026-04）

- PP-0（前端 vitest 基建）：完成
- CL-01（档 1 机械清扫，unused imports/variables/types）：完成，46 条错误清零
- CL-02a（α 方案扩散面扫描）：完成
- CL-02b（α 方案全量重命名）：完成，14 条 TS2300 清零

**成果**：frontend TS 错误总数 145 → 83（减少 62 条，减少比例 43%）。
**详细决策归档**：见 `docs/phase-4b-cleanup-summary.md`

## P3 — 删除节点时 toast 显示 undefined

**现状**: 删除节点时 toast 显示 "已删除节点"，但如果 toast 想显示节点名，当前会读到 undefined。
**修法**: toast 调用放在 `setNodes` 之前（先读 `selectedNode.data.displayName` 再删），或在 store 里保留被删节点的副本用于通知。
**文件**: `frontend/src/components/model-builder/ModelCanvas.tsx`

## P2 — Axios 并发刷新 token 竞态

**现状**: response interceptor 没有全局 refresh promise。多个并发请求同时 401 时，每个请求都会独立触发刷新流程，可能产生多余的 refresh 请求。
**修法**: 用全局 `let refreshingPromise: Promise<void> | null = null` 让所有 401 请求等待同一个刷新完成。刷新完成后统一重试队列中的所有请求。
**文件**: `frontend/src/services/api.ts`
**影响**: 第四步展开复合节点时会频繁并发拉取详情 API，此问题会被放大。

**[已关闭 · Phase 4b 清扫阶段 INV-01 确认]**
实际在 Phase 4a 已落地（frontend/src/services/api.ts 第 29 行 refreshingPromise + queueMicrotask 清锁）。
本条为误挂，关闭。

## P3: 模型配置保存时自动归一化节点坐标

**现状**：
- React Flow 的 flow 坐标系原点可以不在视觉中心
- 用户操作后节点坐标可能出现大负数（如 x: -1566, y: -324）
- 当前靠 fitView 在加载时兜底显示，但保存下来的 YAML/JSON 里坐标是脏的

**影响**：
- YAML diff 难以阅读（坐标偏移导致大量无意义变更）
- 外部协作时（导入到其他工具）坐标体系不统一

**建议修复时机**：Phase 4b（YAML 导入导出）
- 保存前遍历所有节点，找到最小 x/y，将所有节点平移使最小坐标为 (0,0)
- 或在加载后提供"归一化坐标"按钮

---

### [Phase 5 前置任务] 领域模型命名规范确立

**性质**：非 P1/P2/P3，是 Phase 5 开工 gate，必做不可跳过

**背景**：
Phase 4b 清扫阶段（CL-02）修复了 augmentation 和 generation 两个模块共享的 7 个同名类型（CreateTemplateRequest / UpdateTemplateRequest / CreateJobRequest / JobListQuery / JobControlRequest / JobControlResponse / JobProgressResponse）产生的 14 条 TS2300 duplicate identifier 错误。根因是两个业务模块自然共享"模板"和"任务"等领域概念，但未建立统一的命名前缀规范。

**触发时机**：Phase 5（训练模块）开工的第一条提示词之前。

**必做内容**：
- 审视所有业务模块（augmentation/generation/training/testing/pruning/distillation）共享的公共概念（Template/Job/Config/Request/Response 等）
- 确立 `<Module><Name>` 前缀命名规则作为项目规范（驼峰形式，例：AugmentationCreateTemplateRequest / TrainingCreateJobRequest）
- 写进 `docs/coding-standards.md`（如该文件不存在则新建）
- Phase 5 开工的第一条提示词必须显式引用这份规范

**不做的风险**：Phase 5 训练模块引入 CreateJobRequest / UpdateJobRequest / JobListQuery 等通用名字时，会和 augmentation/generation 再撞一次 TS2300，需要重复 CL-02 的清扫工作。

**预估成本**：规范制定 30 分钟，写文档 30 分钟，合计约 1 小时。

## [P1] ApiResponse 泛型契约统一

**背景**：
Phase 4b 清扫阶段 INV-01 报告显示，frontend 共有 12 条 TS18046 "is of type 'unknown'" 错误，全部分布在 `response.data.data` 或 `data` 的访问上，横跨 AugmentationPage、DatasetDetailPage、DatasetListPage、previewService.ts 等文件。根因是 axios 的 `ApiResponse<T>` 泛型契约未在类型定义层统一传递——某些接口未正确传入泛型参数，导致 `data` fallback 为 `unknown`。

**性质**：基础设施级类型契约问题，影响所有业务模块的 API 调用。

**触发时机**：开始任何新业务模块（Phase 5+）且涉及 API 调用前，或下次深度修改 `src/services/api.ts` 时。

**预估成本**：2-4 小时，需要系统审视 api.ts 的所有 endpoint 定义并逐一补齐泛型。

## [P2] GenerationPage PlacementStrategy 类型对齐

**背景**：
GenerationPage.tsx 当前有 37 条 TS 错误（TS2339 / TS2322 / TS2353 组合）源于 PlacementStrategy 类型定义与业务实现脱节。类型定义只声明了部分字段（例如 roi / type），但业务代码使用了更多字段（grid / heatmap / defects_per_image 等）。

**触发修复**：下次修改 GenerationPage.tsx 相关功能时顺手修。

**预估成本**：1-2 小时，需要先和产品确认 PlacementStrategy 支持哪些字段。

## [P2] previewService 字段缺失

**背景**：
previewService.ts 有 11 条 TS2339 missing property 错误，源于 PreviewResponse 类型定义滞后于后端真实返回结构。

**触发修复**：下次动数据预览相关功能时顺手修。

**预估成本**：30 分钟 - 1 小时，需要对齐后端 /preview 接口实际返回字段。

## [P3] GenerationCreateJobRequest dead export

**背景**：
`src/types/generation.ts` 中保留的 `GenerationCreateJobRequest` 是 dead export，当前无任何代码 import。CL-02b 按"本轮范围"原则保留了这个 export。

**触发修复**：generation 模块功能稳定后（Phase 8 或之后）可删除。

**预估成本**：5 分钟。

## [P3] zustand store 的 _get 命名偏离惯例

**背景**：
项目 `tsconfig.json` 的 `noUnusedParameters` 选项强制要求未使用参数必须用下划线前缀（TypeScript 官方豁免机制）。这导致 `src/stores/augmentationStore.ts` 中 zustand immer middleware 的 `get` 参数必须写成 `_get`，偏离 zustand 社区通用命名惯例。

ESLint 的 `@typescript-eslint/no-unused-vars` 规则可以通过下划线或 eslint-disable 注释绕开，但这只影响 ESLint 不影响 TypeScript 编译器——两者是独立检查路径。

**触发修复**：项目做 tsconfig 大调整时（如果真要改 noUnusedParameters，需要评估全项目影响）。单独为美化命名修改 tsconfig 不值得。

**预估成本**：评估 tsconfig 影响 30 分钟，改动本身 5 分钟。
