# extra_modules

本目录存放 Module 画布生成的 PyTorch 模块代码（.py 文件）。

**生成机制**：Phase 4b B-2 实现，本目录由 B-1 建立为空目录等待使用。

**导入约定**：生成的模块将被 ultralytics 通过 `from backend.app.ml.runtime.extra_modules.xxx import XXX` 或等价机制加载，详见 Phase 5 训练模块的对接文档。

**不上传 GitHub**：.py 文件由 gitignore 排除，仅本 README 作为占位保留。
