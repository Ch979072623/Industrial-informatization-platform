"""
数据生成任务模块

提供 Celery 异步任务执行数据生成
"""
import os
import cv2
import json
import logging
import shutil
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
import numpy as np

# 配置日志
logger = logging.getLogger(__name__)


class JobState:
    """任务状态管理（用于支持暂停/恢复）"""
    _states: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def get(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return cls._states.get(job_id)
    
    @classmethod
    def set(cls, job_id: str, state: Dict[str, Any]) -> None:
        """设置任务状态"""
        cls._states[job_id] = state
    
    @classmethod
    def delete(cls, job_id: str) -> None:
        """删除任务状态"""
        cls._states.pop(job_id, None)
    
    @classmethod
    def is_paused(cls, job_id: str) -> bool:
        """检查任务是否暂停"""
        state = cls.get(job_id)
        return state is not None and state.get('status') == 'paused'
    
    @classmethod
    def is_cancelled(cls, job_id: str) -> bool:
        """检查任务是否被取消"""
        state = cls.get(job_id)
        return state is not None and state.get('status') == 'cancelled'


def _create_yaml_config(output_dir: Path, class_names: List[str]) -> None:
    """创建YOLO数据集YAML配置文件"""
    import yaml
    
    yaml_config = {
        "path": str(output_dir),
        "train": "train/images",
        "val": "val/images",
        "test": "test/images" if (output_dir / "test" / "images").exists() else None,
        "nc": len(class_names),
        "names": class_names
    }
    
    # 移除 None 值
    yaml_config = {k: v for k, v in yaml_config.items() if v is not None}
    
    try:
        yaml_path = output_dir / "data.yaml"
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_config, f, allow_unicode=True, sort_keys=False)
        logger.info(f"已创建 YAML 配置文件: {yaml_path}")
    except Exception as e:
        logger.error(f"创建 YAML 配置失败: {e}")


