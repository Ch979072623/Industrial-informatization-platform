"""
数据增强 API 路由

提供数据增强配置、预览、执行和管理功能
"""
import os
import cv2
import hashlib
import logging
import base64
import numpy as np
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import (
    APIRouter, Depends, HTTPException, status,
    UploadFile, File, Form, Query, BackgroundTasks
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from celery.result import AsyncResult

from app.api.deps import get_db, get_current_user
from app.core.security import TokenData
from app.core.config import settings
from app.schemas.common import APIResponse, PaginatedResponse, PaginationParams
from app.schemas.augmentation import (
    AugmentationTemplateCreate, AugmentationTemplateUpdate,
    AugmentationTemplateResponse, AugmentationJobCreate,
    AugmentationJobUpdate, AugmentationJobResponse,
    AugmentationJobListQuery, AugmentationPreviewRequest,
    AugmentationPreviewResponse, CustomScriptUploadRequest,
    CustomScriptResponse, AvailableOperationsResponse,
    AugmentationOperationDefinition, JobControlRequest,
    JobControlResponse, JobProgressResponse
)
from app.models.augmentation import (
    AugmentationTemplate, AugmentationJob,
    CustomAugmentationScript, AugmentationPreview
)
from app.models.dataset import Dataset, DatasetImage

# 导入增强服务
from app.services.augmentation_service import (
    get_augmentation_service,
    AugmentationConfig,
    BBox
)
from app.tasks.augmentation_task import (
    augment_dataset_task,
    control_augmentation_job
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/augmentation", tags=["数据增强"])


# ==================== 工具函数 ====================

def check_admin_permission(current_user: TokenData) -> None:
    """检查管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )


def generate_config_hash(config: List[Dict[str, Any]]) -> str:
    """生成配置哈希"""
    config_str = str(sorted(str(config)))
    return hashlib.sha256(config_str.encode()).hexdigest()


# ==================== 操作定义 ====================

OPERATION_DEFINITIONS: List[AugmentationOperationDefinition] = [
    # 几何变换
    AugmentationOperationDefinition(
        operation_type="horizontal_flip",
        name="水平翻转",
        description="水平翻转图像和标注框",
        category="geometric",
        icon="FlipHorizontal",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="vertical_flip",
        name="垂直翻转",
        description="垂直翻转图像和标注框",
        category="geometric",
        icon="FlipVertical",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="random_rotate",
        name="随机旋转",
        description="随机旋转图像（-180°到+180°）",
        category="geometric",
        icon="RotateCw",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "angle_range", "type": "range", "default": [-180, 180], "min": -180, "max": 180, "step": 1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="random_crop",
        name="随机裁剪",
        description="随机裁剪图像区域",
        category="geometric",
        icon="Crop",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "crop_ratio", "type": "float", "default": 0.8, "min": 0.5, "max": 1.0, "step": 0.05}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="scale",
        name="缩放",
        description="随机缩放图像",
        category="geometric",
        icon="Maximize",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "scale_range", "type": "range", "default": [0.8, 1.2], "min": 0.5, "max": 2.0, "step": 0.1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="affine_transform",
        name="仿射变换",
        description="组合旋转、平移、缩放和剪切",
        category="geometric",
        icon="Move",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "angle", "type": "float", "default": 0, "min": -180, "max": 180, "step": 1},
            {"name": "translate_x", "type": "float", "default": 0, "min": -1, "max": 1, "step": 0.05},
            {"name": "translate_y", "type": "float", "default": 0, "min": -1, "max": 1, "step": 0.05},
            {"name": "scale", "type": "float", "default": 1.0, "min": 0.5, "max": 2.0, "step": 0.1},
            {"name": "shear", "type": "float", "default": 0, "min": -45, "max": 45, "step": 1}
        ],
        supports_bbox=True
    ),
    # 颜色变换
    AugmentationOperationDefinition(
        operation_type="brightness",
        name="亮度调整",
        description="调整图像亮度",
        category="color",
        icon="Sun",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "brightness_range", "type": "range", "default": [-30, 30], "min": -100, "max": 100, "step": 1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="contrast",
        name="对比度调整",
        description="调整图像对比度",
        category="color",
        icon="Contrast",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "contrast_range", "type": "range", "default": [0.8, 1.2], "min": 0.5, "max": 2.0, "step": 0.1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="saturation",
        name="饱和度调整",
        description="调整图像饱和度",
        category="color",
        icon="Palette",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "saturation_range", "type": "range", "default": [0.8, 1.2], "min": 0.5, "max": 2.0, "step": 0.1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="hue_jitter",
        name="色调抖动",
        description="随机调整图像色调",
        category="color",
        icon="Palette",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "hue_range", "type": "range", "default": [-10, 10], "min": -30, "max": 30, "step": 1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="histogram_equalization",
        name="直方图均衡化",
        description="增强图像对比度",
        category="color",
        icon="BarChart",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="clahe",
        name="CLAHE自适应均衡",
        description="自适应直方图均衡化",
        category="color",
        icon="BarChart2",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "clip_limit", "type": "float", "default": 2.0, "min": 1.0, "max": 10.0, "step": 0.5},
            {"name": "tile_grid_size", "type": "int", "default": 8, "min": 4, "max": 16, "step": 1}
        ],
        supports_bbox=True
    ),
    # 噪声与模糊
    AugmentationOperationDefinition(
        operation_type="gaussian_noise",
        name="高斯噪声",
        description="添加高斯噪声",
        category="noise_blur",
        icon="Zap",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "std_range", "type": "range", "default": [5, 15], "min": 0, "max": 50, "step": 1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="salt_pepper_noise",
        name="椒盐噪声",
        description="添加椒盐噪声",
        category="noise_blur",
        icon="ZapOff",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "noise_ratio", "type": "float", "default": 0.01, "min": 0, "max": 0.1, "step": 0.01}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="gaussian_blur",
        name="高斯模糊",
        description="应用高斯模糊",
        category="noise_blur",
        icon="Blur",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "kernel_size", "type": "int", "default": 5, "min": 3, "max": 15, "step": 2},
            {"name": "sigma", "type": "float", "default": 1.0, "min": 0.1, "max": 5.0, "step": 0.1}
        ],
        supports_bbox=True
    ),
    AugmentationOperationDefinition(
        operation_type="motion_blur",
        name="运动模糊",
        description="模拟运动模糊效果",
        category="noise_blur",
        icon="Wind",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "kernel_size", "type": "int", "default": 5, "min": 3, "max": 15, "step": 2},
            {"name": "angle", "type": "float", "default": 0, "min": 0, "max": 360, "step": 1}
        ],
        supports_bbox=True
    ),
    # 高级增强
    AugmentationOperationDefinition(
        operation_type="cutout",
        name="CutOut擦除",
        description="随机擦除图像区域",
        category="advanced",
        icon="Square",
        parameters=[
            {"name": "probability", "type": "probability", "default": 1.0, "min": 0, "max": 1},
            {"name": "erase_ratio", "type": "float", "default": 0.2, "min": 0.1, "max": 0.5, "step": 0.05},
            {"name": "max_erase_count", "type": "int", "default": 1, "min": 1, "max": 5, "step": 1}
        ],
        supports_bbox=True
    ),
]


# ==================== API 路由 ====================

@router.get("/operations", response_model=APIResponse[AvailableOperationsResponse])
async def get_available_operations(
    current_user: TokenData = Depends(get_current_user)
) -> APIResponse[AvailableOperationsResponse]:
    """
    获取可用的增强操作列表
    
    返回所有预定义的增强操作及其参数定义
    """
    categories = [
        {"key": "geometric", "name": "几何变换", "icon": "Move"},
        {"key": "color", "name": "颜色变换", "icon": "Palette"},
        {"key": "noise_blur", "name": "噪声与模糊", "icon": "Zap"},
        {"key": "advanced", "name": "高级增强", "icon": "Sparkles"},
        {"key": "custom", "name": "自定义", "icon": "Code"},
    ]
    
    return APIResponse.success_response(
        data=AvailableOperationsResponse(
            operations=OPERATION_DEFINITIONS,
            categories=categories
        )
    )


# ==================== 模板管理 ====================

@router.get("/templates", response_model=APIResponse[PaginatedResponse[AugmentationTemplateResponse]])
async def list_templates(
    pagination: PaginationParams = Depends(),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[PaginatedResponse[AugmentationTemplateResponse]]:
    """
    获取增强模板列表
    
    返回用户保存的模板和系统预设模板
    """
    # 查询条件：用户自己的模板或系统预设
    conditions = [
        (AugmentationTemplate.created_by == current_user.user_id) | 
        (AugmentationTemplate.is_preset == True)
    ]
    
    # 获取总数
    count_query = select(func.count()).select_from(AugmentationTemplate).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # 获取分页数据
    result = await db.execute(
        select(AugmentationTemplate)
        .where(and_(*conditions))
        .order_by(desc(AugmentationTemplate.created_at))
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    templates = result.scalars().all()
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=[AugmentationTemplateResponse.model_validate(t) for t in templates],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    )


@router.post("/templates", response_model=APIResponse[AugmentationTemplateResponse])
async def create_template(
    request: AugmentationTemplateCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[AugmentationTemplateResponse]:
    """
    创建增强模板
    
    保存当前的增强流水线配置为模板
    """
    # 验证配置
    is_valid, error_msg = AugmentationConfig.validate_pipeline_config(request.pipeline_config)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"配置验证失败: {error_msg}"
        )
    
    # 创建模板
    template = AugmentationTemplate(
        name=request.name,
        description=request.description,
        pipeline_config=request.pipeline_config,
        is_preset=False,
        created_by=current_user.user_id
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    logger.info(f"用户 {current_user.user_id} 创建增强模板: {template.id}, name={request.name}")
    
    return APIResponse.success_response(
        data=AugmentationTemplateResponse.model_validate(template),
        message="模板创建成功"
    )


@router.put("/templates/{template_id}", response_model=APIResponse[AugmentationTemplateResponse])
async def update_template(
    template_id: str,
    request: AugmentationTemplateUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[AugmentationTemplateResponse]:
    """更新增强模板"""
    result = await db.execute(
        select(AugmentationTemplate).where(AugmentationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 检查权限
    if template.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改此模板"
        )
    
    # 更新字段
    if request.name is not None:
        template.name = request.name
    if request.description is not None:
        template.description = request.description
    if request.pipeline_config is not None:
        is_valid, error_msg = AugmentationConfig.validate_pipeline_config(request.pipeline_config)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"配置验证失败: {error_msg}"
            )
        template.pipeline_config = request.pipeline_config
    
    await db.commit()
    await db.refresh(template)
    
    return APIResponse.success_response(
        data=AugmentationTemplateResponse.model_validate(template),
        message="模板更新成功"
    )


@router.delete("/templates/{template_id}", response_model=APIResponse)
async def delete_template(
    template_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse:
    """删除增强模板"""
    result = await db.execute(
        select(AugmentationTemplate).where(AugmentationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 检查权限
    if template.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此模板"
        )
    
    # 不能删除系统预设
    if template.is_preset:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能删除系统预设模板"
        )
    
    await db.delete(template)
    await db.commit()
    
    logger.info(f"用户 {current_user.user_id} 删除增强模板: {template_id}")
    
    return APIResponse.success_response(message="模板删除成功")


# ==================== 增强任务 ====================

@router.get("/jobs", response_model=APIResponse[PaginatedResponse[AugmentationJobResponse]])
async def list_jobs(
    query: AugmentationJobListQuery = Depends(),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[PaginatedResponse[AugmentationJobResponse]]:
    """
    获取增强任务列表
    
    支持按状态和数据集筛选
    """
    conditions = [AugmentationJob.created_by == current_user.user_id]
    
    if query.status:
        conditions.append(AugmentationJob.status == query.status)
    if query.source_dataset_id:
        conditions.append(AugmentationJob.source_dataset_id == query.source_dataset_id)
    
    # 获取总数
    from sqlalchemy import func
    count_query = select(func.count()).select_from(AugmentationJob).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # 获取分页数据
    result = await db.execute(
        select(AugmentationJob)
        .where(and_(*conditions))
        .order_by(desc(AugmentationJob.created_at))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    jobs = result.scalars().all()
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=[AugmentationJobResponse.model_validate(j) for j in jobs],
            total=total,
            page=query.page,
            page_size=query.page_size
        )
    )


@router.post("/jobs", response_model=APIResponse[AugmentationJobResponse])
async def create_job(
    request: AugmentationJobCreate,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[AugmentationJobResponse]:
    """
    创建增强任务
    
    提交数据增强任务到 Celery 执行
    """
    # 验证配置
    is_valid, error_msg = AugmentationConfig.validate_pipeline_config(request.pipeline_config)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"配置验证失败: {error_msg}"
        )
    
    # 检查源数据集
    result = await db.execute(
        select(Dataset).where(Dataset.id == request.source_dataset_id)
    )
    source_dataset = result.scalar_one_or_none()
    
    if not source_dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="源数据集不存在"
        )
    
    # 检查数据集访问权限
    if source_dataset.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此数据集"
        )
    
    # 创建任务记录
    job = AugmentationJob(
        name=request.name,
        source_dataset_id=request.source_dataset_id,
        pipeline_config=request.pipeline_config,
        augmentation_factor=request.augmentation_factor,
        status="pending",
        progress=0.0,
        processed_count=0,
        total_count=0,
        generated_count=0,
        created_by=current_user.user_id
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # 启动 Celery 任务
    try:
        # 使用前端传递的新数据集名称，或生成默认名称
        output_name = request.new_dataset_name or f"{source_dataset.name}_augmented"
        
        celery_task = augment_dataset_task.delay(
            job_id=job.id,
            dataset_id=request.source_dataset_id,
            pipeline_config=request.pipeline_config,
            augmentation_factor=request.augmentation_factor,
            output_dataset_name=output_name,
            class_names=source_dataset.class_names,
            target_split=request.target_split,
            include_original=request.include_original
        )
        
        # 更新 Celery 任务ID
        job.celery_task_id = celery_task.id
        await db.commit()
        
        logger.info(f"用户 {current_user.user_id} 创建增强任务: {job.id}, celery_task={celery_task.id}")
        
        return APIResponse.success_response(
            data=AugmentationJobResponse.model_validate(job),
            message="增强任务已提交"
        )
        
    except Exception as e:
        # 任务启动失败，更新状态
        job.status = "failed"
        job.error_message = f"启动 Celery 任务失败: {str(e)}"
        await db.commit()
        
        logger.error(f"启动 Celery 任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动增强任务失败: {str(e)}"
        )


@router.get("/jobs/{job_id}", response_model=APIResponse[AugmentationJobResponse])
async def get_job(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[AugmentationJobResponse]:
    """获取增强任务详情"""
    result = await db.execute(
        select(AugmentationJob).where(AugmentationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查权限
    if job.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    return APIResponse.success_response(
        data=AugmentationJobResponse.model_validate(job)
    )


@router.post("/jobs/{job_id}/control", response_model=APIResponse[JobControlResponse])
async def control_job(
    job_id: str,
    request: JobControlRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[JobControlResponse]:
    """
    控制增强任务
    
    支持 pause（暂停）、resume（恢复）、cancel（取消）
    """
    result = await db.execute(
        select(AugmentationJob).where(AugmentationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查权限
    if job.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权控制此任务"
        )
    
    # 发送控制命令
    control_result = control_augmentation_job.delay(job_id, request.action)
    result_data = control_result.get(timeout=5)
    
    if result_data.get("success"):
        # 更新数据库状态
        if request.action == "pause":
            job.status = "paused"
        elif request.action == "resume":
            job.status = "running"
        elif request.action == "cancel":
            job.status = "cancelled"
        await db.commit()
    
    return APIResponse.success_response(
        data=JobControlResponse(
            success=result_data.get("success", False),
            new_status=job.status,
            message=result_data.get("message", "")
        )
    )


@router.get("/jobs/{job_id}/progress", response_model=APIResponse[JobProgressResponse])
async def get_job_progress(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[JobProgressResponse]:
    """获取任务进度"""
    result = await db.execute(
        select(AugmentationJob).where(AugmentationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 检查权限
    if job.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    # 从 Celery 获取最新状态
    if job.celery_task_id:
        celery_result = AsyncResult(job.celery_task_id)
        if celery_result.state == 'PROGRESS':
            meta = celery_result.info or {}
            job.progress = meta.get('percent', job.progress)
            job.generated_count = meta.get('generated', job.generated_count)
    
    # 计算预计剩余时间（基于生成速度）
    estimated_remaining = None
    if job.status == "running" and job.timing_stats:
        images_per_second = job.timing_stats.get('images_per_second', 0)
        remaining_images = job.total_count - job.generated_count
        if images_per_second > 0:
            estimated_remaining = int(remaining_images / images_per_second)
    
    return APIResponse.success_response(
        data=JobProgressResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            processed_count=job.processed_count,
            total_count=job.total_count,
            generated_count=job.generated_count,
            current_operation=None,  # TODO: 从执行日志获取
            estimated_time_remaining=estimated_remaining
        )
    )


# ==================== 预览功能 ====================

@router.post("/preview", response_model=APIResponse[AugmentationPreviewResponse])
async def create_preview(
    request: AugmentationPreviewRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[AugmentationPreviewResponse]:
    """
    创建增强预览
    
    对指定图像应用增强流水线并返回预览结果
    支持数据集内图片或上传的图片（base64编码）
    """
    logger.info(f"create_preview called with dataset_id={request.source_dataset_id}, image_id={request.image_id}")
    import asyncio
    import base64
    from concurrent.futures import ThreadPoolExecutor
    from io import BytesIO
    from PIL import Image as PILImage
    
    # 检查源数据集
    result = await db.execute(
        select(Dataset).where(Dataset.id == request.source_dataset_id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 判断是否使用上传的图片
    use_uploaded_image = request.uploaded_image and request.uploaded_image.startswith('data:image')
    
    if use_uploaded_image:
        # 处理上传的图片
        try:
            # 解析 base64 图片
            header, encoded = request.uploaded_image.split(',', 1)
            image_data = base64.b64decode(encoded)
            
            # 使用 OpenCV 读取
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                raise ValueError("无法解码上传的图片")
            
            height, width = image.shape[:2]
            
            # 对于上传的图片，没有标注框
            original_bboxes = []
            bboxes = []
            
            # 异步执行增强
            async def _process_uploaded_image():
                try:
                    service = get_augmentation_service()
                    result = service.augment_image(image, [], request.pipeline_config)
                    
                    if not result.success:
                        raise ValueError(f"增强失败: {result.error_message}")
                    
                    # 保存预览图像
                    preview_dir = Path(settings.upload_dir) / "augmentation_previews"
                    preview_dir.mkdir(parents=True, exist_ok=True)
                    
                    preview_filename = f"uploaded_{current_user.user_id}_{int(datetime.now().timestamp())}.jpg"
                    preview_path = preview_dir / preview_filename
                    
                    cv2.imwrite(str(preview_path), result.image)
                    
                    return {
                        "success": True,
                        "preview_path": str(preview_path),
                        "original_bboxes": [],
                        "augmented_bboxes": [],
                        "applied_operations": result.applied_operations,
                        "width": width,
                        "height": height,
                    }
                except Exception as e:
                    logger.error(f"处理上传图片失败: {e}")
                    return {"success": False, "error": str(e)}
            
            result = await asyncio.wait_for(_process_uploaded_image(), timeout=10.0)
            
            if not result.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"预览生成失败: {result.get('error', '未知错误')}"
                )
            
            # 构建响应
            from app.schemas.augmentation import PreviewImageInfo, PreviewBBoxInfo
            
            return APIResponse.success_response(
                data=AugmentationPreviewResponse(
                    original=PreviewImageInfo(
                        url=request.uploaded_image,  # 返回原图 base64
                        width=result["width"],
                        height=result["height"],
                        bbox_count=0,
                        bboxes=[]
                    ),
                    augmented=PreviewImageInfo(
                        url=f"/api/v1/augmentation/preview/file/{Path(result['preview_path']).name}",
                        width=result["width"],
                        height=result["height"],
                        bbox_count=0,
                        bboxes=[]
                    ),
                    applied_operations=result.get("applied_operations", []),
                    processing_time_ms=0
                )
            )
            
        except Exception as e:
            logger.error(f"处理上传图片失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"处理上传图片失败: {str(e)}"
            )
    
    # 原有的数据集图片处理逻辑
    # 获取图像 - 支持通过 name_id 或 id 查询
    if request.image_id:
        # 先尝试通过 name_id 查询（前端通常使用 name_id）
        result = await db.execute(
            select(DatasetImage).where(
                and_(
                    DatasetImage.name_id == request.image_id,
                    DatasetImage.dataset_id == request.source_dataset_id
                )
            )
        )
        image_record = result.scalar_one_or_none()
        
        # 如果找不到，尝试通过 id 查询
        if not image_record:
            result = await db.execute(
                select(DatasetImage).where(
                    and_(
                        DatasetImage.id == request.image_id,
                        DatasetImage.dataset_id == request.source_dataset_id
                    )
                )
            )
            image_record = result.scalar_one_or_none()
    else:
        # 随机获取一张图像
        result = await db.execute(
            select(DatasetImage)
            .where(DatasetImage.dataset_id == request.source_dataset_id)
            .limit(1)
        )
        image_record = result.scalar_one_or_none()
    
    if not image_record:
        logger.error(f"Image not found: dataset_id={request.source_dataset_id}, image_id={request.image_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"找不到图像: dataset_id={request.source_dataset_id}, image_id={request.image_id}"
        )
    
    # 检查缓存
    config_hash = generate_config_hash(request.pipeline_config)
    result = await db.execute(
        select(AugmentationPreview).where(
            and_(
                AugmentationPreview.source_image_id == image_record.id,
                AugmentationPreview.config_hash == config_hash,
                AugmentationPreview.expires_at > datetime.now(timezone.utc).isoformat()
            )
        )
    )
    cached_preview = result.scalar_one_or_none()
    
    if cached_preview:
        # 从缓存构建响应
        original_bboxes = cached_preview.preview_annotations.get('original_bboxes', [])
        augmented_bboxes = cached_preview.preview_annotations.get('augmented_bboxes', [])
        
        return APIResponse.success_response(
            data=AugmentationPreviewResponse(
                original=PreviewImageInfo(
                    url=f"/api/v1/augmentation/preview/original/{request.source_dataset_id}/{image_record.name_id}",
                    width=image_record.width or 0,
                    height=image_record.height or 0,
                    bbox_count=len(original_bboxes),
                    bboxes=[
                        PreviewBBoxInfo(
                            id=f"orig_bbox_{i}",
                            x1=b['x1'],
                            y1=b['y1'],
                            x2=b['x2'],
                            y2=b['y2'],
                            class_id=b['class_id'],
                            class_name=dataset.class_names[b['class_id']] if b['class_id'] < len(dataset.class_names) else None
                        )
                        for i, b in enumerate(original_bboxes)
                    ]
                ),
                augmented=PreviewImageInfo(
                    url=f"/api/v1/augmentation/preview/{cached_preview.id}/image",
                    width=image_record.width or 0,
                    height=image_record.height or 0,
                    bbox_count=len(augmented_bboxes),
                    bboxes=[
                        PreviewBBoxInfo(
                            id=f"aug_bbox_{i}",
                            x1=b['x1'],
                            y1=b['y1'],
                            x2=b['x2'],
                            y2=b['y2'],
                            class_id=b['class_id'],
                            class_name=dataset.class_names[b['class_id']] if b['class_id'] < len(dataset.class_names) else None
                        )
                        for i, b in enumerate(augmented_bboxes)
                    ]
                ),
                applied_operations=cached_preview.preview_annotations.get('applied_operations', []),
                processing_time_ms=0
            )
        )
    
    # 异步执行增强（带超时）
    async def _generate_preview():
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(pool, _do_augment, image_record, request.pipeline_config, dataset)
    
    def _do_augment(image_record, pipeline_config, dataset):
        """在同步上下文中执行增强"""
        try:
            # 读取图像 - 尝试多种路径组合
            image_path = image_record.filepath
            possible_paths = [
                image_path,  # 原路径
                os.path.join(dataset.path, image_path),  # 相对 dataset.path
                os.path.join(os.getcwd(), image_path),  # 相对工作目录
                os.path.join(os.getcwd(), 'backend', image_path),  # 相对 backend 目录
            ]
            
            # 去重并过滤存在的路径
            possible_paths = list(dict.fromkeys(possible_paths))
            
            image = None
            actual_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    actual_path = path
                    image = cv2.imread(path)
                    if image is not None:
                        break
            
            if image is None:
                logger.error(f"尝试的所有路径均无法读取图像: {possible_paths}")
                raise ValueError(f"无法读取图像，尝试的路径: {possible_paths}")
            
            logger.info(f"成功读取图像: {actual_path}")
            
            # 读取标注 - 同样尝试多种路径
            bboxes = []
            if image_record.annotation_path:
                label_path = image_record.annotation_path
                label_possible_paths = [
                    label_path,
                    os.path.join(dataset.path, label_path),
                    os.path.join(os.getcwd(), label_path),
                    os.path.join(os.getcwd(), 'backend', label_path),
                    # 尝试在图片所在目录的 labels 子目录
                    os.path.join(os.path.dirname(actual_path), '..', 'labels', os.path.basename(label_path)),
                ]
                
                label_possible_paths = list(dict.fromkeys(label_possible_paths))
                
                for path in label_possible_paths:
                    if os.path.exists(path):
                        bboxes = _load_yolo_labels_for_preview(path)
                        logger.info(f"成功读取标注: {path}, 标注数: {len(bboxes)}")
                        break
            
            # 记录原图标注框
            original_bboxes = [{
                "x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2,
                "class_id": b.class_id
            } for b in bboxes]
            
            # 执行增强
            service = get_augmentation_service()
            result = service.augment_image(image, bboxes, pipeline_config)
            
            if not result.success:
                raise ValueError(f"增强失败: {result.error_message}")
            
            # 保存预览图像
            preview_dir = Path(settings.upload_dir) / "augmentation_previews"
            preview_dir.mkdir(parents=True, exist_ok=True)
            
            preview_filename = f"{image_record.id}_{config_hash[:16]}.jpg"
            preview_path = preview_dir / preview_filename
            
            cv2.imwrite(str(preview_path), result.image)
            
            return {
                "success": True,
                "preview_path": str(preview_path),
                "original_bboxes": original_bboxes,
                "augmented_bboxes": [{
                    "x1": b.x1, "y1": b.y1, "x2": b.x2, "y2": b.y2,
                    "class_id": b.class_id
                } for b in result.bboxes],
                "applied_operations": result.applied_operations
            }
            
        except Exception as e:
            logger.error(f"生成预览失败: {e}")
            return {"success": False, "error": str(e)}
    
    # 执行增强，设置超时
    try:
        result = await asyncio.wait_for(_generate_preview(), timeout=10.0)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="预览生成超时，请简化增强流水线或减少操作数量"
        )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"预览生成失败: {result.get('error', '未知错误')}"
        )
    
    # 保存缓存记录
    preview_record = AugmentationPreview(
        source_image_id=image_record.id,
        config_hash=config_hash,
        preview_image_path=result["preview_path"],
        preview_annotations={
            "original_bboxes": result.get("original_bboxes", []),
            "augmented_bboxes": result.get("augmented_bboxes", []),
            "applied_operations": result.get("applied_operations", [])
        },
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        created_by=current_user.user_id
    )
    
    db.add(preview_record)
    await db.commit()
    await db.refresh(preview_record)
    
    # 构建响应
    from app.schemas.augmentation import PreviewImageInfo, PreviewBBoxInfo
    
    return APIResponse.success_response(
        data=AugmentationPreviewResponse(
            original=PreviewImageInfo(
                url=f"/api/v1/augmentation/preview/original/{request.source_dataset_id}/{image_record.name_id}",
                width=image_record.width or 0,
                height=image_record.height or 0,
                bbox_count=len(result.get("original_bboxes", [])),
                bboxes=[
                    PreviewBBoxInfo(
                        id=f"orig_bbox_{i}",
                        x1=b['x1'],
                        y1=b['y1'],
                        x2=b['x2'],
                        y2=b['y2'],
                        class_id=b['class_id'],
                        class_name=dataset.class_names[b['class_id']] if b['class_id'] < len(dataset.class_names) else None
                    )
                    for i, b in enumerate(result.get("original_bboxes", []))
                ]
            ),
            augmented=PreviewImageInfo(
                url=f"/api/v1/augmentation/preview/{preview_record.id}/image",
                width=image_record.width or 0,
                height=image_record.height or 0,
                bbox_count=len(result.get("augmented_bboxes", [])),
                bboxes=[
                    PreviewBBoxInfo(
                        id=f"aug_bbox_{i}",
                        x1=b['x1'],
                        y1=b['y1'],
                        x2=b['x2'],
                        y2=b['y2'],
                        class_id=b['class_id'],
                        class_name=dataset.class_names[b['class_id']] if b['class_id'] < len(dataset.class_names) else None
                    )
                    for i, b in enumerate(result.get("augmented_bboxes", []))
                ]
            ),
            applied_operations=result.get("applied_operations", []),
            processing_time_ms=0
        )
    )


def _load_yolo_labels_for_preview(label_path: str) -> List[BBox]:
    """加载YOLO标注用于预览"""
    bboxes = []
    try:
        with open(label_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    class_id = int(parts[0])
                    x_center = float(parts[1])
                    y_center = float(parts[2])
                    width = float(parts[3])
                    height = float(parts[4])
                    
                    x1 = x_center - width / 2
                    y1 = y_center - height / 2
                    x2 = x_center + width / 2
                    y2 = y_center + height / 2
                    
                    bboxes.append(BBox(
                        x1=max(0, x1),
                        y1=max(0, y1),
                        x2=min(1, x2),
                        y2=min(1, y2),
                        class_id=class_id
                    ))
    except Exception as e:
        logger.warning(f"加载标注失败: {e}")
    return bboxes


@router.get("/preview/{preview_id}/image")
async def get_preview_image(
    preview_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取预览图像文件
    
    注意：此接口不需要认证，因为预览图片 URL 包含随机哈希（config_hash）
    作为安全措施，且24小时后会自动过期删除
    """
    result = await db.execute(
        select(AugmentationPreview).where(AugmentationPreview.id == preview_id)
    )
    preview = result.scalar_one_or_none()
    
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="预览不存在"
        )
    
    # 检查是否过期
    try:
        from datetime import datetime
        expires_at = datetime.fromisoformat(preview.expires_at)
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="预览已过期，请重新生成"
            )
    except (ValueError, TypeError):
        pass  # 如果解析失败，继续返回图片
    
    if not os.path.exists(preview.preview_image_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="预览图像文件不存在"
        )
    
    return FileResponse(preview.preview_image_path, media_type="image/jpeg")


