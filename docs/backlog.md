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

## [A-cleanup 合集 · 触发时机：A-5 完成后] 画布 UX 小 bug

**触发时机**：Phase 4b A 组（画布展开/折叠重构）A-5 完成后，A-cleanup 阶段一次性统一修。

本合集里的条目如果严重影响 A 组其他施工时，可以提前单独修。否则等 A-cleanup。

### 子项 1：画布连线无法按 Delete 键删除

**现状**：选中连线后按 Delete / Backspace 无反应，只能用 Ctrl+Z 回退。

**根因推测**：React Flow 默认支持 Delete 删除，`ModelCanvas.tsx` 的 `deleteKeyCode={['Backspace', 'Delete']}` 配置看似正确，但 `onKeyDown` 里的删除逻辑只处理了 `selectedNode`，没处理选中的 edge。

**修法**：
- 画布维护 `selectedEdge` 状态，或改用 React Flow 原生的 edge selection
- `onKeyDown` 里补上删除 edge 的分支

**文件**：`frontend/src/components/model-builder/ModelCanvas.tsx`

**预估成本**：15-30 分钟。

### 子项 2：刷新后 viewport 不恢复，节点在视口外

**现状**：刷新页面后画布 viewport 回到默认 `(0, 0, zoom=1)`，但节点保留在用户最后拖拽的坐标。用户看到空白画布，需要滚动/缩放才能找到节点。

**根因推测**：(a) zustand persist 的 partialize 没包含 viewport；(b) 加载 localStorage 草稿时没触发 fitView()。

**修法**：
- 方向 A：改 partialize 把 viewport 加入持久化
- 方向 B：在画布 mount 时调 ReactFlow 的 fitView()
- 两者可结合

**文件**：`frontend/src/stores/modelBuilderStore.ts` + `frontend/src/components/model-builder/ModelCanvas.tsx`

**预估成本**：30 分钟 - 1 小时。

### 子项 3：dev server 多实例规范性问题

**现状**：开发过程中反复出现 5173/5174/5175 多 vite 实例同时跑的情况。根因是 Claude Code 和用户各自启动 dev server 且没有终止机制。症状：浏览器访问错端口白屏、@vite/client 串线、auth token 对不上。

**修法**：
- 把"启动 dev server 前检查 5173 占用"的流程写入 `docs/qa-scripts.md`
- 或在启动脚本里加端口检查
- 用户侧养成 `netstat -ano | findstr :5173` → `taskkill /PID <PID> /F` 的习惯

**文件**：`docs/qa-scripts.md`（新建或扩充）

**预估成本**：10 分钟写文档。

### 子项 4：vite.config.ts.timestamp-*.mjs 临时文件泄漏

**现状**：`pnpm run dev` 启动时 Vite 会生成 `frontend/vite.config.ts.timestamp-*.mjs` 临时文件。当前没有被 `.gitignore` 忽略，偶尔出现在 `git status` untracked 列表里污染工作区观感。

**修法**：
- 在 `frontend/.gitignore` 里加一行 `vite.config.ts.timestamp-*.mjs` 或 `*.timestamp-*.mjs`
- 删除已存在的临时文件（`del frontend\vite.config.ts.timestamp-*.mjs`）

**文件**：`frontend/.gitignore`

**预估成本**：5 分钟。

### 子项 5：A-3c 错误态未做浏览器 integration 验证

**现状**：A-3c 的加载失败 + 重试按钮逻辑只做了单元测试覆盖（mock store 返回 error），没做浏览器真实触发（网络离线 + 刷新）的 integration 验证。代码路径全对但未实地验过。

**修法**：浏览器验证时顺便跑一次"DevTools Network 设 Offline → 展开新的 composite 节点 → 看到加载失败 + 重试按钮"的流程，确认没有视觉 bug 或交互死循环。

**文件**：无改动，仅验证。

**预估成本**：5 分钟（验证通过）；如果发现 bug 视具体情况。

## [P2] 展开态子画布视觉质量提升（流水线布局 + 直角折线）

**触发时机**：A-5 完成后的 A-cleanup，或 B/E 组结束后评估是否并入"结构图导出"feature（见下方"依赖决策"）。

**现状**：
A-3c + A-3c-hotfix 实现了展开态子画布的基本渲染（React Flow 默认风格节点 + 贝塞尔曲线）。用户浏览器验证时反馈视觉上"有点怪"：
- 子节点位置重叠（根因：schema.json 原始 position 纵向密集，机械 `(x,y) → (y,x)` 转置后横向分布不均匀）
- 连线互相交叉 / 穿过节点
- 整体不如论文结构图（如 YOLOv11 的 C3K2 图）清晰

**对比目标**：论文风格结构图，特征：
- 模块用色块区分类型（Conv/Split/C3K/Contact 等各自颜色）
- 直角折线连接（不是贝塞尔）
- 严格的流水线分层（x 坐标分 0/1/2/3... 阶段，每阶段 y 对齐）
- 节点间距规整、不重叠

**两条候选路径**：

**路径 A（平台内嵌）**：改 A-3c 的 SubGraphView
- 引入 dagre 或 elk.js 自动布局
- 重写 ChildAtomicNode 样式（去掉端口圆点、加类型色块、改字号）
- SubEdgeLine 改为直角折线算法
- 模块类型到颜色的映射表（14 个复合 + 23 个原子模块）
- 成本：2-4 小时

