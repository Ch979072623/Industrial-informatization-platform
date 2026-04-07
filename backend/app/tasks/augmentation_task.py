"""
数据增强任务模块

提供 Celery 异步任务执行数据增强
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

# 导入服务
from app.services.augmentation_service import (
    get_augmentation_service,
    BBox,
    AugmentationConfig
)


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


@shared_task(bind=True, max_retries=3, soft_time_limit=7200, time_limit=7200)
def augment_dataset_task(
    self,
    job_id: str,
    dataset_id: str,
    pipeline_config: List[Dict[str, Any]],
    augmentation_factor: int,
    output_dataset_id: Optional[str] = None,
    output_dataset_name: Optional[str] = None,
    class_names: Optional[List[str]] = None,
    custom_script_paths: Optional[Dict[str, str]] = None,
    target_split: Optional[str] = 'train',
    include_original: bool = True
) -> Dict[str, Any]:
    """
    数据增强任务
    
    Args:
        self: Celery Task 实例
        job_id: 增强任务ID
        dataset_id: 源数据集ID
        pipeline_config: 增强流水线配置
        augmentation_factor: 增强倍数
        output_dataset_id: 输出数据集ID（可选，用于更新现有数据集）
        output_dataset_name: 输出数据集名称（可选，用于创建新数据集）
        class_names: 类别名称列表
        custom_script_paths: 自定义脚本路径字典 {script_id: script_path}
        target_split: 目标划分 (train/val/test/all)
        include_original: 是否包含原始图像
        
    Returns:
        增强结果
    """
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.models.augmentation import AugmentationJob
    from app.models.dataset import Dataset, DatasetImage
    from sqlalchemy import select
    
    async def _execute_augmentation():
        """异步执行增强"""
        async with AsyncSessionLocal() as db:
            try:
                # 获取任务记录
                result = await db.execute(
                    select(AugmentationJob).where(AugmentationJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                
                if not job:
                    logger.error(f"找不到增强任务: {job_id}")
                    return {
                        "status": "failed",
                        "error": "找不到增强任务"
                    }
                
                # 获取源数据集
                result = await db.execute(
                    select(Dataset).where(Dataset.id == dataset_id)
                )
                source_dataset = result.scalar_one_or_none()
                
                if not source_dataset:
                    raise ValueError(f"找不到源数据集: {dataset_id}")
                
                # 获取所有图像（用于复制原图）
                result = await db.execute(
                    select(DatasetImage).where(DatasetImage.dataset_id == dataset_id)
                )
                all_images = result.scalars().all()
                
                # 获取需要增强的图像（根据 target_split 筛选）
                if target_split and target_split != 'all':
                    images_to_augment = [img for img in all_images if img.split == target_split]
                else:
                    images_to_augment = all_images
                
                if not images_to_augment:
                    raise ValueError(f"数据集中没有符合条件的图像 (target_split={target_split})")
                
                total_images = len(images_to_augment)
                
                # 更新任务状态
                job.status = "running"
                # total_count 只表示要生成的增强图数量（用于进度显示）
                job.total_count = total_images * augmentation_factor
                job.progress = 0.0
                await db.commit()
                
                # 初始化任务状态
                JobState.set(job_id, {
                    'status': 'running',
                    'processed': 0,
                    'generated': 0,
                    'current_image': None
                })
                
                # 创建输出目录
                if output_dataset_name:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_dir = Path(f"uploads/datasets/{output_dataset_name}_{timestamp}")
                else:
                    output_dir = Path(source_dataset.path) / "augmented"
                
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # 创建子目录
                for split in ['train', 'val', 'test']:
                    (output_dir / split / 'images').mkdir(parents=True, exist_ok=True)
                    (output_dir / split / 'labels').mkdir(parents=True, exist_ok=True)
                
                # 如果需要包含原图，先复制所有原图到输出目录
                if include_original:
                    logger.info(f"复制原始图像到输出目录...")
                    for img in all_images:
                        try:
                            # 复制图像
                            src_img_path = img.filepath
                            if not os.path.isabs(src_img_path):
                                if source_dataset.path in src_img_path:
                                    src_img_path = src_img_path
                                else:
                                    src_img_path = os.path.join(source_dataset.path, src_img_path)
                            src_img_path = os.path.normpath(src_img_path)
                            
                            dst_img_path = output_dir / img.split / 'images' / img.filename
                            if os.path.exists(src_img_path):
                                shutil.copy2(src_img_path, dst_img_path)
                            
                            # 复制标注
                            if img.annotation_path:
                                src_label_path = img.annotation_path
                                if not os.path.isabs(src_label_path):
                                    if source_dataset.path in src_label_path:
                                        src_label_path = src_label_path
                                    else:
                                        src_label_path = os.path.join(source_dataset.path, src_label_path)
                                src_label_path = os.path.normpath(src_label_path)
                                
                                dst_label_path = output_dir / img.split / 'labels' / f"{Path(img.filename).stem}.txt"
                                if os.path.exists(src_label_path):
                                    shutil.copy2(src_label_path, dst_label_path)
                        except Exception as e:
                            logger.warning(f"复制原图失败 {img.filename}: {e}")
                
                # 获取增强服务
                service = get_augmentation_service()
                
                # 处理统计
                processed_count = 0
                generated_count = 0
                failed_count = 0
                execution_logs = []
                start_time = datetime.now(timezone.utc)
                
                # 批量处理
                batch_size = 10
                
                for i, image_record in enumerate(images_to_augment):
                    # 检查是否暂停或取消
                    if JobState.is_paused(job_id):
                        logger.info(f"任务 {job_id} 已暂停")
                        job.status = "paused"
                        job.execution_logs = execution_logs
                        await db.commit()
                        return {
                            "status": "paused",
                            "processed": processed_count,
                            "generated": generated_count
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
                            "generated": generated_count
                        }
                    
                    try:
                        # 读取图像
                        image_path = image_record.filepath
                        
                        # 修复路径：检查是否已包含数据集路径，避免重复拼接
                        if not os.path.isabs(image_path):
                            # 如果 filepath 已经包含 source_dataset.path 的一部分，不要重复拼接
                            if source_dataset.path in image_path:
                                image_path = image_path
                            else:
                                image_path = os.path.join(source_dataset.path, image_path)
                        
                        # 标准化路径，去除重复的目录分隔符
                        image_path = os.path.normpath(image_path)
                        
                        if not os.path.exists(image_path):
                            logger.warning(f"图像不存在: {image_path}")
                            failed_count += 1
                            continue
                        
                        image = cv2.imread(image_path)
                        if image is None:
                            logger.warning(f"无法读取图像: {image_path}")
                            failed_count += 1
                            continue
                        
                        # 读取标注
                        bboxes = []
                        label_path = image_record.annotation_path
                        if label_path:
                            if not os.path.isabs(label_path):
                                # 同样修复标注路径
                                if source_dataset.path in label_path:
                                    label_path = label_path
                                else:
                                    label_path = os.path.join(source_dataset.path, label_path)
                                label_path = os.path.normpath(label_path)
                            bboxes = _load_yolo_labels(label_path)
                        
                        # 执行多次增强
                        for aug_idx in range(augmentation_factor):
                            # 更新当前图像状态
                            JobState.set(job_id, {
                                'status': 'running',
                                'processed': processed_count,
                                'generated': generated_count,
                                'current_image': f"{image_record.filename} ({aug_idx + 1}/{augmentation_factor})"
                            })
                            
                            # 执行增强
                            result = service.augment_image(
                                image=image,
                                bboxes=bboxes,
                                pipeline_config=pipeline_config,
                                custom_scripts=custom_script_paths
                            )
                            
                            if not result.success:
                                logger.warning(f"增强失败: {result.error_message}")
                                failed_count += 1
                                continue
                            
                            # 生成输出文件名
                            aug_filename = f"{Path(image_record.filename).stem}_aug{aug_idx}{Path(image_record.filename).suffix}"
                            output_image_path = output_dir / image_record.split / 'images' / aug_filename
                            output_label_path = output_dir / image_record.split / 'labels' / f"{Path(aug_filename).stem}.txt"
                            
                            # 保存图像
                            cv2.imwrite(str(output_image_path), result.image)
                            
                            # 保存标注
                            _save_yolo_labels(output_label_path, result.bboxes)
                            
                            generated_count += 1
                        
                        processed_count += 1
                        
                        # 更新进度（每10张或最后一张）
                        if processed_count % batch_size == 0 or i == total_images - 1:
                            # 进度基于生成的图片数量
                            target_generated = total_images * augmentation_factor
                            progress = (generated_count / target_generated) * 100 if target_generated > 0 else 0
                            job.progress = progress
                            job.processed_count = processed_count
                            job.generated_count = generated_count
                            
                            # 添加日志
                            execution_logs.append({
                                'time': datetime.now(timezone.utc).isoformat(),
                                'processed': processed_count,
                                'generated': generated_count,
                                'failed': failed_count,
                                'current_image': image_record.filename
                            })
                            job.execution_logs = execution_logs
                            
                            await db.commit()
                            
                            # 更新 Celery 任务状态
                            self.update_state(
                                state='PROGRESS',
                                meta={
                                    'current': generated_count,
                                    'total': total_images * augmentation_factor,
                                    'generated': generated_count,
                                    'percent': progress
                                }
                            )
                        
                    except Exception as e:
                        logger.error(f"处理图像 {image_record.filename} 失败: {e}")
                        failed_count += 1
                        execution_logs.append({
                            'time': datetime.now(timezone.utc).isoformat(),
                            'error': str(e),
                            'filename': image_record.filename
                        })
                
                # 计算时间统计
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()
                
                timing_stats = {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat(),
                    'duration_seconds': duration,
                    'images_per_second': processed_count / duration if duration > 0 else 0
                }
                
                # 创建/更新数据集记录
                if output_dataset_name:
                    # 创建新数据集
                    split_desc = f"{target_split}集" if target_split != 'all' else "全部"
                    orig_desc = "含原图" if include_original else "不含原图"
                    new_dataset = Dataset(
                        name=output_dataset_name,
                        description=f"从 {source_dataset.name} 的{split_desc}增强生成 (倍数: {augmentation_factor}, {orig_desc})",
                        path=str(output_dir),
                        format="YOLO",
                        total_images=generated_count + (total_images if include_original else 0),
                        class_names=class_names or source_dataset.class_names,
                        split_ratio=source_dataset.split_ratio,
                        production_line_id=source_dataset.production_line_id,
                        created_by=job.created_by
                    )
                    db.add(new_dataset)
                    await db.flush()
                    
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
                    
                    job.target_dataset_id = new_dataset.id
                
                # 创建 YAML 配置文件
                _create_yaml_config(output_dir, class_names or source_dataset.class_names)
                
                # 更新任务状态为完成
                job.status = "completed"
                job.progress = 100.0
                job.processed_count = processed_count
                # total_count 保持为生成的增强图目标数量
                # generated_count 为实际生成的增强图数量
                job.generated_count = generated_count
                job.execution_logs = execution_logs
                job.timing_stats = timing_stats
                await db.commit()
                
                # 清理任务状态
                JobState.delete(job_id)
                
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "processed": processed_count,
                    "generated": generated_count,
                    "failed": failed_count,
                    "duration_seconds": duration,
                    "output_dir": str(output_dir)
                }
                
            except SoftTimeLimitExceeded:
                logger.error(f"任务 {job_id} 执行超时")
                job.status = "failed"
                job.error_message = "任务执行超时"
                await db.commit()
                raise
                
            except Exception as e:
                logger.error(f"增强任务失败: {e}", exc_info=True)
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
    
    return loop.run_until_complete(_execute_augmentation())


def _load_yolo_labels(label_path: str) -> List[BBox]:
    """
    加载 YOLO 格式标注
    
    Args:
        label_path: 标注文件路径
        
    Returns:
        边界框列表
    """
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
                    
                    # 转换为 Pascal VOC 格式
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
        logger.warning(f"加载标注失败 {label_path}: {e}")
    
    return bboxes


def _save_yolo_labels(label_path: Path, bboxes: List[BBox]) -> None:
    """
    保存 YOLO 格式标注
    
    Args:
        label_path: 输出路径
        bboxes: 边界框列表
    """
    try:
        with open(label_path, 'w') as f:
            for bbox in bboxes:
                # 转换为 YOLO 格式
                x_center = (bbox.x1 + bbox.x2) / 2
                y_center = (bbox.y1 + bbox.y2) / 2
                width = bbox.x2 - bbox.x1
                height = bbox.y2 - bbox.y1
                
                f.write(f"{bbox.class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
    except Exception as e:
        logger.error(f"保存标注失败 {label_path}: {e}")


def _create_yaml_config(output_dir: Path, class_names: List[str]) -> None:
    """
    创建 YOLO 数据集 YAML 配置文件
    
    Args:
        output_dir: 输出目录
        class_names: 类别名称列表
    """
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
    except Exception as e:
        logger.error(f"创建 YAML 配置失败: {e}")


@shared_task
def control_augmentation_job(job_id: str, action: str) -> Dict[str, Any]:
    """
    控制增强任务（暂停/恢复/取消）
    
    Args:
        job_id: 任务ID
        action: 控制动作 (pause/resume/cancel)
        
    Returns:
        控制结果
    """
    try:
        if action == 'pause':
            state = JobState.get(job_id)
            if state and state['status'] == 'running':
                JobState.set(job_id, {**state, 'status': 'paused'})
                return {"success": True, "message": "任务已暂停"}
            return {"success": False, "message": "任务不在运行状态"}
        
        elif action == 'resume':
            state = JobState.get(job_id)
            if state and state['status'] == 'paused':
                JobState.set(job_id, {**state, 'status': 'running'})
                # 重新触发任务
                # 这里需要重新启动 augment_dataset_task
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
def cleanup_augmentation_cache(expiry_hours: int = 24) -> Dict[str, Any]:
    """
    清理过期的增强预览缓存
    
    Args:
        expiry_hours: 过期时间（小时）
        
    Returns:
        清理结果
    """
    from datetime import datetime, timedelta
    from app.db.session import AsyncSessionLocal
    from app.models.augmentation import AugmentationPreview
    from sqlalchemy import select, delete
    
    async def _cleanup():
        async with AsyncSessionLocal() as db:
            try:
                expiry_time = datetime.now(timezone.utc) - timedelta(hours=expiry_hours)
                
                # 查询过期缓存
                result = await db.execute(
                    select(AugmentationPreview).where(
                        AugmentationPreview.expires_at < expiry_time.isoformat()
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
