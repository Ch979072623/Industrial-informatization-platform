"""
数据生成 API 路由

提供数据生成配置、预览、执行和管理功能
"""
import os
import io
import cv2
import base64
import hashlib
import logging
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
from celery.result import AsyncResult

from app.api.deps import get_db, get_current_user, require_admin
from app.core.security import TokenData
from app.core.config import settings
from app.schemas.common import APIResponse, PaginatedResponse, PaginationParams
from app.schemas.generation import (
    GeneratorListResponse,
    GeneratorInfo,
    ValidateConfigRequest,
    ValidateConfigResponse,
    ConfigError,
    GenerationPreviewRequest,
    GenerationPreviewResponse,
    PreviewAnnotation,
    GenerationMetadata,
    GenerationTemplateCreate,
    GenerationTemplateUpdate,
    GenerationTemplateResponse,
    GenerationJobCreate,
    GenerationJobUpdate,
    GenerationJobResponse,
    GenerationJobListQuery,
    ExecuteGenerationRequest,
    ExecuteGenerationResponse,
    JobControlRequest,
    JobControlResponse,
    GenerationJobProgressResponse,
    GenerationErrorDetail,
    QualityReportResponse,
    MergeGenerationRequest,
    MergeGenerationResponse,
    DefectCacheListResponse,
    DefectCacheInfo,
    RefreshCacheRequest,
    HeatmapGenerateRequest,
    HeatmapGenerateResponse
)
from app.models.generation import (
    GenerationTemplate,
    GenerationJob,
    DefectLibraryCache,
    GenerationPreview as GenerationPreviewModel
)
from app.models.dataset import Dataset
from app.ml.generation import GenerationError

