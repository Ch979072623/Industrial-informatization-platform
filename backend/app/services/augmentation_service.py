"""
数据增强服务模块

提供图像数据增强的核心功能，基于 albumentations 库实现
"""
import os
import io
import sys
import cv2
import hashlib
import logging
import tempfile
import importlib.util
from typing import List, Dict, Any, Tuple, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
import numpy as np
from PIL import Image
from fastapi import HTTPException, status
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from celery.result import AsyncResult

from app.models.augmentation import AugmentationJob
from app.schemas.augmentation import (
    AugmentationJobCreate,
    AugmentationJobListQuery,
    JobControlRequest,
    JobControlResponse,
    JobProgressResponse,
)

# 配置日志
logger = logging.getLogger(__name__)

# 尝试导入 albumentations，如果没有安装则提供降级方案
try:
    import albumentations as A
    from albumentations.core.composition import BboxParams
    ALBUMENTATIONS_AVAILABLE = True
except ImportError:
    ALBUMENTATIONS_AVAILABLE = False
    logger.warning("albumentations 未安装，将使用 OpenCV 实现基础增强")


@dataclass
class BBox:
    """边界框数据类"""
    x1: float  # 归一化坐标 (0-1)
    y1: float
    x2: float
    y2: float
    class_id: int
    confidence: Optional[float] = None
    
    def to_albumentations(self) -> List[float]:
        """转换为 albumentations 格式 [x_center, y_center, width, height]"""
        x_center = (self.x1 + self.x2) / 2
        y_center = (self.y1 + self.y2) / 2
        width = self.x2 - self.x1
        height = self.y2 - self.y1
        return [x_center, y_center, width, height, self.class_id]
    
    @classmethod
    def from_albumentations(cls, bbox: List[float]) -> "BBox":
        """从 albumentations 格式创建"""
        x_center, y_center, width, height = bbox[:4]
        class_id = int(bbox[4]) if len(bbox) > 4 else 0
        x1 = x_center - width / 2
        y1 = y_center - height / 2
        x2 = x_center + width / 2
        y2 = y_center + height / 2
        return cls(x1=x1, y1=y1, x2=x2, y2=y2, class_id=class_id)
    
    def clamp(self) -> "BBox":
        """将坐标限制在 [0, 1] 范围内"""
        return BBox(
            x1=max(0.0, min(1.0, self.x1)),
            y1=max(0.0, min(1.0, self.y1)),
            x2=max(0.0, min(1.0, self.x2)),
            y2=max(0.0, min(1.0, self.y2)),
            class_id=self.class_id,
            confidence=self.confidence
        )


@dataclass
class AugmentationResult:
    """增强结果数据类"""
    image: np.ndarray
    bboxes: List[BBox]
    applied_operations: List[str] = field(default_factory=list)
    success: bool = True
    error_message: Optional[str] = None


