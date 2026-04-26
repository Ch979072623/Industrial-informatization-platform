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

## [已关闭 · 2026-04-20] A-cleanup 合集（A 组收尾）

本合集的 6 个子项在 Phase 4b A 组 A-cleanup 阶段及后续 hotfix 中处理完毕。A 组结束后关闭。

### 子项 1：画布连线无法按 Delete 键删除 ✅

**状态**：A-cleanup 阶段二完成（commit `fb69192`）
**补充**：HF-1（commit `a807c42`）扩展工具栏垃圾桶按钮也支持删 edge（原提示词 scope 遗漏）
**补充**：hotfix-3 修复 onEdgeClick 从未注册导致的"选中 edge 时 selectedNode 未清、Delete 误删节点"Phase 4a 遗留 bug

### 子项 2：刷新后 viewport 不恢复，节点在视口外 ✅

**状态**：A-cleanup 阶段三完成（commit `393340a`）
**方案**：A+B 结合 —— partialize 白名单加入 viewport（持久化）+ mount 时 useRef 闸门单次调用（fitView 兜底）

### 子项 3：dev server 多实例规范性问题 ⏸

**状态**：代码侧无改动，文档侧未完成。挂独立 backlog 条目 "dev server 启动流程规范化写入 qa-scripts.md"（见下方新条目）

### 子项 4：vite.config.ts.timestamp-*.mjs 临时文件泄漏 ✅

**状态**：A-cleanup 阶段一完成（commit `8ff7808`）
**方案**：frontend/.gitignore 加规则

### 子项 5：A-3c 错误态未做浏览器 integration 验证 ⏸

**状态**：未做，挂独立 backlog 条目 "A-3c 错误态浏览器验证"（见下方新条目）

### 子项 6：反向拖线从 target handle 出发会刷 React Flow Error #008 ✅

**状态**：A-cleanup 阶段四完成（commit `97cd0d2`）
**方案**：方向 A，加 `isValidConnection` prop 到 ReactFlow 组件
**附加发现**：React Flow v12 的"反向拖线自动交换 source/target"是 UX 改进，用户确认接受

### A-cleanup hotfix 系列（2026-04-20）

A-cleanup 主交付后用户浏览器验证连续发现 5 个"新功能依赖的旧状态管理缺陷"bug，以独立 commit 修复：

- **HF-1**（commit `a807c42`）：工具栏垃圾桶按钮支持 edge 删除
- **HF-2**（commit `0f6481c`）：全局 hotkey 改 window 级监听 + input/textarea guard
- **hotfix-2**：Ctrl+S 在 input 内阻止浏览器"另存为网页"（guard 逻辑顺序修正）
- **hotfix-3**：点击 edge 时清 selectedNode（onEdgeClick 从未注册，Phase 4a 遗留）
- **hotfix-4**（commit `9892b25`）：刷新后 seed history baseline（history 栈不持久化导致首次 undo 失败）

**重要沉淀**：4 轮 hotfix 的共同根因是"新功能依赖的旧状态管理有缺陷"。详见 kickoff-log 章节 16。

**经验条目**：新功能的 QA 必须走到"依赖的旧状态机制"的边界验证，不能只看新功能自身。

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

## [P3] 后端开发环境启动机制混乱

**现状**：
Phase 4b 开发过程中反复出现"代码已改、后端 API 返回旧结构"的症状。深入调查发现三层问题叠加：

1. **启动脚本环境不一致**：
   - `setup_conda.ps1` 创建 conda 环境 `defect-detection` 并在其中装依赖
   - `start_dev.ps1` 启动后端时用 `backend/venv/Scripts/Activate.ps1`（走 venv 路径），不走 conda
   - 如果用户误用 `start_dev.ps1`，后端跑的是 venv 的 Python，与 conda 环境脱节
   - 结果：conda 环境里的最新代码改动，在 venv 启动的进程里看不到

2. **后端进程在独立窗口运行（看不到日志）**：
   - `start_dev.ps1` 用 `Start-Process powershell -ArgumentList "-NoExit"` 另开窗口跑 uvicorn
   - 主终端看不到后端状态，难以感知"没重启"这件事
   - 如果那个窗口被误关，后端可能以异常状态残留

