# Backlog

## P3 — 删除节点时 toast 显示 undefined

**现状**: 删除节点时 toast 显示 "已删除节点"，但如果 toast 想显示节点名，当前会读到 undefined。
**修法**: toast 调用放在 `setNodes` 之前（先读 `selectedNode.data.displayName` 再删），或在 store 里保留被删节点的副本用于通知。
**文件**: `frontend/src/components/model-builder/ModelCanvas.tsx`

## P2 — Axios 并发刷新 token 竞态

**现状**: response interceptor 没有全局 refresh promise。多个并发请求同时 401 时，每个请求都会独立触发刷新流程，可能产生多余的 refresh 请求。
**修法**: 用全局 `let refreshingPromise: Promise<void> | null = null` 让所有 401 请求等待同一个刷新完成。刷新完成后统一重试队列中的所有请求。
**文件**: `frontend/src/services/api.ts`
**影响**: 第四步展开复合节点时会频繁并发拉取详情 API，此问题会被放大。

## P3: 模型配置保存时自动归一化节点坐标

**现状**：
- React Flow 的 flow 坐标系原点可以不在视觉中心
- 用户操作后节点坐标可能出现大负数（如 x: -1566, y: -324）
- 当前靠 itView 在加载时兜底显示，但保存下来的 YAML/JSON 里坐标是脏的

**影响**：
- YAML diff 难以阅读（坐标偏移导致大量无意义变更）
- 外部协作时（导入到其他工具）坐标体系不统一

**建议修复时机**：Phase 4b（YAML 导入导出）
- 保存前遍历所有节点，找到最小 x/y，将所有节点平移使最小坐标为 (0,0)
- 或在加载后提供"归一化坐标"按钮