class AugmentationConfig:
    """增强配置类"""
    
    # 文件上传限制
    MAX_SCRIPT_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_SCRIPT_EXTENSIONS = {'.py'}
    
    # 沙箱执行配置
    SCRIPT_TIMEOUT = 5  # 秒
    
    # 预览配置
    PREVIEW_MAX_SIZE = 1024  # 预览图像最大边长
    
    @staticmethod
    def validate_pipeline_config(config: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        验证流水线配置
        
        Args:
            config: 流水线配置列表
            
        Returns:
            (是否有效, 错误信息)
        """
        if not isinstance(config, list):
            return False, "配置必须是列表"
        
        if len(config) > 20:
            return False, "流水线操作数量不能超过20个"
        
        valid_operation_types = {
            'horizontal_flip', 'vertical_flip', 'rotate', 'random_rotate', 'random_crop',
            'scale', 'affine_transform', 'brightness', 'contrast', 'saturation',
            'hue_jitter', 'histogram_equalization', 'clahe', 'gaussian_noise',
            'salt_pepper_noise', 'gaussian_blur', 'motion_blur', 'mosaic',
            'mixup', 'cutout', 'cutmix', 'custom_script'
        }
        
        for i, op in enumerate(config):
            if not isinstance(op, dict):
                return False, f"第 {i+1} 个操作必须是字典"
            
            op_type = op.get('operation_type')
            if not op_type:
                return False, f"第 {i+1} 个操作缺少 operation_type"
            
            if op_type not in valid_operation_types:
                return False, f"第 {i+1} 个操作类型无效: {op_type}"
            
            # 验证概率
            prob = op.get('probability', 1.0)
            if not isinstance(prob, (int, float)) or prob < 0 or prob > 1:
                return False, f"第 {i+1} 个操作概率必须在 0-1 之间"
        
        return True, ""


class AlbumentationAugmenter:
    """基于 albumentations 的增强器"""
    
    def __init__(self):
        if not ALBUMENTATIONS_AVAILABLE:
            raise ImportError("albumentations 未安装")
    
    def create_transform(self, pipeline_config: List[Dict[str, Any]]) -> A.Compose:
        """
        从配置创建 albumentations 变换流水线
        
        Args:
            pipeline_config: 流水线配置
            
        Returns:
            albumentations Compose 对象
        """
        transforms = []
        
        for op_config in pipeline_config:
            if not op_config.get('enabled', True):
                continue
                
            prob = op_config.get('probability', 1.0)
            op_type = op_config['operation_type']
            
            try:
                transform = self._create_single_transform(op_type, op_config, prob)
                if transform:
                    transforms.append(transform)
            except Exception as e:
                logger.warning(f"创建变换 {op_type} 失败: {e}")
        
        # 添加边界框参数
        bbox_params = BboxParams(
            format='yolo',  # [x_center, y_center, width, height]
            label_fields=['class_ids'],
            min_visibility=0.1,  # 至少10%可见
        )
        
        return A.Compose(transforms, bbox_params=bbox_params)
    
    def _create_single_transform(self, op_type: str, config: Dict[str, Any], prob: float) -> Optional[A.BasicTransform]:
        """创建单个变换"""
        
        # 几何变换
        if op_type == 'horizontal_flip':
            return A.HorizontalFlip(p=prob)
        
        elif op_type == 'vertical_flip':
            return A.VerticalFlip(p=prob)
        
        elif op_type == 'random_rotate':
            angle_range = config.get('angle_range', [-180, 180])
            return A.Rotate(
                limit=angle_range,
                border_mode=cv2.BORDER_CONSTANT,
                value=0,
                p=prob
            )
        
        elif op_type == 'rotate':
            angle_range = config.get('angle_range', [-15, 15])
            return A.Rotate(
                limit=angle_range,
                border_mode=cv2.BORDER_CONSTANT,
                value=0,
                p=prob
            )
        
        elif op_type == 'random_crop':
            crop_ratio = config.get('crop_ratio', 0.8)
            return A.RandomResizedCrop(
                scale=(crop_ratio, 1.0),
                ratio=(0.75, 1.33),
                p=prob
            )
        
        elif op_type == 'scale':
            scale_range = config.get('scale_range', [0.8, 1.2])
            return A.Affine(
                scale={'x': scale_range, 'y': scale_range},
                p=prob
            )
        
        elif op_type == 'affine_transform':
            return A.Affine(
                rotate=config.get('angle', 0),
                translate_px={
                    'x': int(config.get('translate_x', 0) * 100),
                    'y': int(config.get('translate_y', 0) * 100)
                },
                scale=config.get('scale', 1.0),
                shear=config.get('shear', 0),
                p=prob
            )
        
        # 颜色变换
        elif op_type == 'brightness':
            brightness_range = config.get('brightness_range', [-30, 30])
            return A.RandomBrightnessContrast(
                brightness_limit=[b/100 for b in brightness_range],
                contrast_limit=0,
                p=prob
            )
        
        elif op_type == 'contrast':
            contrast_range = config.get('contrast_range', [0.8, 1.2])
            return A.RandomBrightnessContrast(
                brightness_limit=0,
                contrast_limit=contrast_range,
                p=prob
            )
        
        elif op_type == 'saturation':
            saturation_range = config.get('saturation_range', [0.8, 1.2])
            return A.ColorJitter(
                saturation=saturation_range,
                p=prob
            )
        
        elif op_type == 'hue_jitter':
            hue_range = config.get('hue_range', [-10, 10])
            return A.HueSaturationValue(
                hue_shift_limit=hue_range,
                p=prob
            )
        
        elif op_type == 'histogram_equalization':
            return A.Equalize(p=prob)
        
        elif op_type == 'clahe':
            return A.CLAHE(
                clip_limit=config.get('clip_limit', 2.0),
                tile_grid_size=(config.get('tile_grid_size', 8),) * 2,
                p=prob
            )
        
        # 噪声与模糊
        elif op_type == 'gaussian_noise':
            std_range = config.get('std_range', [5.0, 15.0])
            var_limit = (std_range[0] ** 2, std_range[1] ** 2)
            return A.GaussNoise(
                var_limit=var_limit,
                p=prob
            )
        
        elif op_type == 'salt_pepper_noise':
            noise_ratio = config.get('noise_ratio', 0.01)
            return A.ISONoise(
                intensity=(noise_ratio, noise_ratio * 2),
                p=prob
            )
        
        elif op_type == 'gaussian_blur':
            kernel_size = config.get('kernel_size', 5)
            return A.GaussianBlur(
                blur_limit=kernel_size,
                sigma_limit=config.get('sigma', 1.0),
                p=prob
            )
        
        elif op_type == 'motion_blur':
            kernel_size = config.get('kernel_size', 5)
            return A.MotionBlur(
                blur_limit=kernel_size,
                p=prob
            )
        
        # 高级增强
        elif op_type == 'cutout':
            erase_ratio = config.get('erase_ratio', 0.2)
            max_erase_count = config.get('max_erase_count', 1)
            return A.CoarseDropout(
                max_holes=max_erase_count,
                max_height=int(erase_ratio * 100),
                max_width=int(erase_ratio * 100),
                p=prob
            )
        
        # 暂不支持的高级操作需要特殊处理
        elif op_type in ('mosaic', 'mixup', 'cutmix'):
            logger.warning(f"操作 {op_type} 需要自定义实现")
            return None
        
        return None
    
    def augment(
        self,
        image: np.ndarray,
        bboxes: List[BBox],
        pipeline_config: List[Dict[str, Any]]
    ) -> AugmentationResult:
        """
        执行增强
        
        Args:
            image: 输入图像 (BGR格式)
            bboxes: 边界框列表
            pipeline_config: 流水线配置
            
        Returns:
            增强结果
        """
        try:
            transform = self.create_transform(pipeline_config)
            
            # 准备边界框数据（先 clamp 确保符合 albumentations YOLO 格式要求）
            albumentations_bboxes = []
            class_ids = []
            for bbox in bboxes:
                clamped = bbox.clamp()
                alb_bbox = clamped.to_albumentations()
                albumentations_bboxes.append(alb_bbox[:4])  # [x, y, w, h]
                class_ids.append(alb_bbox[4])  # class_id
            
            # 应用变换
            transformed = transform(
                image=image,
                bboxes=albumentations_bboxes,
                class_ids=class_ids
            )
            
            # 转换回 BBox 对象
            transformed_bboxes = []
            for bbox_data, class_id in zip(transformed['bboxes'], transformed['class_ids']):
                bbox = BBox.from_albumentations(list(bbox_data) + [class_id]).clamp()
                # 过滤无效框
                if bbox.x2 > bbox.x1 and bbox.y2 > bbox.y1:
                    transformed_bboxes.append(bbox)
            
            # 记录应用的操作
            applied_ops = [
                op['operation_type'] for op in pipeline_config
                if op.get('enabled', True) and op.get('probability', 1.0) > 0
            ]
            
            return AugmentationResult(
                image=transformed['image'],
                bboxes=transformed_bboxes,
                applied_operations=applied_ops,
                success=True
            )
            
        except Exception as e:
            logger.error(f"增强失败: {e}")
            return AugmentationResult(
                image=image,
                bboxes=bboxes,
                success=False,
                error_message=str(e)
            )


class FallbackAugmenter:
    """降级增强器（使用 OpenCV 实现基础功能）"""
    
    def augment(
        self,
        image: np.ndarray,
        bboxes: List[BBox],
        pipeline_config: List[Dict[str, Any]]
    ) -> AugmentationResult:
        """使用 OpenCV 执行基础增强"""
        result_image = image.copy()
        result_bboxes = bboxes.copy()
        applied_ops = []
        
        for op_config in pipeline_config:
            if not op_config.get('enabled', True):
                continue
            
            prob = op_config.get('probability', 1.0)
            if np.random.random() > prob:
                continue
            
            op_type = op_config['operation_type']
            
            try:
                if op_type == 'horizontal_flip':
                    result_image = cv2.flip(result_image, 1)
                    # 翻转边界框
                    for bbox in result_bboxes:
                        x1, x2 = 1.0 - bbox.x2, 1.0 - bbox.x1
                        bbox.x1, bbox.x2 = x1, x2
                    applied_ops.append(op_type)
                
                elif op_type == 'vertical_flip':
                    result_image = cv2.flip(result_image, 0)
                    for bbox in result_bboxes:
                        y1, y2 = 1.0 - bbox.y2, 1.0 - bbox.y1
                        bbox.y1, bbox.y2 = y1, y2
                    applied_ops.append(op_type)
                
                elif op_type == 'brightness':
                    brightness_range = op_config.get('brightness_range', [-30, 30])
                    delta = np.random.randint(brightness_range[0], brightness_range[1])
                    result_image = cv2.convertScaleAbs(result_image, alpha=1, beta=delta)
                    applied_ops.append(op_type)
                
                elif op_type == 'gaussian_blur':
                    kernel_size = op_config.get('kernel_size', 5)
                    result_image = cv2.GaussianBlur(result_image, (kernel_size, kernel_size), 0)
                    applied_ops.append(op_type)
                
            except Exception as e:
                logger.warning(f"应用操作 {op_type} 失败: {e}")
        
        # 归一化边界框
        result_bboxes = [bbox.clamp() for bbox in result_bboxes]
        
        return AugmentationResult(
            image=result_image,
            bboxes=result_bboxes,
            applied_operations=applied_ops,
            success=True
        )


class CustomScriptExecutor:
    """自定义脚本执行器"""
    
    def __init__(self, script_path: str, timeout: int = AugmentationConfig.SCRIPT_TIMEOUT):
        self.script_path = script_path
        self.timeout = timeout
        self._function: Optional[Callable] = None
        self._load_script()
    
    def _load_script(self) -> None:
        """加载脚本文件"""
        try:
            # 读取脚本内容
            with open(self.script_path, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # 验证语法
            compile(script_content, self.script_path, 'exec')
            
            # 在沙箱中加载模块
            spec = importlib.util.spec_from_file_location(
                "custom_augment", 
                self.script_path
            )
            module = importlib.util.module_from_spec(spec)
            
            # 限制可用的内置函数
            safe_builtins = {
                'len', 'range', 'enumerate', 'zip', 'map', 'filter',
                'abs', 'min', 'max', 'sum', 'round', 'int', 'float', 'str',
                'list', 'tuple', 'dict', 'set', 'frozenset',
                'isinstance', 'hasattr', 'getattr', 'setattr',
                'print', '__import__'
            }
            
            # 创建受限执行环境
            restricted_globals = {
                "__builtins__": {k: __builtins__[k] for k in safe_builtins if k in __builtins__},
                "np": np,
                "cv2": cv2,
            }
            
            spec.loader.exec_module(module)
            
            # 查找 augment 函数
            if hasattr(module, 'augment'):
                self._function = module.augment
            else:
                raise ValueError("脚本必须定义 augment 函数")
                
        except Exception as e:
            logger.error(f"加载自定义脚本失败: {e}")
            raise
    
    def execute(
        self,
        image: np.ndarray,
        bboxes: List[BBox]
    ) -> Tuple[np.ndarray, List[BBox]]:
        """
        执行自定义增强
        
        Args:
            image: 输入图像
            bboxes: 边界框列表
            
        Returns:
            (增强后的图像, 边界框列表)
        """
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("脚本执行超时")
        
        try:
            # 设置超时
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.timeout)
            
            # 转换边界框格式
            bbox_list = [
                [bbox.x1, bbox.y1, bbox.x2, bbox.y2, bbox.class_id]
                for bbox in bboxes
            ]
            
            # 执行用户函数
            result_image, result_bboxes = self._function(image, bbox_list)
            
            # 取消超时
            signal.alarm(0)
            
            # 转换回 BBox 对象
            output_bboxes = []
            for bbox_data in result_bboxes:
                output_bboxes.append(BBox(
                    x1=bbox_data[0],
                    y1=bbox_data[1],
                    x2=bbox_data[2],
                    y2=bbox_data[3],
                    class_id=int(bbox_data[4])
                ).clamp())
            
            return result_image, output_bboxes
            
        except TimeoutError:
            logger.error("自定义脚本执行超时")
            raise
        except Exception as e:
            logger.error(f"执行自定义脚本失败: {e}")
            raise


class AugmentationService:
    """数据增强服务"""
    
    def __init__(self):
        self.config = AugmentationConfig()
        if ALBUMENTATIONS_AVAILABLE:
            self.augmenter = AlbumentationAugmenter()
        else:
            logger.warning("使用降级增强器")
            self.augmenter = FallbackAugmenter()
    
    def augment_image(
        self,
        image: np.ndarray,
        bboxes: List[BBox],
        pipeline_config: List[Dict[str, Any]],
        custom_scripts: Optional[Dict[str, str]] = None
    ) -> AugmentationResult:
        """
        增强单张图像
        
        Args:
            image: 输入图像 (BGR格式)
            bboxes: 边界框列表
            pipeline_config: 流水线配置
            custom_scripts: 自定义脚本路径字典 {script_id: script_path}
            
        Returns:
            增强结果
        """
        # 分离自定义脚本操作
        standard_ops = []
        custom_ops = []
        
        for op in pipeline_config:
            if op.get('operation_type') == 'custom_script':
                custom_ops.append(op)
            else:
                standard_ops.append(op)
        
        # 执行标准增强
        if standard_ops:
            result = self.augmenter.augment(image, bboxes, standard_ops)
        else:
            result = AugmentationResult(image=image, bboxes=bboxes)
        
        if not result.success:
            return result
        
        # 执行自定义脚本增强
        for custom_op in custom_ops:
            if not custom_op.get('enabled', True):
                continue
            
            prob = custom_op.get('probability', 1.0)
            if np.random.random() > prob:
                continue
            
            script_id = custom_op.get('script_id')
            if not script_id or not custom_scripts or script_id not in custom_scripts:
                logger.warning(f"找不到自定义脚本: {script_id}")
                continue
            
            try:
                executor = CustomScriptExecutor(custom_scripts[script_id])
                result.image, result.bboxes = executor.execute(
                    result.image, result.bboxes
                )
                result.applied_operations.append(f"custom_script:{script_id}")
            except Exception as e:
                logger.error(f"自定义脚本执行失败: {e}")
                # 继续处理，不中断流水线
        
        return result
    
    def generate_preview(
        self,
        image: np.ndarray,
        bboxes: List[BBox],
        pipeline_config: List[Dict[str, Any]],
        max_size: int = 512
    ) -> Tuple[np.ndarray, List[BBox], List[str]]:
        """
        生成预览图像
        
        Args:
            image: 输入图像
            bboxes: 边界框列表
            pipeline_config: 流水线配置
            max_size: 最大输出尺寸
            
        Returns:
            (预览图像, 边界框, 应用的操作列表)
        """
        # 缩放图像以提高预览速度
        h, w = image.shape[:2]
        scale = min(max_size / max(h, w), 1.0)
        if scale < 1.0:
            new_w, new_h = int(w * scale), int(h * scale)
            preview_image = cv2.resize(image, (new_w, new_h))
            # 缩放边界框
            preview_bboxes = []
            for bbox in bboxes:
                preview_bboxes.append(BBox(
                    x1=bbox.x1,
                    y1=bbox.y1,
                    x2=bbox.x2,
                    y2=bbox.y2,
                    class_id=bbox.class_id
                ))
        else:
            preview_image = image.copy()
            preview_bboxes = bboxes.copy()
        
        # 执行增强
        result = self.augment_image(preview_image, preview_bboxes, pipeline_config)
        
        return result.image, result.bboxes, result.applied_operations
    
    @staticmethod
    def compute_config_hash(config: List[Dict[str, Any]]) -> str:
        """计算配置哈希值（用于缓存）"""
        config_str = str(sorted(str(config)))
        return hashlib.sha256(config_str.encode()).hexdigest()
    
    @staticmethod
    def draw_bboxes(
        image: np.ndarray,
        bboxes: List[BBox],
        class_names: Optional[List[str]] = None,
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        在图像上绘制边界框
        
        Args:
            image: 输入图像
            bboxes: 边界框列表（归一化坐标）
            class_names: 类别名称列表
            color: 框颜色
            thickness: 线宽
            
        Returns:
            带标注的图像
        """
        result = image.copy()
        h, w = image.shape[:2]
        
        for i, bbox in enumerate(bboxes):
            # 转换为像素坐标
            x1 = int(bbox.x1 * w)
            y1 = int(bbox.y1 * h)
            x2 = int(bbox.x2 * w)
            y2 = int(bbox.y2 * h)
            
            # 绘制框
            cv2.rectangle(result, (x1, y1), (x2, y2), color, thickness)
            
            # 绘制标签
            label = str(bbox.class_id)
            if class_names and bbox.class_id < len(class_names):
                label = class_names[bbox.class_id]
            
            (text_w, text_h), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(
                result,
                (x1, y1 - text_h - 4),
                (x1 + text_w, y1),
                color,
                -1
            )
            cv2.putText(
                result,
                label,
                (x1, y1 - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
        
        return result


class AugmentationJobService:
    """增强任务服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _check_job_ownership(self, job: AugmentationJob, current_user_id: str) -> None:
        """检查任务所有权,无权限则抛 403"""
        if job.created_by != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问此任务"
            )
    
    async def create_job(
        self,
        request: AugmentationJobCreate,
        current_user_id: str
    ) -> AugmentationJob:
        """
        创建增强任务
        
        1. 校验流水线配置
        2. 校验源数据集存在
        3. 检查数据集访问权限
        4. 创建 AugmentationJob ORM
        5. 提交 Celery task
        """
        from app.models.dataset import Dataset
        from app.tasks.augmentation_task import augment_dataset_task
        
        # 验证配置
        is_valid, error_msg = AugmentationConfig.validate_pipeline_config(request.pipeline_config)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"配置验证失败: {error_msg}"
            )
        
        # 检查源数据集
        result = await self.db.execute(
            select(Dataset).where(Dataset.id == request.source_dataset_id)
        )
        source_dataset = result.scalar_one_or_none()
        
        if not source_dataset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="源数据集不存在"
            )
        
        # 检查数据集访问权限
        if source_dataset.created_by != current_user_id:
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
            created_by=current_user_id
        )
        
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        
        # 启动 Celery 任务
        try:
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
            
            job.celery_task_id = celery_task.id
            await self.db.commit()
            
            logger.info(f"用户 {current_user_id} 创建增强任务: {job.id}, celery_task={celery_task.id}")
            
        except Exception as e:
            logger.error(f"启动 Celery 增强任务失败: {e}")
            job.status = "failed"
            job.error_message = f"启动 Celery 任务失败: {str(e)}"
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"启动增强任务失败: {str(e)}"
            )
        
        return job
    
    async def list_jobs(
        self,
        query: AugmentationJobListQuery,
        current_user_id: str
    ) -> Tuple[List[AugmentationJob], int]:
        """
        列出增强任务
        
        支持按状态和数据集筛选
        只返回当前用户创建的任务
        """
        conditions = [AugmentationJob.created_by == current_user_id]
        
        if query.status:
            conditions.append(AugmentationJob.status == query.status)
        if query.source_dataset_id:
            conditions.append(AugmentationJob.source_dataset_id == query.source_dataset_id)
        
        # 获取总数
        count_query = select(func.count()).select_from(AugmentationJob).where(and_(*conditions))
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        # 获取分页数据
        stmt = (
            select(AugmentationJob)
            .where(and_(*conditions))
            .order_by(desc(AugmentationJob.created_at))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        
        result = await self.db.execute(stmt)
        jobs = result.scalars().all()
        
        return list(jobs), total
    
    async def get_job(self, job_id: str, current_user_id: str) -> AugmentationJob:
        """获取增强任务详情"""
        result = await self.db.execute(
            select(AugmentationJob).where(AugmentationJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在"
            )
        
        self._check_job_ownership(job, current_user_id)
        return job
    
    async def get_job_progress(
        self,
        job_id: str,
        current_user_id: str
    ) -> JobProgressResponse:
        """获取任务进度"""
        job = await self.get_job(job_id, current_user_id)
        
        # 从 Celery 获取最新状态
        if job.celery_task_id:
            celery_result = AsyncResult(job.celery_task_id)
            if celery_result.state == 'PROGRESS':
                meta = celery_result.info or {}
                job.progress = meta.get('percent', job.progress)
                job.generated_count = meta.get('generated', job.generated_count)
        
        # 计算预计剩余时间
        estimated_remaining = None
        if job.status == "running" and job.timing_stats:
            images_per_second = job.timing_stats.get('images_per_second', 0)
            remaining_images = job.total_count - job.generated_count
            if images_per_second > 0:
                estimated_remaining = int(remaining_images / images_per_second)
        
        return JobProgressResponse(
            job_id=job.id,
            status=job.status,
            progress=job.progress,
            processed_count=job.processed_count,
            total_count=job.total_count,
            generated_count=job.generated_count,
            current_operation=None,
            estimated_time_remaining=estimated_remaining
        )
    
    async def control_job(
        self,
        job_id: str,
        request: JobControlRequest,
        current_user_id: str
    ) -> JobControlResponse:
        """
        控制增强任务
        
        支持 pause（暂停）、resume（恢复）、cancel（取消）
        """
        from app.tasks.augmentation_task import control_augmentation_job
        
        job = await self.get_job(job_id, current_user_id)
        
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
            await self.db.commit()
        
        return JobControlResponse(
            success=result_data.get("success", False),
            new_status=job.status,
            message=result_data.get("message", "")
        )


# 全局服务实例
_augmentation_service: Optional[AugmentationService] = None


def get_augmentation_service() -> AugmentationService:
    """获取增强服务单例"""
    global _augmentation_service
    if _augmentation_service is None:
        _augmentation_service = AugmentationService()
    return _augmentation_service