3. **uvicorn --reload 在 Windows 下可靠性差**：
   - Python 的 --reload 依赖文件系统事件
   - Windows 下某些文件写入方式（特别是"写临时文件+rename"的原子替换）可能不触发事件
   - Claude Code 的 `str_replace` / `create_file` 工具写文件时 uvicorn 可能收不到通知

**影响**：每次后端代码改动后开发者不知道是不是真的生效，多次浪费时间排查"看起来是前端 bug 实际是后端没重载"。

**触发修复时机**：Phase 5 开始之前（Phase 5 大量改后端代码，累积时间成本不可控）。

**修法候选**：
- 方向 A（推荐）：统一到 conda 环境，修改 `start_dev.ps1` 的 `Start-Backend` 走 `conda activate defect-detection` 而不是 venv；删除 venv 创建逻辑。另提供一个"前台启动后端"选项（不要 Start-Process 另开窗口），让日志在主终端可见
- 方向 B：保留 venv 路径但和 conda 二选一，让脚本有 `-Env conda|venv` 参数
- 方向 C：引入 watchfiles 或 watchdog 替代 uvicorn 默认 reloader

**预估成本**：方向 A 约 1-2 小时（改脚本 + 文档 + 验证）。

**开发流程临时规范**（在修复之前）：
- 每次涉及后端代码改动的 Claude Code 会话完成后，用户**手动重启后端**：`taskkill /PID <后端PID> /F` + `conda activate defect-detection` + `cd backend && python -m uvicorn app.main:app --reload`
- 不要用 `start_dev.ps1` 启动后端（临时）
- 这条临时规范写进 docs/qa-scripts.md

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

## [已取消 · 2026-04-20] Phase 4b A-5 跨层级拖拽

**原设想**：
- 方向 1：从外部拖节点进入展开容器，parentId 更新
- 方向 2：从容器内拖子节点到外部，外部连线重接或断开

**取消理由**：
1. **产品等价**：用户重新表述的需求（拖拽连线自定义复合结构 + 管理员权限 + I/O 检查）等价于 D.1 "封装为新复合模块"，无需另开 A-5 任务
2. **技术被堵死**：A-3c 把子画布做成 `pointer-events-none` 博物馆玻璃罩，方向 2（从子画布拖出）事实上不可能；原始 A-5 依赖的 parentId 路径在 A-3c 选 α（普通 DOM + 绝对定位）时也被同步排除
3. **代码状态干净**：A-5-recon 确认 `ModelCanvas` 从未注册 `onNodeDragStop` 等 drag 钩子，`nestedNodes.ts` 自 A-1 起为 dead code，取消无需 rollback

**产品需求加固（转入 D.1）**：见下方"D.1 产品需求加固"条目

**证据来源**：`docs/private/A-5-recon-report.md`

---

## [P3 · 触发时机：D 组开工前] `nestedNodes.ts` 去向评估

**背景**：
`frontend/src/utils/modelBuilder/nestedNodes.ts` 提供 `flattenNodes` / `nestNodes` 纯函数，A-1 建立时预期 A-5 会用到。A-5-recon 确认截至 A-4 无任何生产代码 import（仅测试文件引用），是 dead code。A-5 已取消后该工具失去原定消费者。

**去向候选**：
- α：保留。D.1 封装逻辑如需处理选中节点之间的父子结构，`flattenNodes` 可能借得上
- β：删除工具 + 对应测试。D.1 如纯粹"选中 → 生成 schema → 保存"不经过层级计算

**触发时机**：D 组开工前（起草 D.1 提示词时根据 D.1 实现细节决定）

**预估成本**：β 约 5 分钟；α 如需改造约 30 分钟

---

## [加固 · 合并入 D.1 · 触发时机：D 组开工] D.1 "封装为新复合模块" 产品需求加固

**背景**：
A-5 取消过程中用户重新确认 D.1 的完整产品形态，在原 Phase 4b 交接文档 D.1 描述之外补充两项硬约束。

**加固项**：
1. **管理员权限**：非管理员用户不能创建新复合模块。后端 API 鉴权（`POST /models/encapsulate`）+ 前端菜单按用户角色隐藏
2. **输入输出检查**：保存前校验
   - `proxy_inputs` / `proxy_outputs` 指定的 `sub_node_id` 确实在选中节点集合内
   - 端口索引 `port_index` 在对应子节点的 schema 端口范围内
   - 选中节点之间的 `sub_edges` 构成 DAG（无环）

