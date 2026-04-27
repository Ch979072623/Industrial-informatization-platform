"""
训练任务 API 路由

提供训练任务的创建、查询、控制和进度跟踪功能
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.core.security import TokenData
from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.training import (
    TrainingJobCreate,
    TrainingJobResponse,
    TrainingJobListQuery,
    TrainingJobControlRequest,
    TrainingJobControlResponse,
    TrainingJobProgressResponse,
)
from app.services.training_service import TrainingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])


def get_training_service(db: AsyncSession = Depends(get_db)) -> TrainingService:
    """获取训练任务服务实例"""
    return TrainingService(db)


# ==================== 训练任务管理 ====================

@router.post("/jobs", response_model=APIResponse[TrainingJobResponse])
async def create_training_job(
    request: TrainingJobCreate,
    current_user: TokenData = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> APIResponse[TrainingJobResponse]:
    """
    创建训练任务
    
    提交训练任务到 Celery 异步执行
    """
    job = await service.create_job(request, current_user.user_id)
    return APIResponse.success_response(
        data=TrainingJobResponse.model_validate(job),
        message="训练任务已提交"
    )


@router.get("/jobs", response_model=APIResponse[PaginatedResponse[TrainingJobResponse]])
async def list_training_jobs(
    status: Optional[str] = None,
    model_builder_config_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: TokenData = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> APIResponse[PaginatedResponse[TrainingJobResponse]]:
    """
    获取训练任务列表
    
    支持按状态、模型构建器配置和数据集筛选
    """
    query = TrainingJobListQuery(
        status=status,
        model_builder_config_id=model_builder_config_id,
        dataset_id=dataset_id,
        page=page,
        page_size=page_size,
    )
    jobs, total = await service.list_jobs(query)
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=[TrainingJobResponse.model_validate(j) for j in jobs],
            total=total,
            page=page,
            page_size=page_size
        )
    )


@router.get("/jobs/{job_id}", response_model=APIResponse[TrainingJobResponse])
async def get_training_job(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> APIResponse[TrainingJobResponse]:
    """获取训练任务详情"""
    job = await service.get_job(job_id)
    return APIResponse.success_response(
        data=TrainingJobResponse.model_validate(job)
    )


@router.get("/jobs/{job_id}/progress", response_model=APIResponse[TrainingJobProgressResponse])
async def get_training_job_progress(
    job_id: str,
    current_user: TokenData = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> APIResponse[TrainingJobProgressResponse]:
    """获取训练任务进度"""
    progress = await service.get_progress(job_id)
    return APIResponse.success_response(data=progress)


@router.post("/jobs/{job_id}/control", response_model=APIResponse[TrainingJobControlResponse])
async def control_training_job(
    job_id: str,
    request: TrainingJobControlRequest,
    current_user: TokenData = Depends(get_current_user),
    service: TrainingService = Depends(get_training_service),
) -> APIResponse[TrainingJobControlResponse]:
    """
    控制训练任务
    
    支持 pause（暂停）、resume（恢复）、cancel（取消）
    """
    result = await service.control_job(job_id, request)
    return APIResponse.success_response(data=result)