**路径 B（独立工具）**：新开"结构图导出"feature
- 生成 Mermaid / PlantUML / dot 文件，用户可以嵌进论文
- 独立 feature，不依赖展开态视觉
- 成本：2-3 天工作量
- 更适合论文级别使用场景

**依赖决策（用户待拍板）**：
A 还是 B？两条路径差异很大，不应同时投入。B 更适合论文场景但工作量大；A 成本低但平台视觉风格会分裂（展开态变"论文图"其他地方还是"交互式编辑器"）。

**建议决策时机**：B/E 组结束后再判断。那时 YAML 导入导出能力已有，"结构图导出"是否值得投入会更清楚。

## [P2] Phase 4a schema 坐标标注规范统一

**背景**：
Phase 4a 的 14 个复合模块 schema.json 里 sub_nodes 的 position 用了纵向布局（所有节点 x≈100，y 递增）。这导致 A-3c 需要在 SubGraphView 里做 `(x,y) → (y,x)` 运行时转置才能在横向画布上正确显示。

转置是运行时纠偏，不是根治。schema 的 source of truth 和视觉呈现不一致，未来新标 schema（如 custom 模块）如果用横向布局，A-3c 的转置反而会搞反。

**修法候选**：
- 方向 1：统一把 14 个 schema.json 的 position 改为横向布局（所有 x 递增，y≈100 左右），去掉 A-3c 的运行时转置
- 方向 2：在 schema.json 里加 `layout_direction: "horizontal" | "vertical"` 字段，前端根据字段决定是否转置
- 方向 3：留着不改，把"纵向布局 + 运行时转置"固化为约定（在文档里写明，custom 模块也要遵循）

**触发时机**：
- Phase 5 开工 gate 顺手做（和"领域模型命名规范"同批次讨论 schema 规范）
- 或 D 组（封装/解封装）开工前（封装新模块时用户会手动标坐标，此时必须定规则）

**预估成本**：
- 方向 1：1-2 小时（14 个 schema × 平均 8 个 sub_nodes，手动重标）
- 方向 2：30 分钟（加字段 + 改 SubGraphView 的转置条件）
- 方向 3：10 分钟（只写文档）

**与 "展开态视觉提升" 的关系**：
如果采纳"展开态视觉提升（路径 A）"引入自动布局库，schema 里的 position 就变成"用户意图提示"而不是"精确坐标"，本条 backlog 的紧迫性降低。建议两条一起决策。

## [P3] 模块详情 API 缓存粒度

**背景**：
INV-01 报告观察到：前端每次拖拽一个模块到画布就调一次 `GET /models/modules/{type}` 详情 API。如果用户拖 3 个 Conv2d，就请求 3 次同样的数据。

A-3c 已经用 `moduleSchemas` store 缓存避免了重复请求，但那是展开态懒加载的场景。拖拽时模块库的 `ModuleLibrary.tsx` 是否走同样的缓存，需要核实。

**触发修复**：A 组收尾时或下次修 ModuleLibrary.tsx 时顺手看。

**修法**：如果 ModuleLibrary 也走 `moduleSchemas` 缓存就收敛；否则考虑把 `moduleSchemas` 的 action 抽到更上层（或提供一个公共 `useModuleSchema(type)` hook）。

**预估成本**：30 分钟 - 1 小时。

## [P3] React Router v7 迁移预警

**背景**：
Console 持续出现两条 React Router v6.x 的 Future Flag Warning：
- `v7_startTransition` 未开启
- `v7_relativeSplatPath` 未开启

这是 React Router v7 迁移的提前预警，不是 bug。可以通过设置 future flags 立即静音，也可以等真升级 v7 时再处理。

**触发修复**：
- 短期（静音）：5 分钟，加两行 router 配置
- 长期（真升级）：React Router v7 发布后评估，1-2 小时

**预估成本**：见上。

## [P3] React Flow 动态 Handle 必须显式调用 updateNodeInternals（知识点）

**背景**：
Phase 4b A-3b-hotfix 发现：React Flow v12 的 `nodeInternals` 测量系统不会自动响应 Handle 数量的运行时变化。动态端口机制（concat 的 `input_ports_dynamic: true`）在 A-3b-fix 里数据层已经完全正确工作（useNodeConnections 返回实时连接数、computeDynamicPorts 正确扩展端口数组），但 React Flow 画布上仍只显示初始端口数量，导致连线命中测试失败。

**已修复方式**：用 `useUpdateNodeInternals` hook 在端口数量变化时显式触发重新测量。

**性质**：非待办，是经验条目。保留作为**未来所有涉及动态 Handle 场景的检查清单**：
- 复合节点展开态渲染子 Handle 时（A-3c 用了普通 div 规避了此问题）
- 节点根据某个 prop 切换端口数量时
- 自定义节点有任何运行时端口变化时

**伴生教训**：React Flow 的运行时测量系统属于**单元测试盲区**，jsdom 环境不运行 measureNode。未来所有 React Flow 相关提示词必须在验收剧本里声明"需要浏览器手动验证"。