**触发时机**：D 组（封装/解封装）正式开工时一并实施，不单独立项

## [P3 · 触发时机：参数面板下次重度改动时] 受控 input 的 Ctrl+Z 行为不一致

**现象**：
参数面板的 number input（如 in_channels、out_channels 等）内进行"全选 + Delete + 输入新值"的编辑序列后，按 Ctrl+Z 可能出现部分撤销的中间态（如输入框显示 `064` 且 `64` 仍选中），而不是清晰回到编辑前的值。

**根因**：
React 受控组件的 `value` 由 state 管理，浏览器 input 的原生 undo 栈操作 DOM，两者脱节。这是 React + controlled input 的固有行为，不是项目代码 bug。

**影响范围**：
所有 React 受控 input，不限于参数面板。但参数面板是用户最可能触发这种编辑序列的地方。

**修法候选**：
- 方向 α：参数面板维护自己的 undo 栈，接管 Ctrl+Z 在 input 内的行为（`event.preventDefault()` + 自定义 undo）
- 方向 β：把参数面板的每次修改纳入全局 zustand history 栈（通过 `saveHistory` 在 onBlur 时触发）
- 方向 γ：不修，写进用户文档说明"参数编辑请用拖选+输入直接覆盖"

**触发时机**：
参数面板下次重度改动时（如 Phase 4b 参数校验增强、或 C 组模型验证返回的参数面板实时推算功能开工时）一并处理。单独为此修改不值得。

**发现来源**：Phase 4b A-cleanup-hotfix 浏览器验证阶段，2026-04-20

## [已落地 · 2026-04-20] 论文源码私有化目录

**位置**：`backend/app/ml/paper_reference/`

**目录结构**：
- `ultralytics/` — 魔改版 YOLOv11，含论文三模块（PMSFA / FocusFeature / Detect_SASD），用于 Phase 5 模型训练、Phase 6 模型测试、B 组等价性测试
- `ultralytics-yolo11-20251219/` — 纯净 YOLOv11 基线，用于 Phase 7 剪枝、Phase 8 蒸馏（因剪枝蒸馏需在 YOLO 源码上加文件改东西，单独留一份干净基线）
- 其他工具脚本：`get_FPS.py` / `get_model_erf.py` / `heatmap.py` / `plot_channel_image.py` / `plot_result.py` / `track.py` / `train.py` / `transform_PGI.py` / `transform_weight.py`
- `README.md` — 占位 + 目录用途说明（白名单保留，非私有）

**gitignore 规则**：整体 `backend/app/ml/paper_reference/**` 忽略，白名单放行 `!backend/app/ml/paper_reference/README.md`

**用途**：
- B 组代码生成的等价性测试（PMSFA / FocusFeature / Detect_SASD 三模块的 shape & 数值对比）走**魔改版**（`ultralytics/`）
- Phase 7 剪枝 / Phase 8 蒸馏走**纯净基线**（`ultralytics-yolo11-20251219/`）
- 学术追溯：论文核心贡献的"source of truth"参考基线

**关键产品决策**：平台 composite 模块 = 对外 source of truth（已经过等价性测试对齐论文）；论文原版 = 私有保留，仅用于校验。GitHub 开源时其他人不需要论文源码即可使用平台；需要原生 YOLO11 基线时从 Ultralytics 官方获取。

---

## [E 组前置 · 触发时机：E 组开工前（可在 B 组期间提前补 1-2 个）] YOLO11 原生模块补齐

**背景**：
用户论文以 YOLOv11 为基线进行改进（Phase 5-8 均基于 YOLOv11 结构）。Phase 4b 任务组 E（YAML 导入导出）要支持导入 yolo11.yaml 基线作为起点，但 Phase 4a 实现的 14 个 composite 模块**不包含 YOLO11 原生模块**，需要补齐。

**缺失模块清单**（对照 yolo11.yaml）：

