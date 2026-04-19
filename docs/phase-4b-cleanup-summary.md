# Phase 4b 清扫阶段小结

## TL;DR

Phase 4b 正式开工前，先做了一轮 TypeScript 错误清扫，将 frontend 基线从 145 条 TS 错误降至 83 条（减少 62 条，43%）。耗时约 2 小时。剩余 83 条全部是需要产品/后端决策才能修复的类型契约问题，已挂 backlog，与 Phase 4b 施工路径零耦合。

## 为什么要在 Phase 4b 前做清扫

Phase 4b 开工前执行了只读调查 INV-01，发现 frontend 项目 `npx tsc --noEmit` 基线为 145 条错误、横跨 15 个文件。但**关键事实**：这 145 条错误全部在 Phase 1/2/3 的业务代码（数据集/数据增强/数据生成模块），**Phase 4a 的 model-builder 相关代码 0 条错误**。

这意味着两个选项：
- **选项 α**：带病推进 Phase 4b，但新代码可能被旧噪音淹没，且 Phase 4b 的 B/C/D/E 阶段要往 api.ts 加 4 组新接口，在有命名冲突的文件里继续堆会越滚越大。
- **选项 β**：开工前清扫一次，给 Phase 4b 一个干净的基线。

选择了**选项 β 的分段版本**：清最高性价比的部分（档 1 机械清扫 + api.ts 命名冲突），剩下的需要业务决策的部分挂 backlog。

## 分段决策

INV-01 把 145 条错误分为三档：

- **档 1（工具类小问题）**：46 条 unused imports/types，机械可修
- **档 2（类型推断歧义）**：82 条 type mismatch / missing property，需要理解业务
- **档 3（语法级/设计级错误）**：17 条 duplicate identifier / module resolution，可能触发连锁改动

分段策略：
- **立即修**：档 1 全部 + 档 3 中的 16 条 api.ts 命名冲突（共计 62 条）
- **挂 backlog**：档 2 全部 + 其他档 3（共计 83 条），按触发条件分发到未来 Phase

立即修部分的预期成本：2-3 小时。实际耗时约 2 小时，落在区间下缘。

## api.ts 命名冲突：为什么选 α 方案（前缀制）而不是 β（import alias）

INV-01 发现 api.ts 里 14 条 TS2300 duplicate identifier 源于 `augmentation.ts` 和 `generation.ts` 两个类型文件定义了 7 个同名接口（CreateTemplateRequest 等）。修复有两种方案：

- **方案 α**：在类型定义层加命名空间前缀（AugmentationCreateTemplateRequest / GenerationCreateTemplateRequest），类型文件本身重命名，所有使用点跟着改。彻底消除冲突。
- **方案 β**：仅在 api.ts 里用 `import type { X as AugmentationX }` 形式 alias，类型定义不动。改动最小但债转移。

CL-02a 只读扫描显示 α 方案扩散面仅 3 个文件（augmentation.ts + generation.ts + api.ts）、46 处使用点，**无任何业务组件被波及**。这让 α 的主要成本（扩散面大）几乎不存在。

选择 α 的理由：
- 扩散面实际很小（3 文件）
- 项目还有 7-8 个 Phase 要做，α 一劳永逸，β 会让每个新 Phase 都可能踩同样的坑
- α 的机械重命名是 Claude Code 的优势项目

命名约定确立：`<Module><Name>` 前缀制，驼峰形式。

## 阶段执行账本

| 阶段 | 目的 | 实际耗时 |
|---|---|---|
| PP-0 | 前端 vitest 基建（装 vitest + @testing-library/react + 2 条 smoke 测试）| ~20 分钟 |
| INV-01 | TS 错误只读清点（生成分类统计报告）| ~15 分钟 |
| CL-01 | 档 1 机械清扫（46 条 unused → 0）| ~45 分钟 |
| CL-02a | α 方案扩散面只读扫描 | ~10 分钟 |
| CL-02b | α 方案全量重命名（14 条 TS2300 → 0）| ~50 分钟 |
| **合计** | | **约 2 小时** |

## 关键经验沉淀

### 1. 阶段独立验证是重命名任务的生命线
CL-02b 执行时，阶段一完成后跑独立 tsc 验证，抓到首次漏改 `AugmentationState` 接口内的 5 处方法签名引用（tsc 报 TS2304 4 条）。如果没有阶段间验证闸门，这些漏改会和阶段二 api.ts 的改动混在一起，排查成本会显著上升。未来所有重命名/重构类提示词都应该延续"分段独立验证"模式。

### 2. TypeScript 和 ESLint 是独立的检查路径
CL-02b 计划中一度打算用 `// eslint-disable-next-line @typescript-eslint/no-unused-vars` 注释保留 `get` 参数名（zustand 惯例），但验证后发现该注释只影响 ESLint，不影响 TypeScript 编译器的 `noUnusedParameters` 检查。正确做法是使用下划线前缀（TS 官方豁免机制）。这是 TypeScript 项目里容易混淆的概念。

### 3. "顺手修"的诱惑必须硬约束
清扫类提示词最大的风险是 Claude Code 看到明显可以修的错误忍不住顺手修，污染改动范围。所有清扫提示词都写了"禁止顺手修非本轮范围错误"的硬约束，并用数字基线（"档 2 应保持 82 条"）验证是否越界。实际执行中档 2 / 档 3 数字零漂移，证明硬约束 + 数字基线是有效的防线。

### 4. 只读调查先行降低决策风险
INV-01（TS 错误清点）和 CL-02a（α 扩散面扫描）都是纯只读任务，总耗时约 25 分钟。这 25 分钟避免了两次可能的方向错误：
- 如果没有 INV-01，可能直接动手全清扫，实际需要 10-16 小时且大部分是业务决策问题。
- 如果没有 CL-02a，α 方案的扩散面评估只能靠猜，可能因过度担心而误选 β。

未来所有"不确定方向的技术债清理"都应先做只读调查。

## 未清扫部分的去向

剩余 83 条 TS 错误已分类挂入 `docs/backlog.md`：
- **Phase 5 前置任务**：领域模型命名规范（避免 Phase 5 再次触发 CL-02 类清扫）
- **P1**：ApiResponse 泛型契约统一（12 条 TS18046）
- **P2**：GenerationPage PlacementStrategy 类型对齐（37 条）、previewService 字段缺失（11 条）
- **P3**：GenerationCreateJobRequest dead export、zustand store 的 `_get` 命名

每条都标注了触发修复的时机，不会成为"永远挂着"的僵尸 backlog。

## 下一步

BL-01 是清扫阶段最后一条提示词。BL-01 完成后进入 Phase 4b 正式施工，第一条是 A-1（modelBuilderStore + 类型层扩展）。
