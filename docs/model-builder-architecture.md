# 模型构建器架构文档

## 协作约定（Agent 必须遵守）

### 1. 完成标准：前端可见才算完成

> **任何后端改动如果没有配套的前端适配，都不算任务完成。**
>
> 任务完成的最低标准是用户能在浏览器前端看到预期效果。如果改动涉及前后端数据契约变更，前端适配是任务不可分割的一部分，不能"做完后端就停下来让用户自己捡尾巴"。

### 2. API 变更同步流程

当后端修改了 API 路由、响应格式或数据结构时，必须按以下 checklist 执行：

1. **更新后端路由** — 新路由实现 + 旧路由清理（返回 404 或删除文件）
2. **更新前端服务层** — `frontend/src/services/api.ts` 同步替换 URL 和类型
3. **更新前端类型定义** — `frontend/src/types/` 下对应类型清理旧字段、对齐新契约
4. **更新前端组件** — 所有引用旧类型 / 旧字段的组件同步适配
5. **启动前后端验证** — 确认浏览器中功能正常、旧数据已清理、新数据正确显示

### 3. 数据契约规范

#### 模块定义（ModuleDefinition）

| 层级 | 接口 | 返回内容 | 用途 |
|------|------|----------|------|
| 列表 | `GET /api/v1/models/modules` | `type, display_name, category, is_composite, params_schema, proxy_inputs, proxy_outputs` | 模块库侧边栏 |
| 详情 | `GET /api/v1/models/modules/{type}` | 完整 `schema_json`（含 `sub_nodes, sub_edges`） | 双击展开子图、参数面板 |

#### 参数 Schema（params_schema）

```ts
interface ParamSchema {
  name: string;        // 参数名（如 "inc"）
  type: string;        // "int" | "float" | "int[]" | "tuple" | "bool" | "string"
  default?: unknown;   // 默认值
  min?: number;        // 最小值（数值型）
  max?: number;        // 最大值（数值型）
  description?: string;// 参数描述
}
```

前端参数面板必须按 `params_schema` 数组渲染，不能假设字段名或固定字段。

#### 代理端口（proxy_inputs / proxy_outputs）

```ts
interface ProxyPort {
  sub_node_id: string;
  port_index: number;
  name: string;
}
```

复合模块折叠态的输入/输出端口数量 = `proxy_inputs.length` / `proxy_outputs.length`。

### 4. 模块同步机制

- **自动同步**：后端 startup 事件调用 `sync_builtin_modules()`，扫描 `atomic/*.json` + `composite/*/schema.json`，按 `type` upsert 到 `module_definitions` 表
- **手动同步**：`cd backend && python -m app.scripts.sync_modules`
- **幂等性**：重复执行不会重复插入，已消失的旧 builtin 模块会被自动清理
- **前端缓存**：模块库数据在页面刷新时重新加载，确保与后端文件系统一致

### 5. 目录结构

```
backend/app/ml/modules/
  atomic/           # 23 个原子模块 JSON
    conv2d.json
    ...
  composite/        # 14 个复合模块目录
    pmsfa/
      module.py
      schema.json
    focusfeature/
      module.py
      schema.json
    ...
    resblock/
      module.py
      schema.json
      schema_identity.json   # 测试专用（identity shortcut）
    resnetbottleneck/
      module.py
      schema.json
      schema_identity.json   # 测试专用
```

### 6. 测试标准

所有复合模块必须满足：
- `module.py`（手写参考实现）与 `schema.json`（动态构图）前向传播数值差 < 1e-4
- 表达式求值器（`${...}`）支持完整 AST 白名单
- 嵌套复合模块（如 CSP_PMSFA 内部引用 ResNetBottleneck）能正确递归实例化