# 导入生成服务
from app.services.generation_service import get_generation_service
from app.tasks.generation_task import (
    generate_dataset_task,
    control_generation_job
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generation", tags=["数据生成"])


# ==================== 工具函数 ====================

def check_admin_permission(current_user: TokenData) -> None:
    """检查管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )


def generate_config_hash(config: Dict[str, Any]) -> str:
    """生成配置哈希"""
    config_str = str(sorted(str(config)))
    return hashlib.sha256(config_str.encode()).hexdigest()


def numpy_to_base64(image: np.ndarray, format: str = "jpg") -> str:
    """将 numpy 图像转换为 base64"""
    success, buffer = cv2.imencode(f".{format}", image)
    if not success:
        raise ValueError("图像编码失败")
    return base64.b64encode(buffer).decode("utf-8")


def base64_to_numpy(base64_str: str) -> np.ndarray:
    """将 base64 转换为 numpy 图像"""
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    
    image_data = base64.b64decode(base64_str)
    nparr = np.frombuffer(image_data, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if image is None:
        raise ValueError("无法解码图像")
    
    return image


# ==================== 数据集列表 ====================

@router.get("/datasets", response_model=APIResponse[PaginatedResponse[Dict[str, Any]]])
async def list_datasets_for_generation(
    has_annotations: Optional[bool] = Query(None, description="是否有标注"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[PaginatedResponse[Dict[str, Any]]]:
    """
    获取可用于生成的数据集列表
    
    - 用于选择缺陷源数据集（需要有标注）
    - 用于选择基底数据集（可以无标注）
    """
    from app.models.dataset import Dataset
    
    try:
        # 构建查询条件
        conditions = []
        
        if current_user.role != "admin":
            conditions.append(Dataset.created_by == current_user.user_id)
        
        logger.info(f"查询数据集列表 - 用户: {current_user.user_id}, 角色: {current_user.role}, has_annotations: {has_annotations}")
        
        # 获取数据集列表
        query = select(Dataset)
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await db.execute(query.order_by(Dataset.created_at.desc()))
        datasets = result.scalars().all()
        
        logger.info(f"找到 {len(datasets)} 个数据集")
        
        # 构建响应数据 - 使用 Dataset 模型的现有字段
        items = []
        for dataset in datasets:
            # 直接使用 Dataset 模型的统计字段
            items.append({
                "id": dataset.id,
                "name": dataset.name,
                "description": dataset.description,
                "format": dataset.format,
                "image_count": dataset.total_images,
                "annotated_count": dataset.total_annotations,
                "class_names": dataset.class_names,
                "created_at": dataset.created_at.isoformat()
            })
            
            logger.info(f"数据集: {dataset.name}, 图像: {dataset.total_images}, 有标注: {dataset.total_annotations}")
        
        # 如果有标注筛选条件
        if has_annotations is not None:
            if has_annotations:
                items = [d for d in items if d["annotated_count"] > 0]
            else:
                items = [d for d in items if d["annotated_count"] == 0]
        
        logger.info(f"返回 {len(items)} 个数据集")
        
        return APIResponse.success_response(
            data=PaginatedResponse.create(
                items=items,
                total=len(items),
                page=1,
                page_size=len(items)
            )
        )
        
    except Exception as e:
        logger.error(f"获取数据集列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据集列表失败: {str(e)}"
        )


# ==================== 生成器管理 ====================

@router.get("/generators", response_model=APIResponse[GeneratorListResponse])
async def list_generators(
    current_user: TokenData = Depends(get_current_user)
) -> APIResponse[GeneratorListResponse]:
    """
    获取可用生成器列表
    
    返回所有可用的数据生成器及其配置信息
    """
    try:
        service = get_generation_service()
        generators = service.list_generators()
        
        return APIResponse.success_response(
            data=GeneratorListResponse(generators=generators)
        )
    except Exception as e:
        logger.error(f"获取生成器列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取生成器列表失败: {str(e)}"
        )


@router.post("/validate", response_model=APIResponse[ValidateConfigResponse])
async def validate_config(
    request: ValidateConfigRequest,
    current_user: TokenData = Depends(get_current_user)
) -> APIResponse[ValidateConfigResponse]:
    """
    验证生成器配置
    
    验证给定的生成器配置是否有效
    """
    try:
        service = get_generation_service()
        is_valid, error_msg = service.validate_config(
            request.generator_name,
            request.config
        )
        
        errors = None
        if not is_valid and error_msg:
            errors = [{"field": "config", "message": error_msg}]
        
        return APIResponse.success_response(
            data=ValidateConfigResponse(is_valid=is_valid, errors=errors)
        )
    except ValueError as e:
        return APIResponse.success_response(
            data=ValidateConfigResponse(
                is_valid=False,
                errors=[{"field": "generator_name", "message": str(e)}]
            )
        )
    except Exception as e:
        logger.error(f"配置验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"配置验证失败: {str(e)}"
        )


# ==================== 生成预览 ====================

@router.post("/preview", response_model=APIResponse[GenerationPreviewResponse])
async def create_preview(
    request: GenerationPreviewRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[GenerationPreviewResponse]:
    """
    创建生成预览
    
    根据配置生成单张预览图像，响应时间限制在 2 秒内
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    try:
        service = get_generation_service()
        
        # 特殊处理缺陷迁移生成器：需要加载数据集
        if request.generator_name == "defect_migration":
            from app.ml.generation.defect_migration import DefectMigrationGenerator
            
            # 获取数据集路径
            source_dataset_id = request.config.get("source_dataset_id")
            base_dataset_id = request.config.get("base_dataset_id")
            
            if not source_dataset_id or not base_dataset_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="缺陷迁移生成器需要指定源数据集和基底数据集"
                )
            
            # 查询数据集
            result = await db.execute(select(Dataset).where(Dataset.id == source_dataset_id))
            source_dataset = result.scalar_one_or_none()
            
            result = await db.execute(select(Dataset).where(Dataset.id == base_dataset_id))
            base_dataset = result.scalar_one_or_none()
            
            if not source_dataset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="源数据集不存在"
                )
            if not base_dataset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="基底数据集不存在"
                )
        
        # 使用线程池执行生成（避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        
        def _do_preview():
            generator = service.get_generator(request.generator_name)
            generator.configure(request.config)
            
            # 如果是缺陷迁移生成器，加载数据
            if request.generator_name == "defect_migration" and isinstance(generator, DefectMigrationGenerator):
                # 加载缺陷库
                defect_count = generator.load_defect_library_sync(
                    source_dataset.path,
                    source_dataset.class_names
                )
                if defect_count == 0:
                    raise GenerationError("源数据集中没有可提取的缺陷")
                
                # 加载基底图像
                base_count = generator.load_base_images_sync(base_dataset.path, max_images=10)
                if base_count == 0:
                    raise GenerationError("基底数据集中没有可用的图像")
            
            return generator.generate_single(seed=request.seed)
        
        with ThreadPoolExecutor() as executor:
            # 根据生成器类型设置超时时间
            # 外部 API（如 HuggingFace、Replicate）需要更长时间
            if request.generator_name == "stable_diffusion_api":
                timeout = 60.0  # 外部 API 需要更长超时（模型加载 + 推理）
            else:
                timeout = 5.0   # 本地生成器保持 5 秒
            
            result = await asyncio.wait_for(
                loop.run_in_executor(executor, _do_preview),
                timeout=timeout
            )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"预览生成失败: {result.error_message}"
            )
        
        # 转换图像为 base64
        generated_b64 = numpy_to_base64(
            cv2.cvtColor(result.image, cv2.COLOR_RGB2BGR)
        )
        
        # 构建响应
        metadata = result.metadata or {}
        response_data = GenerationPreviewResponse(
            original_image="",  # 简化处理，不返回原图
            generated_image=f"data:image/jpeg;base64,{generated_b64}",
            annotations=PreviewAnnotation(
                boxes=result.annotations.get("boxes", []),
                labels=result.annotations.get("labels", []),
                scores=result.annotations.get("scores", [])
            ),
            metadata=GenerationMetadata(
                num_defects=metadata.get("num_defects", 0),
                color_match_mode=metadata.get("color_match_mode"),
                placement_strategy=metadata.get("placement_strategy"),
                fusion_quality_scores=metadata.get("fusion_quality_scores"),
                average_quality=result.quality_score,
                api_type=metadata.get("api_type"),
                api_call_time=metadata.get("api_call_time")
            ),
            generation_time=metadata.get("api_call_time", 0)
        )
        
        return APIResponse.success_response(data=response_data)
        
    except asyncio.TimeoutError:
        logger.warning("预览生成超时")
        is_api = request.generator_name == "stable_diffusion_api"
        detail = (
            "预览生成超时（外部 API 需要等待模型加载，请重试）" 
            if is_api 
            else "预览生成超时（5秒），请简化配置或减少数据量"
        )
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=detail
        )
    except GenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"预览生成失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"预览生成失败: {str(e)}"
        )