| 模块 | 类型 | 用途 |
|---|---|---|
| `Conv`（ultralytics 版） | composite | Conv + BN + SiLU，YOLO 通用基本块（区别于已有 `Conv_GN`） |
| `C3k2` | composite | YOLO11 引入的新 block |
| `SPPF` | composite | Spatial Pyramid Pooling Fast（YOLOv5+） |
| `C2PSA` | composite | YOLO11 特有 PSA 注意力 block |
| `Detect`（ultralytics 版） | composite | YOLO 原生检测头（区别于项目的 `Detect_SASD`） |

**已有可复用**：`Concat`（原子模块）、`nn.Upsample`（需确认注册名）

**技术路径**：路径 α（平台内重新实现，用户 2026-04-20 决策）
- 按 ultralytics 源码在项目的 composite 模块体系内重建 schema.json + module.py
- 每个模块走 Phase 4a 已建立的"论文模块"标准流程（schema.json + module.py + 等价性测试）
- 优点：学术追溯一致、用户可展开查看内部、不依赖 ultralytics 作为运行时依赖
- 放弃路径 β（ultralytics passthrough）：会打破"学术追溯"产品主线，用户明确拒绝

**触发时机策略**：
- **B 组期间可提前补 1-2 个**：B 组代码生成的等价性测试需要样本，补一个如 `C3k2` 作为测试 case 扩展覆盖
- **E 组开工前必须全部补齐**：yolo11.yaml 导入依赖这些模块全部已注册

**预估成本**：
- 每个 composite 模块约 1-2 小时（schema 标注 + module.py + 等价性测试）
- 5 个模块 ≈ 6-10 小时
- 可分散在 B/C/D 组期间完成

**基线画布落地**：本任务完成后，yolo11 基线画布 = "E 组导入功能加载 yolo11.yaml"，**不是额外独立 feature**

---

## [Phase 4d · 触发时机：Phase 4d 开工] 模块代码浏览器页面

**背景**：
用户希望在平台内查看 composite 模块的 Python 源码，方便审查实现质量。独立 feature，归入 Phase 4d（模板管理 + 自定义模块）。

**产品定位**：
- **只读代码浏览器**，不是编辑器
- 数据源：`backend/app/ml/modules/composite/*/module.py`（用户 2026-04-20 决策为数据源 (a)）
- **关键副作用**：论文源码从公共代码解耦——GitHub 开源项目时浏览器只展示 composite 实现，论文源码保持私有

**UI 设计要点**：
- 独立页面（不在模型构建页面内）
- 左侧：模块名目录树（按类别分组：backbone / neck / head / attention / paper / 其他）
- 右侧：选中模块 → 展开查看源码
- 源码高亮（Monaco Editor 或 shiki）
- AST 分块标注（class 定义 / forward 方法 / `__init__` 等）
- 权限：管理员可见；普通用户视角需要单独决策

**实现方向（未定）**：
- 方向 A：后端 API `GET /models/modules/{type}/source` 返回文件纯文本 + AST 元数据，前端用 Monaco 渲染
- 方向 B：完全前端实现（vite `import.meta.glob` 把模块代码作为 raw text 打包），但需要和 Vite 配置协调
- 方向 C：后端 API 返回文本，前端用 shiki 高亮（轻量替代 Monaco）

**扩展空间**：
- 未来可扩展数据源到 (b) 论文源码、(c) ultralytics 源码，但权限需要更严格
- 可加搜索 / 批注功能

**触发时机**：Phase 4d 开工

**预估成本**：2-3 天（含后端 API、前端组件、权限、AST 解析、高亮集成）

---

## [P3 · 触发时机：Phase 5 开工前] dev server 启动流程规范化写入 qa-scripts.md

**背景**：
A-cleanup 子项 3 原计划挂入 `docs/qa-scripts.md`，但 A-cleanup 阶段只处理了代码子项（1/2/4/6），文档子项未完成。

**内容**：
- 启动 dev server 前检查 5173 占用（`netstat -ano | findstr :5173`）
- Claude Code 启动后立即 Ctrl+C 关闭，避免和用户启动的 dev server 串线
- 清理残留 vite 进程的命令

**触发时机**：Phase 5 开工前一并写入 qa-scripts.md

**预估成本**：15 分钟写文档

---

## [P3 · 触发时机：A-3c 下次修改时或 Phase 5 开工前] A-3c 错误态浏览器验证

