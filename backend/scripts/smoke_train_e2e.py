"""End-to-end 1 epoch training smoke (P5-S3-T2 / backlog B.2)

验证 ModelBuilderConfig → architecture_to_yaml → YOLO(yaml).train(...)
完整生产链路在官方 pip ultralytics 下能跑通 1 epoch。

Usage:
    conda activate defect-detection
    cd backend
    python scripts/smoke_train_e2e.py [--config-id ID] [--dataset-name NAME]
                                       [--epochs 1] [--imgsz 160] [--batch 2]
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# 将 backend 加入 Python path（脚本在 backend/scripts/ 下运行）
_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))

# 1. patch 必须最早 —— 在任何 ultralytics 相关 import 之前
from app.ml.runtime.ultralytics_patch import apply_ultralytics_patches

apply_ultralytics_patches()

from app.db.session import AsyncSessionLocal
from app.ml.runtime.yaml_generator import YamlGeneratorError, architecture_to_yaml
from app.models.dataset import Dataset
from app.models.ml_module import ModelBuilderConfig
from app.models.module_definition import ModuleDefinition


def _build_db_resolver(db, module_types):
    """从 ModuleDefinition 表构建同步 resolver，对齐 model_builder.py 生产路径。"""
    module_map: Dict[str, Dict[str, Any]] = {}
    if module_types:
        for mod in db.query(ModuleDefinition).filter(ModuleDefinition.type.in_(list(module_types))).all():
            module_map[mod.type] = {
                "type": mod.type,
                "source": mod.source,
                "is_composite": mod.is_composite,
                "schema_json": mod.schema_json,
                "params_schema": mod.schema_json.get("params_schema") if isinstance(mod.schema_json, dict) else None,
            }

    def sync_resolver(module_type: str) -> Optional[Dict[str, Any]]:
        return module_map.get(module_type)

    return sync_resolver


async def _async_main(args) -> None:
    async with AsyncSessionLocal() as db:
        # ------------------------------------------------------------------
        # 读 config
        # ------------------------------------------------------------------
        from sqlalchemy import select
        stmt = select(ModelBuilderConfig).where(ModelBuilderConfig.id == args.config_id)
        result = await db.execute(stmt)
        config = result.scalar_one_or_none()
        if config is None:
            print(f"ERROR: ModelBuilderConfig '{args.config_id}' not found", file=sys.stderr)
            sys.exit(1)

        # ------------------------------------------------------------------
        # 读 dataset
        # ------------------------------------------------------------------
        stmt_ds = select(Dataset).where(Dataset.name == args.dataset_name)
        result_ds = await db.execute(stmt_ds)
        dataset = result_ds.scalar_one_or_none()
        if dataset is None:
            print(f"ERROR: Dataset '{args.dataset_name}' not found", file=sys.stderr)
            sys.exit(1)

        data_yaml_path = Path(dataset.path) / "data.yaml"
        if not data_yaml_path.exists():
            print(f"ERROR: data.yaml not found at {data_yaml_path}", file=sys.stderr)
            sys.exit(1)

        # ------------------------------------------------------------------
        # 解析 architecture_json
        # ------------------------------------------------------------------
        architecture_json = config.architecture_json
        if isinstance(architecture_json, str):
            architecture_json = json.loads(architecture_json)

        # 向后兼容：旧数据节点可能缺少 section/repeats（对齐 model_builder.py 生产路径）
        for node in architecture_json.get("nodes", []):
            data = node.get("data", {})
            if "section" not in data:
                data["section"] = "backbone"
            if "repeats" not in data:
                data["repeats"] = 1

        # ------------------------------------------------------------------
        # 构建 db resolver
        # ------------------------------------------------------------------
        module_types = set()
        for node in architecture_json.get("nodes", []):
            data = node.get("data", {})
            mt = data.get("moduleType") or data.get("moduleName") or node.get("type", "")
            if mt:
                module_types.add(mt)

        # 异步查询转同步 resolver
        module_map: Dict[str, Dict[str, Any]] = {}
        if module_types:
            stmt_mod = select(ModuleDefinition).where(ModuleDefinition.type.in_(list(module_types)))
            result_mod = await db.execute(stmt_mod)
            for mod in result_mod.scalars().all():
                module_map[mod.type] = {
                    "type": mod.type,
                    "source": mod.source,
                    "is_composite": mod.is_composite,
                    "schema_json": mod.schema_json,
                    "params_schema": mod.schema_json.get("params_schema") if isinstance(mod.schema_json, dict) else None,
                }

        def sync_resolver(module_type: str) -> Optional[Dict[str, Any]]:
            return module_map.get(module_type)

        # ------------------------------------------------------------------
        # 生成 YAML
        # ------------------------------------------------------------------
        yaml_str = architecture_to_yaml(architecture_json, resolver=sync_resolver)
        arch_path = Path("scripts/_smoke_arch.yaml")
        arch_path.write_text(yaml_str, encoding="utf-8")
        print(f"Generated YAML -> {arch_path}")
        print("--- YAML first 50 lines ---")
        for i, line in enumerate(yaml_str.splitlines()[:50], 1):
            print(f"{i:3d}| {line}")
        print("---")

        # ------------------------------------------------------------------
        # 训练
        # ------------------------------------------------------------------
        from ultralytics import YOLO

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project = "runs/smoke"
        name = timestamp

        model = YOLO(str(arch_path))
        model.train(
            data=str(data_yaml_path),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            project=project,
            name=name,
        )

        save_dir = Path(project) / name
        last_pt = save_dir / "weights" / "last.pt"
        if last_pt.exists():
            print(f"Checkpoint exists: {last_pt}")
        else:
            print(f"WARNING: checkpoint not found at {last_pt}")

        print("smoke PASS")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="E2E 1-epoch training smoke")
    parser.add_argument("--config-id", default="f942dcd3-997e-44cc-9ece-64ea53e16056", help="ModelBuilderConfig UUID")
    parser.add_argument("--dataset-name", default="neu-1_train70_val20_test10", help="Dataset name")
    parser.add_argument("--epochs", type=int, default=1, help="Training epochs")
    parser.add_argument("--imgsz", type=int, default=160, help="Image size")
    parser.add_argument("--batch", type=int, default=2, help="Batch size")
    args = parser.parse_args()

    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
