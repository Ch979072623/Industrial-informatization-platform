"""
模型模块定义 API 路由（新模块库）

提供基于 module_definitions 表的模块管理服务，
替代旧的 /ml-modules（基于 ml_module 表）。

路由前缀: /api/v1/models/modules
"""
import logging
from typing import List, Dict, Any, Optional, Callable

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.core.security import TokenData
from app.schemas.common import APIResponse
from app.schemas.module_definition import ModuleDefinitionListItem, ModuleDefinitionDetail, ModuleDefinitionResponse
from app.schemas.ml_module import ModuleDefinitionCreate, ModelNode
from app.models.module_definition import ModuleDefinition
from app.ml.modules.registry import sync_builtin_modules
from app.ml.modules.canvas_converter import canvas_to_schema, CanvasConversionError

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


async def _build_module_resolver(
    db: AsyncSession,
    nodes: List[ModelNode],
) -> Callable[[str], Optional[Dict[str, Any]]]:
    """预查画布中所有子模块的 schema，返回同步解析器"""
    types = set()
    for n in nodes:
        if n.type not in ("input_port", "output_port"):
            mt = n.data.get("moduleType") or n.data.get("moduleName")
            if mt:
                types.add(mt)

    if not types:
        return lambda _mt: None

    result = await db.execute(
        select(ModuleDefinition).where(ModuleDefinition.type.in_(types))
    )
    schema_map = {m.type: m.schema_json for m in result.scalars().all()}

    def resolver(module_type: str) -> Optional[Dict[str, Any]]:
        return schema_map.get(module_type)

    return resolver


@router.post("", response_model=APIResponse[ModuleDefinitionResponse])
async def create_module(
    payload: ModuleDefinitionCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，仅管理员可注册模块",
        )
    """
    从 Module 画布注册新的 composite 模块到 module_definitions 表。

    冲突处理（Q2=δ）：
    - 若 type 已存在且 source='builtin' → 返回 409 Conflict，建议 type_v2 作为新名
    - 若 type 已存在且 source='custom' → 允许覆盖（前端应在 UI 加确认弹窗）
    """
    # 1. 冲突检测
    existing_result = await db.execute(
        select(ModuleDefinition).where(ModuleDefinition.type == payload.type)
    )
    existing_row = existing_result.scalar_one_or_none()

    if existing_row and existing_row.source == "builtin":
        suggested = f"{payload.type}_v2"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "conflict_with_builtin",
                "message": f"模块名 '{payload.type}' 已被内置模块占用",
                "suggested_name": suggested,
            },
        )

    # 2. 转换画布数据 → schema_json
    module_resolver = await _build_module_resolver(db, payload.nodes)
    try:
        schema_json = canvas_to_schema(
            nodes=[n.model_dump() for n in payload.nodes],
            edges=[e.model_dump() for e in payload.edges],
            module_resolver=module_resolver,
        )
        schema_json["type"] = payload.type
        schema_json["display_name"] = payload.display_name
        schema_json["category"] = payload.category
        schema_json["is_composite"] = True
        schema_json["input_ports_dynamic"] = False
        schema_json["params_schema"] = payload.params_schema or []
        if payload.description:
            schema_json["description"] = payload.description
    except CanvasConversionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # 3. 写入或覆盖
    if existing_row:  # source='custom' 情况
        existing_row.display_name = payload.display_name
        existing_row.category = payload.category
        existing_row.schema_json = schema_json
        existing_row.is_composite = True
        existing_row.version += 1
        await db.commit()
        await db.refresh(existing_row)
        resp = APIResponse.success_response(data=_build_detail(existing_row))
        return JSONResponse(status_code=200, content=resp.model_dump())
    else:
        new_module = ModuleDefinition(
            type=payload.type,
            display_name=payload.display_name,
            category=payload.category,
            schema_json=schema_json,
            source="custom",
            is_composite=True,
            created_by=current_user.user_id,
            version=1,
        )
        db.add(new_module)
        await db.commit()
        await db.refresh(new_module)
        resp = APIResponse.success_response(data=_build_detail(new_module))
        return JSONResponse(status_code=201, content=resp.model_dump())


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