# ==================== 模板管理 ====================

@router.get("/templates", response_model=APIResponse[PaginatedResponse[GenerationTemplateResponse]])
async def list_templates(
    pagination: PaginationParams = Depends(),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[PaginatedResponse[GenerationTemplateResponse]]:
    """获取生成模板列表"""
    conditions = [
        (GenerationTemplate.created_by == current_user.user_id) |
        (GenerationTemplate.is_preset == True)
    ]
    
    count_query = select(func.count()).select_from(GenerationTemplate).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    result = await db.execute(
        select(GenerationTemplate)
        .where(and_(*conditions))
        .order_by(desc(GenerationTemplate.created_at))
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    templates = result.scalars().all()
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=[GenerationTemplateResponse.model_validate(t) for t in templates],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    )


@router.post("/templates", response_model=APIResponse[GenerationTemplateResponse])
async def create_template(
    request: GenerationTemplateCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[GenerationTemplateResponse]:
    """创建生成模板"""
    # 验证配置
    service = get_generation_service()
    is_valid, error_msg = service.validate_config(request.generator_name, request.config)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"配置验证失败: {error_msg}"
        )
    
    template = GenerationTemplate(
        name=request.name,
        description=request.description,
        generator_name=request.generator_name,
        config=request.config,
        is_preset=False,
        created_by=current_user.user_id
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    logger.info(f"用户 {current_user.user_id} 创建生成模板: {template.id}")
    
    return APIResponse.success_response(
        data=GenerationTemplateResponse.model_validate(template),
        message="模板创建成功"
    )


@router.delete("/templates/{template_id}", response_model=APIResponse)
async def delete_template(
    template_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse:
    """删除生成模板"""
    result = await db.execute(
        select(GenerationTemplate).where(GenerationTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    if template.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此模板"
        )
    
    if template.is_preset:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能删除系统预设模板"
        )
    
    await db.delete(template)
    await db.commit()
    
    return APIResponse.success_response(message="模板删除成功")


# ==================== 生成任务 ====================

@router.get("/jobs", response_model=APIResponse[PaginatedResponse[GenerationJobResponse]])
async def list_jobs(
    query: GenerationJobListQuery = Depends(),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[PaginatedResponse[GenerationJobResponse]]:
    """获取生成任务列表"""
    conditions = [GenerationJob.created_by == current_user.user_id]
    
    if query.status:
        conditions.append(GenerationJob.status == query.status)
    if query.generator_name:
        conditions.append(GenerationJob.generator_name == query.generator_name)
    
    count_query = select(func.count()).select_from(GenerationJob).where(and_(*conditions))
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    result = await db.execute(
        select(GenerationJob)
        .where(and_(*conditions))
        .order_by(desc(GenerationJob.created_at))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    jobs = result.scalars().all()
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=[GenerationJobResponse.model_validate(j) for j in jobs],
            total=total,
            page=query.page,
            page_size=query.page_size
        )
    )


@router.post("/execute", response_model=APIResponse[ExecuteGenerationResponse])
async def execute_generation(
    request: ExecuteGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[ExecuteGenerationResponse]:
    """
    执行批量生成
    
    提交批量生成任务到 Celery 执行
    """
    # 验证配置
    service = get_generation_service()
    is_valid, error_msg = service.validate_config(request.generator_name, request.config)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"配置验证失败: {error_msg}"
        )
    
    # 检查数据集名称是否冲突
    result = await db.execute(
        select(Dataset).where(Dataset.name == request.output_dataset_name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"数据集名称 '{request.output_dataset_name}' 已存在"
        )
    
    # 检查磁盘空间
    disk_space = service.check_disk_space()
    estimated_usage = service.estimate_disk_usage(request.count)
    
    if disk_space.free_mb < estimated_usage * 1.5:  # 保留 50% 余量
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=f"磁盘空间不足。需要 {estimated_usage:.1f} MB，可用 {disk_space.free_mb:.1f} MB"
        )
    
    # 创建任务记录
    job = GenerationJob(
        name=f"生成任务 - {request.output_dataset_name}",
        generator_name=request.generator_name,
        config=request.config,
        count=request.count,
        annotation_format=request.annotation_format,
        status="pending",
        progress=0.0,
        processed_count=0,
        total_count=request.count,
        success_count=0,
        failed_count=0,
        created_by=current_user.user_id
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # 启动 Celery 任务
    try:
        celery_task = generate_dataset_task.delay(
            job_id=job.id,
            generator_name=request.generator_name,
            config=request.config,
            count=request.count,
            output_dataset_name=request.output_dataset_name,
            annotation_format=request.annotation_format
        )
        
        job.celery_task_id = celery_task.id
        await db.commit()
        
        logger.info(f"用户 {current_user.user_id} 创建生成任务: {job.id}")
        
        # 估算时间
        generator = service.get_generator(request.generator_name)
        estimated_time = generator.estimate_time(request.count)
        
        return APIResponse.success_response(
            data=ExecuteGenerationResponse(
                task_id=job.id,
                estimated_time=estimated_time,
                estimated_disk_usage=estimated_usage
            ),
            message="生成任务已提交"
        )
        
    except Exception as e:
        job.status = "failed"
        job.error_message = f"启动 Celery 任务失败: {str(e)}"
        await db.commit()
        
        logger.error(f"启动 Celery 任务失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动生成任务失败: {str(e)}"
        )


@router.get("/jobs/{job_id}", response_model=APIResponse[GenerationJobResponse])
async def get_job(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[GenerationJobResponse]:
    """获取生成任务详情"""
    result = await db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if job.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    return APIResponse.success_response(
        data=GenerationJobResponse.model_validate(job)
    )


@router.post("/jobs/{job_id}/control", response_model=APIResponse[JobControlResponse])
async def control_job(
    job_id: str,
    request: JobControlRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[JobControlResponse]:
    """控制生成任务"""
    result = await db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if job.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权控制此任务"
        )
    
    # 发送控制命令
    control_result = control_generation_job.delay(job_id, request.action)
    result_data = control_result.get(timeout=5)
    
    if result_data.get("success"):
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


@router.get("/jobs/{job_id}/progress", response_model=APIResponse[GenerationJobProgressResponse])
async def get_job_progress(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[GenerationJobProgressResponse]:
    """获取任务进度"""
    result = await db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
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
            job.processed_count = meta.get('processed', job.processed_count)
    
    # 计算预计剩余时间
    estimated_remaining = None
    if job.status == "running" and job.timing_stats:
        images_per_second = job.timing_stats.get('images_per_second', 0)
        remaining = job.total_count - job.processed_count
        if images_per_second > 0:
            estimated_remaining = int(remaining / images_per_second)
    
    # 解析错误信息
    errors = []
    if job.execution_logs:
        for log in job.execution_logs:
            if 'error' in log:
                errors.append(GenerationErrorDetail(
                    image_index=log.get('index', 0),
                    image_name=log.get('filename'),
                    error=log['error']
                ))
    
    return APIResponse.success_response(
        data=GenerationJobProgressResponse(
            task_id=job.id,
            status=job.status,
            progress=job.progress,
            processed_count=job.processed_count,
            total_count=job.total_count,
            success_count=job.success_count,
            failed_count=job.failed_count,
            current_image=None,  # TODO: 从执行日志获取
            estimated_remaining_time=estimated_remaining,
            errors=errors
        )
    )


# ==================== 质量报告 ====================

@router.get("/jobs/{job_id}/quality-report", response_model=APIResponse[QualityReportResponse])
async def get_quality_report(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[QualityReportResponse]:
    """获取质量报告"""
    result = await db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if job.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    if job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务未完成，无法获取质量报告"
        )
    
    if not job.quality_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="质量报告不存在"
        )
    
    return APIResponse.success_response(
        data=QualityReportResponse(**job.quality_report)
    )


# ==================== 合并结果 ====================

@router.post("/merge", response_model=APIResponse[MergeGenerationResponse])
async def merge_generation_results(
    request: MergeGenerationRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[MergeGenerationResponse]:
    """合并生成结果到数据集"""
    # TODO: 实现合并逻辑
    # 1. 验证任务已完成
    # 2. 根据 merge_mode 执行相应操作
    # 3. 处理类别映射
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="合并功能待实现"
    )


# ==================== 缓存管理 ====================

@router.get("/cache", response_model=APIResponse[DefectCacheListResponse])
async def list_caches(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DefectCacheListResponse]:
    """获取缺陷缓存列表"""
    result = await db.execute(
        select(DefectLibraryCache)
        .where(DefectLibraryCache.created_by == current_user.user_id)
        .order_by(desc(DefectLibraryCache.created_at))
    )
    caches = result.scalars().all()
    
    total_size = sum(c.cache_size_mb for c in caches)
    
    return APIResponse.success_response(
        data=DefectCacheListResponse(
            caches=[
                DefectCacheInfo(
                    cache_key=c.cache_key,
                    source_dataset_id=c.source_dataset_id,
                    color_mode=c.color_mode,
                    defect_count=c.defect_count,
                    cache_size_mb=c.cache_size_mb,
                    expires_at=c.expires_at,
                    created_at=c.created_at.isoformat()
                )
                for c in caches
            ],
            total_size_mb=total_size
        )
    )


@router.post("/cache/refresh", response_model=APIResponse)
async def refresh_cache(
    request: RefreshCacheRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse:
    """刷新缺陷缓存"""
    # TODO: 实现缓存刷新逻辑
    # 1. 删除旧缓存
    # 2. 重新提取缺陷
    # 3. 保存新缓存
    
    return APIResponse.success_response(message="缓存刷新任务已提交")


@router.delete("/cache/{cache_key}", response_model=APIResponse)
async def delete_cache(
    cache_key: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse:
    """删除缺陷缓存"""
    result = await db.execute(
        select(DefectLibraryCache).where(
            and_(
                DefectLibraryCache.cache_key == cache_key,
                DefectLibraryCache.created_by == current_user.user_id
            )
        )
    )
    cache = result.scalar_one_or_none()
    
    if not cache:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="缓存不存在"
        )
    
    # 删除缓存文件
    try:
        import shutil
        cache_path = Path(cache.cache_path)
        if cache_path.exists():
            shutil.rmtree(cache_path)
    except Exception as e:
        logger.warning(f"删除缓存文件失败: {e}")
    
    await db.delete(cache)
    await db.commit()
    
    return APIResponse.success_response(message="缓存已删除")


# ==================== 热力图工具 ====================

@router.post("/heatmap/generate", response_model=APIResponse[HeatmapGenerateResponse])
async def generate_heatmap(
    request: HeatmapGenerateRequest,
    current_user: TokenData = Depends(get_current_user)
) -> APIResponse[HeatmapGenerateResponse]:
    """
    生成热力图
    
    内置热力图生成器，支持高斯分布、边缘偏好等
    """
    try:
        width = request.width
        height = request.height
        
        if request.type == "gaussian":
            # 高斯分布热力图
            params = request.params or {}
            center_x = params.get("center_x", width // 2)
            center_y = params.get("center_y", height // 2)
            sigma = params.get("sigma", min(width, height) // 4)
            
            x = np.arange(width)
            y = np.arange(height)
            x, y = np.meshgrid(x, y)
            
            heatmap = np.exp(-((x - center_x) ** 2 + (y - center_y) ** 2) / (2 * sigma ** 2))
            
        elif request.type == "edge":
            # 边缘偏好热力图
            params = request.params or {}
            edge_width = params.get("edge_width", min(width, height) // 10)
            
            heatmap = np.zeros((height, width))
            heatmap[:edge_width, :] = 1  # 上边缘
            heatmap[-edge_width:, :] = 1  # 下边缘
            heatmap[:, :edge_width] = 1  # 左边缘
            heatmap[:, -edge_width:] = 1  # 右边缘
            
            # 应用高斯模糊使边缘平滑
            heatmap = cv2.GaussianBlur(heatmap, (21, 21), 0)
            
        elif request.type == "center":
            # 中心偏好热力图
            heatmap = np.zeros((height, width))
            center_x, center_y = width // 2, height // 2
            max_dist = np.sqrt(center_x ** 2 + center_y ** 2)
            
            for y in range(height):
                for x in range(width):
                    dist = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                    heatmap[y, x] = 1 - (dist / max_dist)
            
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知的热力图类型: {request.type}"
            )
        
        # 归一化到 0-255
        heatmap = (heatmap / heatmap.max() * 255).astype(np.uint8)
        
        # 应用颜色映射
        heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        
        # 转换为 base64
        heatmap_b64 = numpy_to_base64(heatmap_color)
        
        return APIResponse.success_response(
            data=HeatmapGenerateResponse(
                heatmap_image=f"data:image/jpeg;base64,{heatmap_b64}",
                type=request.type
            )
        )
        
    except Exception as e:
        logger.error(f"生成热力图失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成热力图失败: {str(e)}"
        )



# ==================== 任务删除 ====================


class JobDeleteRequest(BaseModel):
    """批量删除请求"""
    status: Optional[str] = Field(None, description="按状态删除")
    job_ids: Optional[List[str]] = Field(None, description="指定要删除的任务ID列表")


class JobDeleteResponse(BaseModel):
    """删除响应"""
    deleted_count: int = Field(..., description="删除的任务数量")


@router.delete("/jobs/{job_id}", response_model=APIResponse[JobDeleteResponse])
async def delete_job(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[JobDeleteResponse]:
    """
    删除单个生成任务
    
    - 只能删除已完成的任务、失败的任务或已取消的任务
    - 运行中的任务需要先取消
    """
    result = await db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if job.created_by != current_user.user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除此任务"
        )
    
    # 检查任务状态
    if job.status in ["running", "pending"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无法删除{job.status}状态的任务，请先取消任务"
        )
    
    # 删除关联的输出数据集（可选）
    if job.output_dataset_id:
        dataset_result = await db.execute(
            select(Dataset).where(Dataset.id == job.output_dataset_id)
        )
        dataset = dataset_result.scalar_one_or_none()
        if dataset:
            # 标记数据集为待删除状态（由清理任务处理）
            dataset.is_deleted = True
            dataset.deleted_at = datetime.utcnow()
            logger.info(f"标记删除数据集: {dataset.id}")
    
    # 删除任务
    await db.delete(job)
    await db.commit()
    
    logger.info(f"用户 {current_user.user_id} 删除生成任务: {job_id}")
    
    return APIResponse.success_response(
        data=JobDeleteResponse(deleted_count=1),
        message="任务已删除"
    )


@router.delete("/jobs", response_model=APIResponse[JobDeleteResponse])
async def delete_jobs(
    request: JobDeleteRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[JobDeleteResponse]:
    """
    批量删除生成任务
    
    - 可以按状态删除或指定ID列表删除
    - 只能删除已完成、失败或已取消的任务
    """
    conditions = [
        GenerationJob.created_by == current_user.user_id,
        GenerationJob.status.in_(["completed", "failed", "cancelled"])
    ]
    
    if request.job_ids:
        conditions.append(GenerationJob.id.in_(request.job_ids))
    elif request.status:
        conditions.append(GenerationJob.status == request.status)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请指定要删除的任务ID列表或状态"
        )
    
    # 查询要删除的任务
    result = await db.execute(
        select(GenerationJob).where(and_(*conditions))
    )
    jobs = result.scalars().all()
    
    deleted_count = 0
    for job in jobs:
        # 删除关联的输出数据集
        if job.output_dataset_id:
            dataset_result = await db.execute(
                select(Dataset).where(Dataset.id == job.output_dataset_id)
            )
            dataset = dataset_result.scalar_one_or_none()
            if dataset:
                dataset.is_deleted = True
                dataset.deleted_at = datetime.utcnow()
        
        await db.delete(job)
        deleted_count += 1
    
    await db.commit()
    
    logger.info(f"用户 {current_user.user_id} 批量删除 {deleted_count} 个生成任务")
    
    return APIResponse.success_response(
        data=JobDeleteResponse(deleted_count=deleted_count),
        message=f"已删除 {deleted_count} 个任务"
    )
