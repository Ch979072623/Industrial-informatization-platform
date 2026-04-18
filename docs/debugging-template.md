# 调试报告模板

## 适用场景

任何涉及前后端数据不一致、API 行为异常、渲染错误等复杂调试问题，都可以按此模板输出报告。

## 报告结构

### 1. 结论（TL;DR）

用一句话概括根因和修复方向。让 reader 在 5 秒内抓住重点。

### 2. 排查流程（按顺序）

| 步骤 | 动作 | 目的 |
|------|------|------|
| 1. 打印实际数据 | `console.log(JSON.stringify(data, null, 2))` / `curl` / 直接 DB 查询 | 拿到真实结构，不做假设 |
| 2. 对齐字段访问路径 | 对比前端读取路径和后端实际返回路径 | 定位"字段在哪一层"问题 |
| 3. 检查 schema 契约 | 看 Pydantic / OpenAPI / TypeScript 类型定义 | 定位 Pydantic 丢弃字段、类型不匹配 |
| 4. 验证修复 | 单元测试 / 集成测试 / 浏览器手动验证 | 确认前后端一致 |

### 3. 证据

- 后端实际返回的 JSON 键列表
- 前端尝试访问的字段路径
- TypeScript 编译错误或运行时错误栈
- 数据库原始记录

### 4. 方案权衡（至少 2 个）

| 方案 | 改动量 | 效果 | 风险 | 建议 |
|------|--------|------|------|------|
| A | 大/中/小 | 根治/缓解 | 高/中/低 | 推荐/备选 |
| B | ... | ... | ... | ... |
| C（不修） | 无 | ... | ... | 如果... |

### 5. 推荐方案 + 代码

给出明确的推荐和完整可运行的代码片段。

### 6. 并发/竞态注意事项

任何涉及"全局锁 + 异步"的场景，锁变量的释放时机都要推敲：
- 不要在异步操作本身的 `finally` 里立即清空锁
- 用 `queueMicrotask(() => { lock = null })` 推迟到下一个 microtask，保证当前 tick 里所有并发竞争者都已完成判断
- 或者用原子操作 / 信号量

### 7. 调试技巧（可复制）

记录本次用到的快速调试手段：
- 模拟 token 过期：`DevTools → Application → Local Storage → 改 token 值`
- 模拟后端数据：`ASGI transport + httpx.AsyncClient` 直接调用 FastAPI app
- 查看 Pydantic 丢弃字段：对比 `_build_*` 返回的字典和 `response_model` 的字段定义

---

## 范例：本轮 "detail.params_schema is not iterable" 定位报告

### 结论

后端 `_build_detail` 返回了 `params_schema` 到顶层，但 `ModuleDefinitionDetail` Pydantic 模型缺少该字段定义，导致 FastAPI 的 `response_model` 将其静默丢弃。前端 `detail.params_schema` 读到 `undefined`，`for...of undefined` throw。

### 排查流程

1. **打印实际数据**：ASGI transport 直接调用 `/models/modules/FocusFeature`，确认 `data.keys` 不含 `params_schema`
2. **对齐字段访问**：`_build_detail` 确实返回了 `params_schema`，但 API 响应里没有
3. **检查 schema 契约**：`ModuleDefinitionDetail` 只定义了 `schema_json`，没有 `params_schema` / `proxy_inputs` / `proxy_outputs`
4. **验证修复**：给 Pydantic model 添加字段后，API 响应恢复正常

### 方案权衡

| 方案 | 改动量 | 效果 | 建议 |
|------|--------|------|------|
| A. 后端统一 schema | 小 | 根治，列表和详情一致 | **推荐** |
| B. 前端兼容嵌套 | 小 | 改读 `detail.schema_json.params_schema` | 治标不治本 |
| C. 前端防御 | 极小 | `?? []` 避免 throw | 掩盖问题 |

### 并发注意事项

Axios 401 refresh 拦截器：全局 `refreshingPromise` + `queueMicrotask(() => { refreshingPromise = null })` 避免"判断时非空、进 if 前被清空"的竞态。

---

## 工程经验：前端 Console 显示 5xx 时如何鉴别真 bug vs 代理层包装

**场景**：浏览器 Console 出现 GET /api/v1/xxx 500 (Internal Server Error)，但不确定是后端代码真抛了 5xx，还是前端 dev server 代理层把网络错误包装成了 5xx。

**快速鉴别三步法**：

1. **curl 直接打后端 API（绕过代理层）**
   `ash
   curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/models/modules/FocusFeature
   `
   - 如果返回 200 + 正常 JSON → 后端代码没问题
   - 如果返回 500 + 有 traceback → 后端真 bug

2. **看后端 Uvicorn 控制台有无 traceback**
   - 真 500 会在控制台打印完整异常堆栈（TypeError / ValidationError / ...）
   - 代理层包装的错误不会在后端留下任何日志

3. **看前端 dev server 日志**
   - Vite：[vite] http proxy error: /api/v1/xxx + AggregateError [ECONNREFUSED]
   - Webpack：[webpack-dev-server] ... connection refused
   - 这说明后端进程断掉了，不是代码 bug

**判断矩阵**：

| curl 后端 | 后端 traceback | 前端 proxy error | 根因 |
|-----------|---------------|------------------|------|
| 200 | 无 | 有 ECONNREFUSED | **进程不稳定**（重启服务即可） |
| 500 | 有 | 无 | **后端代码 bug**（定位 traceback 修复） |
| 401 | 无 | 无 | **token 过期/无效**（触发 refresh 或重新登录） |

**本次案例**：
- 浏览器 Console：GET /models/modules/FocusFeature 500
- 后端 Uvicorn：无任何 traceback
- Vite 日志：AggregateError [ECONNREFUSED]
- curl 后端：200 + 完整 JSON
- **结论**：后端进程因后台任务超时被杀，Vite 代理连不上 → 包装成 500。重启后端后恢复正常。
