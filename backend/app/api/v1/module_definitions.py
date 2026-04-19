"""
模型模块定义 API 路由（新模块库）

提供基于 module_definitions 表的模块管理服务，
替代旧的 /ml-modules（基于 ml_module 表）。

路由前缀: /api/v1/models/modules
"""
import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.core.security import TokenData
from app.schemas.common import APIResponse
from app.schemas.module_definition import ModuleDefinitionListItem, ModuleDefinitionDetail
from app.models.module_definition import ModuleDefinition
from app.ml.modules.registry import sync_builtin_modules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models/modules", tags=["模型模块定义"])


# ==================== 辅助函数 ====================

def _build_list_item(module: ModuleDefinition) -> Dict[str, Any]:
    """构造列表项（轻量，不含 sub_nodes/sub_edges）"""
    schema = module.schema_json or {}
    is_composite = schema.get("is_composite", False)

    if is_composite:
        proxy_inputs = schema.get("proxy_inputs", [])
        proxy_outputs = schema.get("proxy_outputs", [])
    else:
        proxy_inputs = schema.get("input_ports", [])
        proxy_outputs = schema.get("output_ports", [])

    return {
        "id": module.id,
        "type": module.type,
        "display_name": module.display_name,
        "category": module.category,
        "is_composite": module.is_composite,
        "source": module.source,
        "version": module.version,
        "params_schema": schema.get("params_schema", []),
        "proxy_inputs": proxy_inputs,
        "proxy_outputs": proxy_outputs,
        "input_ports_dynamic": schema.get("input_ports_dynamic"),
    }


def _build_detail(module: ModuleDefinition) -> Dict[str, Any]:
    """构造详情（完整 schema_json，同时扁平化常用字段到顶层）"""
    schema = module.schema_json or {}
    is_composite = schema.get("is_composite", False)

    if is_composite:
        proxy_inputs = schema.get("proxy_inputs", [])
        proxy_outputs = schema.get("proxy_outputs", [])
    else:
        proxy_inputs = schema.get("input_ports", [])
        proxy_outputs = schema.get("output_ports", [])

    return {
        "id": module.id,
        "type": module.type,
        "display_name": module.display_name,
        "category": module.category,
        "is_composite": module.is_composite,
        "source": module.source,
        "version": module.version,
        "params_schema": schema.get("params_schema", []),
        "proxy_inputs": proxy_inputs,
        "proxy_outputs": proxy_outputs,
        "input_ports_dynamic": schema.get("input_ports_dynamic"),
        "schema_json": schema,
        "created_at": module.created_at.isoformat() if module.created_at else None,
        "updated_at": module.updated_at.isoformat() if module.updated_at else None,
    }


# ==================== 模块分类定义 ====================

MODULE_CATEGORIES = [
    {"key": "atomic", "label": "原子层", "icon": "Layers", "description": "PyTorch 原生层和原子算子"},
    {"key": "backbone", "label": "骨干网络", "icon": "Network", "description": "特征提取骨干网络模块"},
    {"key": "neck", "label": "颈部网络", "icon": "GitMerge", "description": "特征融合颈部网络模块"},
    {"key": "head", "label": "检测头", "icon": "Target", "description": "检测头模块"},
    {"key": "attention", "label": "注意力", "icon": "Eye", "description": "注意力机制模块"},
    {"key": "custom", "label": "自定义模块", "icon": "Puzzle", "description": "用户自定义模块"},
]


# ==================== API 路由 ====================

@router.get("", response_model=APIResponse[List[ModuleDefinitionListItem]])
async def list_modules(
    category: Optional[str] = Query(default=None, description="按分类筛选"),
    search: Optional[str] = Query(default=None, description="搜索关键词（匹配 type/display_name）"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[List[ModuleDefinitionListItem]]:
    """
    获取模块列表（轻量版）

    返回所有模块定义，含 is_composite、params_schema、proxy_inputs/outputs 概要，
    不含 sub_nodes/sub_edges（内部子图）。
    """
    stmt = select(ModuleDefinition)
    conditions = []

    if category:
        conditions.append(ModuleDefinition.category == category)

    if search:
        pattern = f"%{search}%"
        conditions.append(
            or_(
                ModuleDefinition.type.ilike(pattern),
                ModuleDefinition.display_name.ilike(pattern)
            )
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(ModuleDefinition.category, ModuleDefinition.type)
    result = await db.execute(stmt)
    modules = result.scalars().all()

    items = [_build_list_item(m) for m in modules]
    return APIResponse.success_response(data=items)


@router.get("/categories", response_model=APIResponse[List[Dict[str, str]]])
async def get_categories(
    current_user: TokenData = Depends(get_current_user)
) -> APIResponse[List[Dict[str, str]]]:
    """获取所有模块分类"""
    return APIResponse.success_response(data=MODULE_CATEGORIES)


@router.get("/{module_type}", response_model=APIResponse[ModuleDefinitionDetail])
async def get_module_detail(
    module_type: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[ModuleDefinitionDetail]:
    """
    获取单个模块详情（完整 schema）

    返回完整 schema_json，包含 sub_nodes、sub_edges、proxy_inputs/outputs 等内部子图信息。
    """
    result = await db.execute(
        select(ModuleDefinition).where(ModuleDefinition.type == module_type)
    )
    module = result.scalar_one_or_none()

    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模块 '{module_type}' 不存在"
        )

    return APIResponse.success_response(data=_build_detail(module))


@router.post("/sync", response_model=APIResponse)
async def trigger_sync(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse:
    """
    手动触发模块同步（管理员可用，普通用户也可在开发环境使用）

    扫描文件系统 schema 并全量同步到数据库。
    """
    await sync_builtin_modules(db)
    return APIResponse.success_response(message="模块同步已触发")
