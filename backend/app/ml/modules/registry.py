"""
模块注册表

启动时扫描 backend/app/ml/modules/ 下所有 schema.json 和 atomic/*.json，
同步到 module_definitions 表。如果 DB 中无对应 type 的 builtin 记录则插入；
如果已存在且 schema 变化则更新（version 自增）。
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module_definition import ModuleDefinition

logger = logging.getLogger(__name__)

MODULES_DIR = Path(__file__).parent


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    """加载 JSON 文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载 {path} 失败: {e}")
        return None


def _discover_atomic_schemas() -> List[Dict[str, Any]]:
    """发现所有原子模块 schema"""
    schemas: List[Dict[str, Any]] = []
    atomic_dir = MODULES_DIR / "atomic"
    if not atomic_dir.exists():
        return schemas
    for json_file in sorted(atomic_dir.glob("*.json")):
        data = _load_json(json_file)
        if data:
            schemas.append(data)
    return schemas


def _discover_composite_schemas() -> List[Dict[str, Any]]:
    """发现所有复合模块 schema"""
    schemas: List[Dict[str, Any]] = []
    composite_dir = MODULES_DIR / "composite"
    if not composite_dir.exists():
        return schemas
    for module_dir in sorted(composite_dir.iterdir()):
        if module_dir.is_dir():
            schema_path = module_dir / "schema.json"
            if schema_path.exists():
                data = _load_json(schema_path)
                if data:
                    schemas.append(data)
    # 同时扫描 custom 目录
    custom_dir = MODULES_DIR / "custom"
    if custom_dir.exists():
        for module_dir in sorted(custom_dir.iterdir()):
            if module_dir.is_dir():
                schema_path = module_dir / "schema.json"
                if schema_path.exists():
                    data = _load_json(schema_path)
                    if data:
                        data["source"] = "custom"
                        schemas.append(data)
    return schemas


def _schema_changed(existing: ModuleDefinition, new_schema: Dict[str, Any]) -> bool:
    """比较现有 schema 与新 schema 是否发生变化"""
    # 简单比较：将两者序列化为 JSON 字符串后对比
    import json
    existing_json = json.dumps(existing.schema_json, sort_keys=True, ensure_ascii=False)
    new_json = json.dumps(new_schema, sort_keys=True, ensure_ascii=False)
    return existing_json != new_json


async def sync_builtin_modules(db: AsyncSession) -> None:
    """
    同步内置模块到数据库（幂等）

    扫描 atomic/ 和 composite/ 目录下的 schema，
    按 type 字段 upsert module_definitions 表中的 builtin 记录。
    若 DB 中存在但文件系统已消失的 builtin 模块，会被清理。
    """
    logger.info("开始同步内置模块定义...")

    all_schemas = _discover_atomic_schemas() + _discover_composite_schemas()
    scanned_types = {s.get("type") for s in all_schemas if s.get("type")}
    added = 0
    updated = 0
    skipped = 0
    removed = 0

    for schema in all_schemas:
        module_type = schema.get("type")
        if not module_type:
            logger.warning(f"schema 缺少 type 字段，跳过: {schema}")
            continue

        category = schema.get("category", "custom")
        is_composite = schema.get("is_composite", False)
        display_name = schema.get("display_name", module_type)
        source = schema.get("source", "builtin")

        result = await db.execute(
            select(ModuleDefinition).where(
                ModuleDefinition.type == module_type,
                ModuleDefinition.source == source
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            if _schema_changed(existing, schema):
                existing.schema_json = schema
                existing.category = category
                existing.is_composite = is_composite
                existing.display_name = display_name
                existing.version += 1
                logger.info(f"更新模块: {module_type} (version={existing.version})")
                updated += 1
            else:
                skipped += 1
        else:
            module_def = ModuleDefinition(
                type=module_type,
                category=category,
                is_composite=is_composite,
                display_name=display_name,
                schema_json=schema,
                source=source,
                version=1,
            )
            db.add(module_def)
            logger.info(f"新增模块: {module_type}")
            added += 1

    # 清理已消失的旧 builtin 模块（如 FDPN 等旧 seed）
    result = await db.execute(
        select(ModuleDefinition).where(
            ModuleDefinition.source == "builtin",
            ModuleDefinition.type.notin_(scanned_types)
        )
    )
    for stale in result.scalars().all():
        logger.info(f"删除旧模块: {stale.type}")
        await db.delete(stale)
        removed += 1

    await db.commit()
    logger.info(
        f"模块同步完成: 新增 {added} 个, 更新 {updated} 个, 跳过 {skipped} 个, 清理 {removed} 个"
    )


async def get_module_definition(
    db: AsyncSession, module_type: str
) -> Optional[ModuleDefinition]:
    """获取单个模块定义"""
    result = await db.execute(
        select(ModuleDefinition).where(ModuleDefinition.type == module_type)
    )
    return result.scalar_one_or_none()


async def list_module_definitions(
    db: AsyncSession,
    category: Optional[str] = None,
    is_composite: Optional[bool] = None,
) -> List[ModuleDefinition]:
    """获取模块定义列表"""
    stmt = select(ModuleDefinition)
    if category:
        stmt = stmt.where(ModuleDefinition.category == category)
    if is_composite is not None:
        stmt = stmt.where(ModuleDefinition.is_composite == is_composite)
    result = await db.execute(stmt)
    return list(result.scalars().all())
