"""
训练任务服务层

提供训练任务的创建、查询、控制和进度跟踪功能
"""
import logging
from typing import List, Tuple
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from celery.result import AsyncResult

from app.schemas.training import (
    TrainingJobCreate,
    TrainingJobListQuery,
    TrainingJobControlRequest,
    TrainingJobControlResponse,
    TrainingJobProgressResponse,
)
from app.models.training_job import TrainingJob
from app.models.ml_module import ModelBuilderConfig
from app.models.dataset import Dataset
from app.tasks.training_task import train_model

logger = logging.getLogger(__name__)


class TrainingService:
    """训练任务服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_job(self, request: TrainingJobCreate, current_user_id: str) -> TrainingJob:
        """
        创建训练任务
        
        1. 校验 ModelBuilderConfig 存在
        2. 校验 Dataset 存在
        3. hyperparams 软兜底 + 范围校验
        4. 创建 TrainingJob ORM
        5. 提交 Celery task
        """
        # 检查模型构建器配置
        result = await self.db.execute(
            select(ModelBuilderConfig).where(ModelBuilderConfig.id == request.model_builder_config_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="模型构建器配置不存在"
            )
        
        # 检查数据集
        result = await self.db.execute(
            select(Dataset).where(Dataset.id == request.dataset_id)
        )
        dataset = result.scalar_one_or_none()
        if not dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="数据集不存在"
            )
        
        # 检查访问权限 (对齐 augmentation: 403)
        if config.created_by != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此模型构建器配置"
            )
        if dataset.created_by != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此数据集"
            )
        
        # hyperparams 软兜底
        hyperparams = dict(request.hyperparams) if request.hyperparams else {}
        hyperparams.setdefault('epochs', 150)
        hyperparams.setdefault('batch', 32)
        hyperparams.setdefault('imgsz', 640)
        
        # 范围校验
        epochs = hyperparams.get('epochs')
        if epochs is not None and (not isinstance(epochs, (int, float)) or epochs < 1 or epochs > 1000):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="epochs 必须在 1-1000 之间"
            )
        batch = hyperparams.get('batch')
        if batch is not None and (not isinstance(batch, (int, float)) or batch < 1 or batch > 512):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="batch 必须在 1-512 之间"
            )
        imgsz = hyperparams.get('imgsz')
        if imgsz is not None and (not isinstance(imgsz, (int, float)) or imgsz < 64 or imgsz > 2048):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="imgsz 必须在 64-2048 之间"
            )
        
        # 创建任务记录
        job = TrainingJob(
            model_builder_config_id=request.model_builder_config_id,
            dataset_id=request.dataset_id,
            production_line_id=request.production_line_id,
            hyperparams=hyperparams,
            status="pending",
            progress=0.0,
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        
        # 启动 Celery 任务
        try:
            celery_task = train_model.delay(job.id)
            job.celery_task_id = celery_task.id
            await self.db.commit()
            await self.db.refresh(job)
            logger.info(f"用户 {current_user_id} 创建训练任务: {job.id}, celery_task={celery_task.id}")
        except Exception as e:
            logger.error(f"启动 Celery 训练任务失败: {e}")
            job.status = "failed"
            job.error_message = f"启动 Celery 任务失败: {str(e)}"
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"启动训练任务失败: {str(e)}"
            )
        
        return job
    
    async def list_jobs(self, query: TrainingJobListQuery) -> Tuple[List[TrainingJob], int]:
        """
        列出训练任务
        
        支持按状态、模型构建器配置ID、数据集ID过滤和分页
        """
        conditions = []
        
        if query.status:
            conditions.append(TrainingJob.status == query.status)
        if query.model_builder_config_id:
            conditions.append(TrainingJob.model_builder_config_id == query.model_builder_config_id)
        if query.dataset_id:
            conditions.append(TrainingJob.dataset_id == query.dataset_id)
        
        # 获取总数
        count_query = select(func.count()).select_from(TrainingJob)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        # 获取分页数据
        stmt = select(TrainingJob).order_by(desc(TrainingJob.created_at))
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.offset((query.page - 1) * query.page_size).limit(query.page_size)
        
        result = await self.db.execute(stmt)
        jobs = result.scalars().all()
        
        return list(jobs), total
    
    async def get_job(self, job_id: str) -> TrainingJob:
        """获取训练任务详情"""
        result = await self.db.execute(
            select(TrainingJob).where(TrainingJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="训练任务不存在"
            )
        return job
    
    async def get_progress(self, job_id: str) -> TrainingJobProgressResponse:
        """获取训练任务进度"""
        job = await self.get_job(job_id)
        
        processed_epochs = 0
        total_epochs = 150
        current_operation = None
        
        # 从 Celery 获取实时进度
        if job.celery_task_id and job.status in ("running", "pending"):
            try:
                celery_result = AsyncResult(job.celery_task_id)
                if celery_result.state == 'PROGRESS':
                    meta = celery_result.info or {}
                    job.progress = meta.get('progress', job.progress)
                    processed_epochs = meta.get('processed_epochs', 0)
                    total_epochs = meta.get('total_epochs', total_epochs)
                    current_operation = meta.get('current_operation')
            except Exception as e:
                logger.warning(f"获取 Celery 任务进度失败: {e}")
        
        # 从 hyperparams 获取 total_epochs
        if job.hyperparams and isinstance(job.hyperparams, dict):
            total_epochs = job.hyperparams.get('epochs', total_epochs)
        
        return TrainingJobProgressResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            processed_epochs=int(processed_epochs),
            total_epochs=int(total_epochs),
            current_operation=current_operation,
            error_message=job.error_message,
        )
    
    async def control_job(
        self,
        job_id: str,
        request: TrainingJobControlRequest
    ) -> TrainingJobControlResponse:
        """
        控制训练任务
        
        支持 pause、resume、cancel (对齐 augmentation)
        """
        job = await self.get_job(job_id)
        action = request.action
        
        if action == "cancel":
            if job.celery_task_id:
                try:
                    AsyncResult(job.celery_task_id).revoke(terminate=True)
                except Exception as e:
                    logger.warning(f"撤销 Celery 任务失败: {e}")
            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            return TrainingJobControlResponse(
                job_id=job.id,
                action=action,
                status=job.status,
                message="任务已取消"
            )
        
        elif action == "pause":
            if job.status != "running":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="任务不在运行状态，无法暂停"
                )
            job.status = "paused"
            await self.db.commit()
            return TrainingJobControlResponse(
                job_id=job.id,
                action=action,
                status=job.status,
                message="任务已暂停 (P5-S2 占位: 真实暂停需 P5-S3 支持)"
            )
        
        elif action == "resume":
            if job.status != "paused":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="任务不在暂停状态，无法恢复"
                )
            job.status = "running"
            await self.db.commit()
            return TrainingJobControlResponse(
                job_id=job.id,
                action=action,
                status=job.status,
                message="任务已恢复 (P5-S2 占位: 真实恢复需 P5-S3 支持)"
            )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的操作: {action}"
        )