**背景**：
A-3c 的展开态"加载失败 + 重试"路径只做了单元测试覆盖（mock store 返回 error），未做浏览器 DevTools Network Offline 场景的真实验证。代码路径全对但未实地验过。

**验证动作**：
- 浏览器 DevTools Network 设 Offline
- 展开一个新 composite 节点（未加载过 schema）
- 看到加载失败 UI + 重试按钮
- 恢复网络 + 点重试 → 正常加载

**触发时机**：A-3c 下次修改时顺手验证；或 Phase 5 开工前统一扫尾

**预估成本**：5 分钟验证；如发现 bug 视情况

## [Phase 4d · 触发时机：Phase 4d 开工 OR B 组 MVP 交付后] 模块库扩展：用户上传自定义模块代码

**背景**：
用户 2026-04-21 提出希望能"自己输入代码注册一个新的原子或模块"，验证后归并到模块库页面扩展方向（而非独立的"模型配置页面"）。

**产品形态**：
- 模块库（ModuleLibrary 组件）右上角加"注册新模块"按钮
- 弹窗含：模块名、is_composite 开关、schema_json 编辑器、Python 代码粘贴区
- 后端验证代码合法性（ast.parse 通过 + import 白名单 + 无副作用）后写入 ModuleDefinition 表
- 代码文件落地到 `backend/app/ml/runtime/extra_modules/user_uploaded/` 独立子目录

**关联**：Phase 4d 模板管理 + 自定义模块功能；和 B-2 的 generate_module_code 产出共用 extra_modules/ 目录

**触发时机**：Phase 4d 开工；或 B 组 MVP 交付后用户实际有"先上传自定义模块再用"需求时提前

**预估成本**：3-5 天（含代码合法性校验）


## [B 组 · 触发时机：B 组 MVP 交付后评估] B-3/5/6 Architecture 部分节奏决定

**背景**：
G5 决策 MVP 只做 B-0/B-1/B-2/B-4（Module 交付路径）。Architecture 部分（yaml 导出 + 加载测试 + UI）延后评估。

**待评估的事**：
1. Module MVP 实际使用中是否暴露新需求导致 B-3/5/6 scope 再调整
2. B-3（Architecture YAML 生成器）是否合并入 E 组 "yaml 导入导出"任务一起做
3. B-5（YAML 加载测试）的容差策略（是否要做数值等价、还是只验证加载成功）
4. B-6（UI）的 Module/Architecture 生成按钮是分开还是合并

**触发时机**：B-0/1/2/4 完成后、进入 B-后半前

**预估成本**：待评估决定


## [遗留清理 · 触发时机：Phase 5 开工前 OR 代码审查时顺手] 遗留 ORM 表清理

**背景**：
B-1 + B-1c 侦察发现两张遗留表**无任何代码引用**：
- `backend/app/models/model_config.py` 的 `ModelConfig` 类（被 `ml_module.ModelBuilderConfig` 替代）
- `backend/app/models/ml_module.py:14` 的 `MLModule` 类（被 `ModuleDefinition` 替代）
- `backend/app/db/seeds/ml_modules_seed.py` 的旧种子数据（含 num_layers 等已废弃字段）

**清理动作**：
- 确认无代码依赖（grep 全项目）
- 删除 ORM 文件
- 生成 Alembic migration 删除对应数据库表
- 删除 seed 文件

**风险**：可能有文档或未来计划依赖这些表；需要和 SQL migration 历史协调

**触发时机**：Phase 5 开工前清理（避免训练系统引入新的陈旧表引用）；或代码审查时顺手做

**预估成本**：2-4 小时（含 migration 验证）


## [B-0 · 触发时机：B-0 施工中] Module 画布旧数据向后兼容

**背景**：
B-0 引入 `mode` 字段后，现有保存的 ModelBuilderConfig 记录没有 mode 字段。B-0 需要向后兼容——旧数据默认按 architecture 处理。

**需要做**：
- 前端：加载旧 config 时若 metadata.mode 不存在，默认 'architecture'
- 后端：Pydantic schema 的 mode 字段设 Optional 默认值 'architecture'

**触发时机**：B-0 施工时内联处理

**预估成本**：30 分钟（在 B-0 提示词里作为硬约束写入）

## [B-1 · 触发时机：B-1 起草时] 保存对话框分模式渲染