@router.get("/preview/original/{dataset_id}/{image_id}")
async def get_original_image(
    dataset_id: str,
    image_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取原图（用于预览对比）
    
    注意：此接口不需要认证，因为预览 URL 包含随机哈希
    作为安全措施，且24小时后会自动过期
    """
    # 获取图像记录
    result = await db.execute(
        select(DatasetImage).where(
            and_(
                DatasetImage.name_id == image_id,
                DatasetImage.dataset_id == dataset_id
            )
        )
    )
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图像不存在"
        )
    
    # 获取数据集
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id)
    )
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 构建图像路径
    image_path = image.filepath
    possible_paths = [
        image_path,
        os.path.join(dataset.path, image_path),
        os.path.join(os.getcwd(), image_path),
        os.path.join(os.getcwd(), 'backend', image_path),
    ]
    
    # 去重并查找存在的路径
    possible_paths = list(dict.fromkeys(possible_paths))
    
    actual_path = None
    for path in possible_paths:
        if os.path.exists(path):
            actual_path = path
            break
    
    if not actual_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图像文件不存在"
        )
    
    return FileResponse(actual_path, media_type="image/jpeg")


@router.get("/preview/file/{filename}")
async def get_preview_file(filename: str):
    """
    获取上传图片的预览文件
    
    用于访问上传图片的增强结果
    """
    # 安全检查：防止目录遍历
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的文件名"
        )
    
    # 构建文件路径
    preview_dir = Path(settings.upload_dir) / "augmentation_previews"
    file_path = preview_dir / filename
    
    # 检查文件是否存在且在正确的目录下
    try:
        file_path = file_path.resolve()
        preview_dir = preview_dir.resolve()
        
        if not str(file_path).startswith(str(preview_dir)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此文件"
            )
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在"
            )
        
        return FileResponse(file_path, media_type="image/jpeg")
    except Exception as e:
        logger.error(f"访问预览文件失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="访问文件失败"
        )


# ==================== 自定义脚本 ====================

@router.post("/custom-scripts", response_model=APIResponse[CustomScriptResponse])
async def upload_custom_script(
    name: str = Form(..., min_length=1, max_length=100),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[CustomScriptResponse]:
    """
    上传自定义增强脚本
    
    脚本需符合规范：定义 augment(image: np.ndarray, bboxes: List) -> Tuple[np.ndarray, List]
    """
    # 检查文件类型
    if not file.filename or not file.filename.endswith('.py'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 .py 文件"
        )
    
    # 读取文件内容
    content = await file.read()
    
    # 检查文件大小
    if len(content) > AugmentationConfig.MAX_SCRIPT_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制 ({AugmentationConfig.MAX_SCRIPT_SIZE // 1024 // 1024}MB)"
        )
    
    # 计算哈希
    script_hash = hashlib.sha256(content).hexdigest()
    
    # 检查是否已存在
    result = await db.execute(
        select(CustomAugmentationScript).where(
            and_(
                CustomAugmentationScript.script_hash == script_hash,
                CustomAugmentationScript.created_by == current_user.user_id
            )
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="相同的脚本已存在"
        )
    
    # 验证语法
    is_valid = True
    validation_error = None
    try:
        compile(content.decode('utf-8'), file.filename, 'exec')
        
        # 检查是否包含 augment 函数
        if b'def augment(' not in content:
            is_valid = False
            validation_error = "脚本必须定义 augment 函数"
    except SyntaxError as e:
        is_valid = False
        validation_error = f"语法错误: {e}"
    except Exception as e:
        is_valid = False
        validation_error = f"验证失败: {e}"
    
    # 保存文件
    script_dir = Path(settings.upload_dir) / "custom_scripts" / current_user.user_id
    script_dir.mkdir(parents=True, exist_ok=True)
    
    script_path = script_dir / f"{script_hash[:16]}_{file.filename}"
    with open(script_path, 'wb') as f:
        f.write(content)
    
    # 创建记录
    script_record = CustomAugmentationScript(
        name=name,
        description=description,
        script_path=str(script_path),
        script_hash=script_hash,
        file_size=len(content),
        is_valid=is_valid,
        validation_error=validation_error,
        created_by=current_user.user_id
    )
    
    db.add(script_record)
    await db.commit()
    await db.refresh(script_record)
    
    logger.info(f"用户 {current_user.user_id} 上传自定义脚本: {script_record.id}, name={name}, valid={is_valid}")
    
    return APIResponse.success_response(
        data=CustomScriptResponse.model_validate(script_record),
        message="脚本上传成功" if is_valid else f"脚本上传成功，但验证失败: {validation_error}"
    )


@router.get("/custom-scripts", response_model=APIResponse[PaginatedResponse[CustomScriptResponse]])
async def list_custom_scripts(
    pagination: PaginationParams = Depends(),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[PaginatedResponse[CustomScriptResponse]]:
    """获取自定义脚本列表"""
    conditions = [CustomAugmentationScript.created_by == current_user.user_id]
    
    from sqlalchemy import func
    count_query = select(func.count()).select_from(CustomAugmentationScript).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    result = await db.execute(
        select(CustomAugmentationScript)
        .where(and_(*conditions))
        .order_by(desc(CustomAugmentationScript.created_at))
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    scripts = result.scalars().all()
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=[CustomScriptResponse.model_validate(s) for s in scripts],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    )


@router.delete("/custom-scripts/{script_id}", response_model=APIResponse)
async def delete_custom_script(
    script_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse:
    """删除自定义脚本"""
    result = await db.execute(
        select(CustomAugmentationScript).where(CustomAugmentationScript.id == script_id)
    )
    script = result.scalar_one_or_none()
    
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="脚本不存在"
        )
    
    # 检查权限
    if script.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此脚本"
        )
    
    # 删除文件
    try:
        if os.path.exists(script.script_path):
            os.remove(script.script_path)
    except Exception as e:
        logger.warning(f"删除脚本文件失败: {e}")
    
    await db.delete(script)
    await db.commit()
    
    return APIResponse.success_response(message="脚本删除成功")


# ==================== 配置验证 ====================

@router.post("/validate", response_model=APIResponse)
async def validate_pipeline_config(
    pipeline_config: List[Dict[str, Any]],
    current_user: TokenData = Depends(get_current_user)
) -> APIResponse:
    """
    验证增强流水线配置
    
    返回配置是否有效及错误信息
    """
    is_valid, error_msg = AugmentationConfig.validate_pipeline_config(pipeline_config)
    
    if is_valid:
        return APIResponse.success_response(message="配置验证通过")
    else:
        return APIResponse.error_response(message=f"配置验证失败: {error_msg}")
