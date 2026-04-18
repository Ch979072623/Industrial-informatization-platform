"""
模型构建器 API 路由

提供模型配置的管理功能，包括：
1. 保存模型配置
2. 获取配置列表
3. 获取配置详情
4. 更新配置
5. 删除配置
6. 生成代码快照
"""
import logging
from typing import Optional, List, Dict, Any

from fastapi import (
    APIRouter, Depends, HTTPException, status, Query
)
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.core.security import TokenData
from app.schemas.common import APIResponse, PaginatedResponse, PaginationParams
from app.schemas.ml_module import (
    ModelBuilderConfigResponse, ModelBuilderConfigListItem,
    ModelBuilderConfigCreate, ModelBuilderConfigUpdate, ModelBuilderConfigQuery,
    ModelArchitecture
)
from app.models.ml_module import ModelBuilderConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model-configs", tags=["模型构建器配置"])


# ==================== 辅助函数 ====================

def generate_code_snapshot(architecture: ModelArchitecture) -> str:
    """
    根据架构生成 PyTorch 代码快照
    
    这是一个简化的实现，生成基本的模块定义代码
    """
    code_lines = [
        "import torch",
        "import torch.nn as nn",
        "",
        "class CustomModel(nn.Module):",
        '    """自定义模型"""',
        "",
        "    def __init__(self, num_classes=10):",
        "        super().__init__()",
    ]
    
    # 为每个节点生成模块定义
    for node in architecture.nodes:
        node_id = node.id
        data = node.data
        module_name = data.get("moduleName", "Unknown")
        params = data.get("parameters", {})
        
        # 简化处理：直接生成模块赋值语句
        param_str = ", ".join([f"{k}={v}" for k, v in params.items()])
        code_lines.append(f"        self.{node_id} = {module_name}({param_str})")
    
    code_lines.extend([
        "",
        "    def forward(self, x):",
        "        # TODO: 根据连接关系实现前向传播",
        "        return x",
    ])
    
    return "\n".join(code_lines)


def build_config_response(config: ModelBuilderConfig) -> ModelBuilderConfigResponse:
    """构建配置响应"""
    return ModelBuilderConfigResponse.model_validate(config)


def build_config_list_item(config: ModelBuilderConfig) -> ModelBuilderConfigListItem:
    """构建配置列表项响应"""
    return ModelBuilderConfigListItem.model_validate(config)


# ==================== 配置管理 API ====================

@router.get("", response_model=APIResponse[PaginatedResponse[ModelBuilderConfigListItem]])
async def list_configs(
    query: ModelBuilderConfigQuery = Depends(),
    pagination: PaginationParams = Depends(),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[PaginatedResponse[ModelBuilderConfigListItem]]:
    """
    获取模型配置列表
    
    返回用户自己的配置和公开的配置
    """
    # 构建查询条件
    conditions = []
    
    # 用户可以看到：自己的配置 + 公开的配置
    access_conditions = [ModelBuilderConfig.created_by == current_user.user_id]
    if query.include_public:
        access_conditions.append(ModelBuilderConfig.is_public == True)
    
    # 管理员可以看到所有配置
    if current_user.role == "admin":
        conditions = []
    else:
        conditions.append(or_(*access_conditions))
    
    # 搜索关键词
    if query.search:
        search_pattern = f"%{query.search}%"
        conditions.append(
            or_(
                ModelBuilderConfig.name.ilike(search_pattern),
                ModelBuilderConfig.description.ilike(search_pattern)
            )
        )
    
    # 获取总数
    count_query = select(func.count()).select_from(ModelBuilderConfig)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # 获取分页数据
    stmt = select(ModelBuilderConfig)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(desc(ModelBuilderConfig.updated_at))
    stmt = stmt.offset(pagination.offset).limit(pagination.page_size)
    
    result = await db.execute(stmt)
    configs = result.scalars().all()
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=[build_config_list_item(c) for c in configs],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    )


