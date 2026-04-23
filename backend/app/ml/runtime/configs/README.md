# configs

本目录存放 Architecture 画布生成的 YAML 模型配置文件（yolo11 格式）。

**生成机制**：Phase 4b B-3 实现，本目录由 B-1 建立为空目录等待使用。

**训练对接**：生成的 yaml 由 ultralytics 的 `YOLO(path)` 加载，详见 Phase 5 训练模块的对接文档。

**不上传 GitHub**：.yaml 文件由 gitignore 排除，仅本 README 作为占位保留。