**背景**：
B-0 完成后浏览器验证发现当前保存对话框对 Module 和 Architecture 不区分。按 G4=β 决策，Module 画布保存应写入 ModuleDefinition 表（注册为可用模块），Architecture 画布保存写入 ModelBuilderConfig 表（当前行为）。

**需要做**（归入 B-1 前端分支，非独立条目）：
- 保存对话框读取 store.mode
- Module 模式：标题"注册为新模块"+ 字段 moduleName/displayName/category/description
- Architecture 模式：标题"保存模型配置"+ 字段保持当前
- 调用分支：Module → `POST /api/v1/models/modules`（B-1 后端产出）；Architecture → `POST /api/v1/model-configs`（保持）

**触发时机**：B-1 开工时一起做，不单独立条目

**产生背景**：B-0 浏览器验证阶段识别，避免"前端先改后端后补"造成虚假就绪

## [基建 · 已落地 · 2026-04-21] 提示词模板 v1

**位置**：`docs/private/prompt-template.md`

**内容**：整合 A-1 + hotfix-3/4 + B-0-HF1 经验的统一提示词模板，12 章节结构，适配侦察/施工/hotfix/文档四类任务

**触发改进**：每次 B-1/B-2/B-3... 使用时发现模板漏项，迭代版本号（v2 / v3...）并在 kickoff-log 记录

**成本**：0（本轮已落地）

## [P3 · 触发时机：代码审查时统一回归 / 或 Phase 5 训练 API 引入鉴权时一起改] inline admin 检查回归到 Depends 风格

**背景**：B-1 因 FastAPI 闭包参数 override 在 pytest 中的局限，POST /modules endpoint 采用 `Depends(get_current_user)` + inline `if role != "admin"` 而非 `Depends(require_admin)`。鉴权语义等价但和项目其他 endpoint 风格不一致。

**触发**：Phase 5 训练 API 引入鉴权时统一审视，或代码审查发现风格偏移时

**预估成本**：1-2h（修 fixture override 写法 + 改 endpoint 依赖声明）


## [P3 · 触发时机：模块库 UX 优化批次] ModuleLibrary 暴露刷新 API 替代 key 重新挂载

**背景**：B-1 注册新模块后用 `key={moduleRefreshKey}` 触发 ModuleLibrary 重新挂载来刷新列表。副作用：丢失搜索框输入、展开折叠状态、滚动位置。

**改进方向**：ModuleLibrary 用 forwardRef + useImperativeHandle 暴露 reload() 方法，或迁移到 zustand 全局 store

**触发**：用户实际使用中反馈"注册后搜索状态丢失"等问题；或 D 组（节点交互优化）开工

**预估成本**：2-3h


## [P3 · 触发时机：Phase 5 开工前 OR 后端测试套件清理批次] backend test_augmentation.py CreateJobRequest 导入失败

**背景**：B-1 阶段零侦察发现 `backend/tests/test_augmentation.py` 因 `CreateJobRequest` 导入失败而无法收集，属于 B-1 之前的遗留问题。

**影响**：后端测试套件不干净，"哪些失败是新引入的哪些是历史遗留"的判断成本累加

**触发**：Phase 5 训练 API 涉及 augmentation job 时一起处理；或后端测试套件统一清理批次

**预估成本**：1-2h（找到 CreateJobRequest 应在哪定义 + 修 import）

## [P3 · 触发时机：dynamic_builder 改动批次或 Phase 5 训练对接时] sub_edges 缺 id 字段

**背景**：B-1 hotfix-3 诊断时发现 canvas_to_schema 写入的 sub_edges 是 `{source, source_port, target, target_port}` 结构，**缺 id 字段**。当前 dynamic_builder 按 source/target 索引消费不需要 id，但未来 sub_edges 级精细操作（如错误定位、序列化往返）会缺 id 而难追溯。

**触发**：dynamic_builder 改动批次；或 Phase 5 训练时序列化 sub_edges 出现追溯需求

**预估成本**：30 分钟（converter 加 id 生成 + 1 条测试）

## [中优先 · 触发时机：B-后半 OR Module 画布功能扩展批次] Module 画布支持子节点参数提升为对外参数

**背景**：
B-1 浏览器验证（2026-04-21）发现：用户在 Architecture 画布点击 Module 节点（如 AnotherTest）时，参数面板显示"此模块没有可配置参数"。