@router.get("/{config_id}", response_model=APIResponse[ModelBuilderConfigResponse])
async def get_config(
    config_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[ModelBuilderConfigResponse]:
    """
    获取单个配置详情
    
    返回完整的模型架构配置
    """
    result = await db.execute(
        select(ModelBuilderConfig).where(ModelBuilderConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    # 检查访问权限
    if (config.created_by != current_user.user_id and 
        not config.is_public and 
        current_user.role != "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此配置"
        )
    
    return APIResponse.success_response(
        data=build_config_response(config)
    )


@router.post("", response_model=APIResponse[ModelBuilderConfigResponse])
async def create_config(
    request: ModelBuilderConfigCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[ModelBuilderConfigResponse]:
    """
    创建模型配置
    
    保存可视化构建器生成的模型架构
    """
    # 生成代码快照
    code_snapshot = generate_code_snapshot(request.architecture_json)
    
    # 提取输入形状和类别数量
    input_shape = request.input_shape
    num_classes = request.num_classes
    
    if not input_shape and request.architecture_json.metadata:
        input_shape = request.architecture_json.metadata.input_shape
    if not num_classes and request.architecture_json.metadata:
        num_classes = request.architecture_json.metadata.num_classes
    
    # 创建配置
    config = ModelBuilderConfig(
        name=request.name,
        description=request.description,
        architecture_json=request.architecture_json.model_dump(),
        code_snapshot=code_snapshot,
        input_shape=input_shape,
        num_classes=num_classes,
        base_model=request.base_model,
        created_by=current_user.user_id,
        is_public=request.is_public,
        version=1
    )
    
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    logger.info(f"用户 {current_user.user_id} 创建模型配置: {config.id}, name={request.name}")
    
    return APIResponse.success_response(
        data=build_config_response(config),
        message="模型配置保存成功"
    )


@router.put("/{config_id}", response_model=APIResponse[ModelBuilderConfigResponse])
async def update_config(
    config_id: str,
    request: ModelBuilderConfigUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[ModelBuilderConfigResponse]:
    """
    更新模型配置
    
    更新配置会创建新版本（version + 1）
    """
    result = await db.execute(
        select(ModelBuilderConfig).where(ModelBuilderConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    # 检查权限
    if config.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此配置"
        )
    
    # 更新字段
    if request.name is not None:
        config.name = request.name
    if request.description is not None:
        config.description = request.description
    if request.architecture_json is not None:
        config.architecture_json = request.architecture_json.model_dump()
        # 重新生成代码快照
        config.code_snapshot = generate_code_snapshot(request.architecture_json)
    if request.input_shape is not None:
        config.input_shape = request.input_shape
    if request.num_classes is not None:
        config.num_classes = request.num_classes
    if request.base_model is not None:
        config.base_model = request.base_model
    if request.is_public is not None:
        config.is_public = request.is_public
    if request.code_snapshot is not None:
        config.code_snapshot = request.code_snapshot
    
    # 版本号 + 1
    config.version += 1
    
    await db.commit()
    await db.refresh(config)
    
    logger.info(f"用户 {current_user.user_id} 更新模型配置: {config_id}, version={config.version}")
    
    return APIResponse.success_response(
        data=build_config_response(config),
        message="模型配置更新成功"
    )


@router.delete("/{config_id}", response_model=APIResponse)
async def delete_config(
    config_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse:
    """
    删除模型配置
    """
    result = await db.execute(
        select(ModelBuilderConfig).where(ModelBuilderConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    # 检查权限
    if config.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此配置"
        )
    
    await db.delete(config)
    await db.commit()
    
    logger.info(f"用户 {current_user.user_id} 删除模型配置: {config_id}")
    
    return APIResponse.success_response(message="模型配置删除成功")


@router.post("/{config_id}/clone", response_model=APIResponse[ModelBuilderConfigResponse])
async def clone_config(
    config_id: str,
    new_name: Optional[str] = Query(default=None, description="新配置名称"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[ModelBuilderConfigResponse]:
    """
    克隆模型配置
    
    基于现有配置创建副本
    """
    result = await db.execute(
        select(ModelBuilderConfig).where(ModelBuilderConfig.id == config_id)
    )
    source_config = result.scalar_one_or_none()
    
    if not source_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="源配置不存在"
        )
    
    # 检查访问权限
    if (source_config.created_by != current_user.user_id and 
        not source_config.is_public and 
        current_user.role != "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此配置"
        )
    
    # 创建副本
    name = new_name or f"{source_config.name} 副本"
    
    cloned_config = ModelBuilderConfig(
        name=name,
        description=source_config.description,
        architecture_json=source_config.architecture_json,
        code_snapshot=source_config.code_snapshot,
        input_shape=source_config.input_shape,
        num_classes=source_config.num_classes,
        base_model=source_config.base_model,
        created_by=current_user.user_id,
        is_public=False,  # 克隆的配置默认不公开
        version=1
    )
    
    db.add(cloned_config)
    await db.commit()
    await db.refresh(cloned_config)
    
    logger.info(f"用户 {current_user.user_id} 克隆模型配置: {config_id} -> {cloned_config.id}")
    
    return APIResponse.success_response(
        data=build_config_response(cloned_config),
        message="模型配置克隆成功"
    )


@router.get("/{config_id}/code", response_model=APIResponse[Dict[str, str]])
async def get_config_code(
    config_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[Dict[str, str]]:
    """
    获取配置生成的代码
    
    返回生成的 PyTorch 代码
    """
    result = await db.execute(
        select(ModelBuilderConfig).where(ModelBuilderConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="配置不存在"
        )
    
    # 检查访问权限
    if (config.created_by != current_user.user_id and 
        not config.is_public and 
        current_user.role != "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此配置"
        )
    
    return APIResponse.success_response(
        data={
            "code": config.code_snapshot or "# 暂无代码",
            "language": "python"
        }
    )