@shared_task(bind=True, max_retries=3, soft_time_limit=7200, time_limit=7200)
def generate_dataset_task(
    self,
    job_id: str,
    generator_name: str,
    config: Dict[str, Any],
    count: int,
    output_dataset_name: str,
    annotation_format: str = "yolo"
) -> Dict[str, Any]:
    """
    数据生成任务
    
    Args:
        self: Celery Task 实例
        job_id: 生成任务ID
        generator_name: 生成器名称
        config: 生成配置
        count: 生成数量
        output_dataset_name: 输出数据集名称
        annotation_format: 标注格式
        
    Returns:
        生成结果
    """
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.models.generation import GenerationJob
    from app.models.dataset import Dataset, DatasetImage
    from sqlalchemy import select
    
    async def _execute_generation():
        """异步执行生成"""
        async with AsyncSessionLocal() as db:
            try:
                # 获取任务记录
                result = await db.execute(
                    select(GenerationJob).where(GenerationJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                
                if not job:
                    logger.error(f"找不到生成任务: {job_id}")
                    return {
                        "status": "failed",
                        "error": "找不到生成任务"
                    }
                
                # 导入生成服务
                from app.services.generation_service import get_generation_service
                from app.ml.generation import GeneratorRegistry
                from app.models.dataset import Dataset
                
                service = get_generation_service()
                
                # 初始化数据集变量
                source_dataset = None
                base_dataset = None
                
                # 获取生成器
                try:
                    generator = GeneratorRegistry.create_generator(generator_name)
                    generator.configure(config)
                    
                    # 如果是缺陷迁移生成器，加载数据集
                    if generator_name == "defect_migration":
                        from app.ml.generation.defect_migration import DefectMigrationGenerator
                        if isinstance(generator, DefectMigrationGenerator):
                            logger.info("初始化缺陷迁移生成器...")
                    elif generator_name == "stable_diffusion_api":
                        logger.info("初始化 Stable Diffusion API 生成器...")
                        logger.info(f"配置: api_endpoint={config.get('api_endpoint')}, prompt={config.get('prompt', '')[:50]}...")
                    else:
                        logger.info(f"初始化 {generator_name} 生成器...")
                    
                    # 缺陷迁移生成器需要加载数据集
                    if generator_name == "defect_migration":
                        from app.ml.generation.defect_migration import DefectMigrationGenerator
                        if isinstance(generator, DefectMigrationGenerator):
                            # 获取数据集
                            source_dataset_id = config.get("source_dataset_id")
                            base_dataset_id = config.get("base_dataset_id")
                            
                            if source_dataset_id and base_dataset_id:
                                result = await db.execute(
                                    select(Dataset).where(Dataset.id == source_dataset_id)
                                )
                                source_dataset = result.scalar_one_or_none()
                                
                                result = await db.execute(
                                    select(Dataset).where(Dataset.id == base_dataset_id)
                                )
                                base_dataset = result.scalar_one_or_none()
                                
                                if source_dataset and base_dataset:
                                    logger.info(f"源数据集路径: {source_dataset.path}")
                                    logger.info(f"基底数据集路径: {base_dataset.path}")
                                    
                                    # 加载缺陷库
                                    defect_count = generator.load_defect_library_sync(
                                        source_dataset.path,
                                        source_dataset.class_names
                                    )
                                    logger.info(f"从源数据集加载了 {defect_count} 个缺陷")
                                    
                                    # 加载基底图像
                                    base_count = generator.load_base_images_sync(
                                        base_dataset.path,
                                        max_images=100
                                    )
                                    logger.info(f"从基底数据集加载了 {base_count} 张图像")
                                    logger.info(f"缺陷库大小: {len(generator.defect_library)}, 基底图像数: {len(generator.base_images)}")
                                else:
                                    if not source_dataset:
                                        logger.error(f"源数据集不存在: {source_dataset_id}")
                                    if not base_dataset:
                                        logger.error(f"基底数据集不存在: {base_dataset_id}")
                except Exception as e:
                    logger.error(f"初始化生成器失败: {e}")
                    job.status = "failed"
                    job.error_message = f"初始化生成器失败: {str(e)}"
                    await db.commit()
                    return {
                        "status": "failed",
                        "error": f"初始化生成器失败: {str(e)}"
                    }
                
                # 更新任务状态
                job.status = "running"
                job.total_count = count
                job.progress = 0.0
                await db.commit()
                
                # 初始化任务状态
                JobState.set(job_id, {
                    'status': 'running',
                    'processed': 0,
                    'success': 0,
                    'failed': 0,
                    'current_image': None
                })
                
                # 创建输出目录
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = Path(f"uploads/datasets/{output_dataset_name}_{timestamp}")
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # 创建子目录
                for split in ['train', 'val', 'test']:
                    (output_dir / split / 'images').mkdir(parents=True, exist_ok=True)
                    (output_dir / split / 'labels').mkdir(parents=True, exist_ok=True)
                
                # 统计数据
                processed_count = 0
                success_count = 0
                failed_count = 0
                execution_logs = []
                quality_scores = []
                total_annotations_count = 0  # 总标注数量
                start_time = datetime.now(timezone.utc)
                
                # 批量处理
                batch_size = 10
                
                logger.info(f"开始生成 {count} 张图像...")
                
                for i in range(count):
                    logger.info(f"生成第 {i+1}/{count} 张图像...")
                    
                    # 检查是否暂停或取消
                    if JobState.is_paused(job_id):
                        logger.info(f"任务 {job_id} 已暂停")
                        job.status = "paused"
                        job.execution_logs = execution_logs
                        await db.commit()
                        return {
                            "status": "paused",
                            "processed": processed_count,
                            "success": success_count,
                            "failed": failed_count
                        }
                    
                    if JobState.is_cancelled(job_id):
                        logger.info(f"任务 {job_id} 已取消")
                        job.status = "cancelled"
                        job.execution_logs = execution_logs
                        await db.commit()
                        # 清理输出目录
                        shutil.rmtree(output_dir, ignore_errors=True)
                        return {
                            "status": "cancelled",
                            "processed": processed_count,
                            "success": success_count,
                            "failed": failed_count
                        }
                    
                    try:
                        # 生成单张图像
                        logger.info(f"调用 generate_single(seed={i})...")
                        result = generator.generate_single(seed=i)
                        logger.info(f"生成结果: success={result.success}, has_image={result.image is not None}")
                        
                        if not result.success or result.image is None:
                            logger.warning(f"生成失败: {result.error_message}")
                            failed_count += 1
                            execution_logs.append({
                                'time': datetime.now(timezone.utc).isoformat(),
                                'index': i,
                                'error': result.error_message or "未知错误"
                            })
                            continue
                        
                        # 确定保存位置（简单划分：80% train, 10% val, 10% test）
                        rand = np.random.random()
                        if rand < 0.8:
                            split = 'train'
                        elif rand < 0.9:
                            split = 'val'
                        else:
                            split = 'test'
                        
                        # 保存图像
                        filename = f"generated_{i:05d}.jpg"
                        image_path = output_dir / split / 'images' / filename
                        
                        # 转换 RGB 到 BGR 保存
                        image_bgr = cv2.cvtColor(result.image, cv2.COLOR_RGB2BGR)
                        cv2.imwrite(str(image_path), image_bgr)
                        
                        # 保存标注
                        label_path = output_dir / split / 'labels' / f"generated_{i:05d}.txt"
                        service.save_annotations(
                            result.annotations,
                            label_path,
                            annotation_format,
                            result.image.shape[1],
                            result.image.shape[0]
                        )
                        
                        success_count += 1
                        quality_scores.append(result.quality_score)
                        
                        # 累加标注数量
                        boxes = result.annotations.get("boxes", [])
                        total_annotations_count += len(boxes)
                        
                    except Exception as e:
                        logger.error(f"生成图像 {i} 失败: {e}")
                        failed_count += 1
                        execution_logs.append({
                            'time': datetime.now(timezone.utc).isoformat(),
                            'index': i,
                            'error': str(e)
                        })
                    
                    processed_count += 1
                    
                    # 更新进度
                    if processed_count % batch_size == 0 or i == count - 1:
                        progress = (processed_count / count) * 100 if count > 0 else 0
                        job.progress = progress
                        job.processed_count = processed_count
                        job.success_count = success_count
                        job.failed_count = failed_count
                        
                        # 添加日志
                        execution_logs.append({
                            'time': datetime.now(timezone.utc).isoformat(),
                            'processed': processed_count,
                            'success': success_count,
                            'failed': failed_count
                        })
                        job.execution_logs = execution_logs
                        
                        await db.commit()
                        
                        # 更新 Celery 任务状态
                        self.update_state(
                            state='PROGRESS',
                            meta={
                                'current': processed_count,
                                'total': count,
                                'success': success_count,
                                'failed': failed_count,
                                'percent': progress
                            }
                        )
                
                # 计算时间统计
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                timing_stats = {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'duration_seconds': duration,
                    'images_per_second': processed_count / duration if duration > 0 else 0
                }
                
                # 生成质量报告
                quality_report = service.generate_quality_report(
                    {
                        "success_count": success_count,
                        "failed_count": failed_count,
                        "quality_scores": quality_scores,
                        "errors": [log for log in execution_logs if 'error' in log]
                    },
                    job_id
                )
                
                # 获取源数据集的类别名称
                class_names = ["defect"]  # 默认类别
                if generator_name == "defect_migration" and source_dataset:
                    class_names = source_dataset.class_names
                    logger.info(f"使用源数据集类别名称: {class_names}")
                
                # 创建数据集记录
                new_dataset = Dataset(
                    name=output_dataset_name,
                    description=f"由 {generator_name} 生成 ({success_count} 张图像)",
                    path=str(output_dir),
                    format=annotation_format.upper(),
                    total_images=success_count,
                    total_annotations=total_annotations_count,
                    class_names=class_names,
                    split_ratio={"train": 0.8, "val": 0.1, "test": 0.1},
                    created_by=job.created_by
                )
                db.add(new_dataset)
                await db.flush()
                
                # 创建 YAML 配置文件
                _create_yaml_config(output_dir, class_names)
                
                # 创建图像记录
                for split in ['train', 'val', 'test']:
                    image_dir = output_dir / split / 'images'
                    if image_dir.exists():
                        for img_file in image_dir.iterdir():
                            if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
                                new_image = DatasetImage(
                                    dataset_id=new_dataset.id,
                                    name_id=img_file.stem,
                                    filename=img_file.name,
                                    filepath=str(Path(split) / 'images' / img_file.name),
                                    split=split,
                                    annotation_path=str(Path(split) / 'labels' / f"{img_file.stem}.txt")
                                )
                                db.add(new_image)
                
                job.output_dataset_id = new_dataset.id
                
                # 更新任务状态为完成
                job.status = "completed"
                job.progress = 100.0
                job.processed_count = processed_count
                job.success_count = success_count
                job.failed_count = failed_count
                job.execution_logs = execution_logs
                job.quality_report = quality_report
                job.timing_stats = timing_stats
                await db.commit()
                
                # 清理任务状态
                JobState.delete(job_id)
                
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "processed": processed_count,
                    "success": success_count,
                    "failed": failed_count,
                    "duration_seconds": duration,
                    "output_dir": str(output_dir),
                    "output_dataset_id": new_dataset.id
                }
                
            except SoftTimeLimitExceeded:
                logger.error(f"任务 {job_id} 执行超时")
                job.status = "failed"
                job.error_message = "任务执行超时"
                await db.commit()
                raise
                
            except Exception as e:
                logger.error(f"生成任务失败: {e}", exc_info=True)
                job.status = "failed"
                job.error_message = str(e)
                job.execution_logs = execution_logs if 'execution_logs' in locals() else []
                await db.commit()
                
                # 尝试重试
                try:
                    self.retry(exc=e, countdown=60)
                except MaxRetriesExceededError:
                    logger.error(f"任务 {job_id} 达到最大重试次数")
                    raise
                
                raise
    
    # 运行异步函数
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_execute_generation())