**根因**：B-1 注册 Module 时 `params_schema: []` 写死，MVP 不支持用户在画布上声明对外参数。但用户体感是 "我的 block 内部 Conv2d 应该能调 in_channels 才对"。

**产品形态需求**：
- Module 画布上应能选中某个内部子节点的某个参数
- 标记该参数为"对外暴露"，给一个对外参数名（如 `out_channels` → 暴露为 `c_out`）
- 注册时 params_schema 自动生成
- 支持 `${...}` 表达式（如多个子节点共用同一对外参数）

**触发时机**：B 组后半（Architecture YAML + UI 完整化）或 Module 画布功能扩展批次

**预估成本**：1-2 天（前端 UI + 后端 schema 同步 + 测试）

**关联**：和 B-2 代码生成器有交集——生成器需要把对外参数正确传递到子节点的 forward 调用

---

## [P3 · 触发时机：用户登录态相关问题修复批次] 后端重启后前端登录态失效缺乏明确提示

**背景**：B-1-hotfix-3 验证时遇到——后端重启后 SQLite 数据库重建，旧 token 失效。前端 `/api/v1/auth/me` 返回 401，但**没有自动跳转到登录页**，主页"看起来登录了"但所有接口都 401。

**改进方向**：axios interceptor 检测到 401 → 清 localStorage token → 跳转 /login

**触发时机**：用户首次反馈登录态相关问题时；或 Phase 5 引入更多 protected 路由时

**预估成本**：1-2 小时

---

## [P3 · 触发时机：开发环境优化批次] Vite 缓存 ERR_CACHE_READ_FAILURE 自愈机制

**背景**：B-1-hotfix-3 后用户遇到 Vite 预构建缓存损坏（`node_modules/.vite/deps/*.js` 读取失败），症状是动态 import 失败、整个页面打不开。手动 `Remove-Item -Recurse -Force node_modules\.vite` 后解决。

**改进方向**：
- 在 `start_dev.ps1` 启动脚本里加一条"启动前先清 .vite"的可选步骤
- 或在 README/qa-scripts 里写明"打不开页面时优先清 .vite"故障排查流程

**触发时机**：开发环境优化批次；或第二次再遇到此问题时

**预估成本**：30 分钟（脚本改动 + 文档）

明白了，按这个格式重写：

---

## [P2 · 触发时机：B-6 前端代码预览上线前，或用户首次反馈下载的 .py 实例化失败时] codegen 生成类 `__init__` 缺少参数默认值

**背景**：
B-2 实现的 `generate_module_code` 在展开 composite 子模块时，未将子模块 `params_schema` 的默认值注入生成类的 `__init__` 签名。例如 Conv_GN 的 `p` / `g` 参数有默认值，但生成的 `__init__(self, p, g)` 不含默认值，用户直接实例化 `Conv_GN()` 会报 `TypeError: missing required positional argument`。

B-4 等价性测试中通过测试侧补丁绕过了此问题，未修改生产代码。

**修法**：`generate_module_code` 生成 `__init__` 签名时，从 `params_schema` 读取每个参数的 `default` 字段，有默认值的参数生成 `param=default` 格式。

**触发时机**：B-6 前端代码预览上线前（用户能看到生成代码时此 bug 明显）；或用户首次反馈复制 .py 后实例化报错时。

**预估成本**：1-2 小时（修 codegen.py + 补测试）

---

## [P3 · 触发时机：同上] codegen 生成签名与 `params_schema` 字段对不上

**背景**：
部分 composite 模块（如 C2f）的 `params_schema` 含有生成类签名未使用的参数（如 `n`）。`generate_module_code` 未做过滤，生成的 `__init__` 签名会包含实际 forward 里用不到的参数，或反之漏掉。

B-4 测试通过 `inspect.signature` 过滤参数绕过了此问题。

**修法**：`generate_module_code` 生成 `__init__` 签名时，只纳入在 `sub_nodes` 参数中实际有 `${var}` 引用的变量名，和 `params_schema` 做交集校验，不一致时抛出 `CodegenError` 提示哪个参数未使用。

**触发时机**：同 BL-codegen-01，两条一起修。

**预估成本**：1-2 小时（和上一条合并处理）