@shared_task
def control_generation_job(job_id: str, action: str) -> Dict[str, Any]:
    """
    控制生成任务（暂停/恢复/取消）
    
    Args:
        job_id: 任务ID
        action: 控制动作 (pause/resume/cancel)
        
    Returns:
        控制结果
    """
    try:
        if action == 'pause':
            state = JobState.get(job_id)
            if state and state.get('status') == 'running':
                JobState.set(job_id, {**state, 'status': 'paused'})
                return {"success": True, "message": "任务已暂停"}
            return {"success": False, "message": "任务不在运行状态"}
        
        elif action == 'resume':
            state = JobState.get(job_id)
            if state and state.get('status') == 'paused':
                JobState.set(job_id, {**state, 'status': 'running'})
                return {"success": True, "message": "任务已恢复"}
            return {"success": False, "message": "任务不在暂停状态"}
        
        elif action == 'cancel':
            JobState.set(job_id, {'status': 'cancelled'})
            return {"success": True, "message": "任务已取消"}
        
        else:
            return {"success": False, "message": f"未知动作: {action}"}
            
    except Exception as e:
        logger.error(f"控制任务失败: {e}")
        return {"success": False, "message": str(e)}


@shared_task
def cleanup_generation_cache(expiry_hours: int = 24) -> Dict[str, Any]:
    """
    清理过期的生成预览缓存
    
    Args:
        expiry_hours: 过期时间（小时）
        
    Returns:
        清理结果
    """
    from datetime import datetime, timedelta
    from app.db.session import AsyncSessionLocal
    from app.models.generation import GenerationPreview
    from sqlalchemy import select, delete
    
    async def _cleanup():
        async with AsyncSessionLocal() as db:
            try:
                expiry_time = datetime.now(timezone.utc) - timedelta(hours=expiry_hours)
                
                # 查询过期缓存
                result = await db.execute(
                    select(GenerationPreview).where(
                        GenerationPreview.expires_at < expiry_time.isoformat()
                    )
                )
                expired_caches = result.scalars().all()
                
                deleted_count = 0
                for cache in expired_caches:
                    # 删除预览图像文件
                    try:
                        if os.path.exists(cache.preview_image_path):
                            os.remove(cache.preview_image_path)
                    except Exception as e:
                        logger.warning(f"删除预览文件失败: {e}")
                    
                    await db.delete(cache)
                    deleted_count += 1
                
                await db.commit()
                
                return {
                    "success": True,
                    "deleted_count": deleted_count,
                    "message": f"清理了 {deleted_count} 个过期缓存"
                }
                
            except Exception as e:
                logger.error(f"清理缓存失败: {e}")
                await db.rollback()
                return {"success": False, "message": str(e)}
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(_cleanup())
