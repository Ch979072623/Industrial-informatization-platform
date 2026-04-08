"""
数据生成服务模块

提供数据生成的核心功能，包括缺陷库管理、生成任务执行等
"""
import os
import cv2
import json
import hashlib
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Callable
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

# 配置日志
logger = logging.getLogger(__name__)

# 导入生成器
from app.ml.generation import (
    BaseGenerator,
    GeneratorRegistry,
    GenerationResult,
    GenerationError
)


@dataclass
class DiskSpaceInfo:
    """磁盘空间信息"""
    total: int
    used: int
    free: int
    
    @property
    def free_mb(self) -> float:
        return self.free / (1024 * 1024)


class GenerationService:
    """
    数据生成服务
    
    管理生成器、缺陷库缓存和生成任务
    """
    
    def __init__(self):
        """初始化服务"""
        # 初始化生成器注册表
        from app.ml.generation.registry import init_generators
        init_generators()
        
        self._cache_dir = Path("uploads/generation_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
    
    # ==================== 生成器管理 ====================
    
    def list_generators(self) -> List[Dict[str, Any]]:
        """
        列出所有可用生成器
        
        Returns:
            生成器信息列表
        """
        return GeneratorRegistry.list_generators()
    
    def get_generator(self, name: str) -> BaseGenerator:
        """
        获取生成器实例
        
        Args:
            name: 生成器名称
            
        Returns:
            生成器实例
        """
        return GeneratorRegistry.get_generator(name)
    
    def validate_config(self, generator_name: str, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        验证生成器配置
        
        Args:
            generator_name: 生成器名称
            config: 配置参数
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            generator = GeneratorRegistry.get_generator(generator_name)
            is_valid, error_msg = generator.validate_config(config)
            return is_valid, error_msg
        except Exception as e:
            return False, str(e)
    
    # ==================== 缺陷库管理 ====================
    
    def extract_defects_from_dataset(
        self,
        dataset_id: str,
        color_mode: str = "standard",
        progress_callback: Optional[Callable] = None
    ) -> Tuple[int, str]:
        """
        从数据集提取缺陷区域
        
        Args:
            dataset_id: 数据集ID
            color_mode: 颜色匹配模式
            progress_callback: 进度回调
            
        Returns:
            (缺陷数量, 缓存路径)
        """
        # TODO: 实现从数据集提取缺陷的逻辑
        # 需要访问数据集标注文件，提取标注框区域
        logger.info(f"从数据集 {dataset_id} 提取缺陷（待实现）")
        return 0, ""
    
    def get_cache_key(self, dataset_id: str, color_mode: str) -> str:
        """
        生成缓存键
        
        Args:
            dataset_id: 数据集ID
            color_mode: 颜色匹配模式
            
        Returns:
            缓存键
        """
        return f"{dataset_id}:{color_mode}"
    
    def get_defect_cache_path(self, cache_key: str) -> Path:
        """
        获取缺陷缓存路径
        
        Args:
            cache_key: 缓存键
            
        Returns:
            缓存目录路径
        """
        cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return self._cache_dir / cache_hash
    
    def check_disk_space(self, path: str = ".") -> DiskSpaceInfo:
        """
        检查磁盘空间
        
        Args:
            path: 路径
            
        Returns:
            磁盘空间信息
        """
        import shutil
        total, used, free = shutil.disk_usage(path)
        return DiskSpaceInfo(total=total, used=used, free=free)
    
    def estimate_disk_usage(
        self,
        count: int,
        width: int = 512,
        height: int = 512,
        format_factor: float = 1.5
    ) -> float:
        """
        估算磁盘使用量
        
        Args:
            count: 图像数量
            width: 图像宽度
            height: 图像高度
            format_factor: 格式因子（包含标注文件的额外空间）
            
        Returns:
            预计使用空间（MB）
        """
        # 假设 JPEG 压缩率
        bytes_per_pixel = 0.5
        image_size = width * height * bytes_per_pixel
        total_bytes = image_size * count * format_factor
        return total_bytes / (1024 * 1024)
    
    # ==================== 生成执行 ====================
    
    def generate_preview(
        self,
        generator_name: str,
        config: Dict[str, Any],
        seed: Optional[int] = None
    ) -> GenerationResult:
        """
        生成预览图像
        
        Args:
            generator_name: 生成器名称
            config: 配置参数
            seed: 随机种子
            
        Returns:
            GenerationResult
        """
        try:
            generator = GeneratorRegistry.create_generator(generator_name)
            generator.configure(config)
            
            result = generator.generate_single(seed=seed)
            
            return result
            
        except Exception as e:
            logger.error(f"生成预览失败: {e}")
            return GenerationResult(
                success=False,
                error_message=str(e)
            )
    
    def generate_batch(
        self,
        generator_name: str,
        config: Dict[str, Any],
        count: int,
        output_dir: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        批量生成图像
        
        Args:
            generator_name: 生成器名称
            config: 配置参数
            count: 生成数量
            output_dir: 输出目录
            progress_callback: 进度回调
            
        Returns:
            生成结果统计
        """
        try:
            generator = GeneratorRegistry.create_generator(generator_name)
            generator.configure(config)
            
            results = generator.generate_batch(
                count=count,
                output_dir=output_dir,
                progress_callback=progress_callback
            )
            
            return results
            
        except Exception as e:
            logger.error(f"批量生成失败: {e}")
            return {
                "success_count": 0,
                "failed_count": count,
                "output_paths": [],
                "annotations": [],
                "quality_scores": [],
                "errors": [{"image_index": 0, "error": str(e)}]
            }
    
    # ==================== 标注格式转换 ====================
    
    def convert_annotation_format(
        self,
        annotations: List[Dict[str, Any]],
        source_format: str,
        target_format: str,
        image_width: int,
        image_height: int
    ) -> List[Dict[str, Any]]:
        """
        转换标注格式
        
        Args:
            annotations: 标注列表
            source_format: 源格式 (yolo/coco/voc)
            target_format: 目标格式 (yolo/coco/voc)
            image_width: 图像宽度
            image_height: 图像高度
            
        Returns:
            转换后的标注列表
        """
        if source_format == target_format:
            return annotations
        
        converted = []
        
        for ann in annotations:
            if source_format == "yolo" and target_format == "voc":
                # YOLO: [class_id, x_center, y_center, width, height] (归一化)
                # VOC: [x1, y1, x2, y2] (像素)
                x_center = ann["boxes"][1] * image_width
                y_center = ann["boxes"][2] * image_height
                width = ann["boxes"][3] * image_width
                height = ann["boxes"][4] * image_height
                
                x1 = x_center - width / 2
                y1 = y_center - height / 2
                x2 = x_center + width / 2
                y2 = y_center + height / 2
                
                converted.append({
                    "boxes": [x1, y1, x2, y2],
                    "label": ann["boxes"][0]
                })
                
            elif source_format == "voc" and target_format == "yolo":
                # VOC 到 YOLO
                x1, y1, x2, y2 = ann["boxes"]
                
                x_center = (x1 + x2) / 2 / image_width
                y_center = (y1 + y2) / 2 / image_height
                width = (x2 - x1) / image_width
                height = (y2 - y1) / image_height
                
                converted.append({
                    "boxes": [ann.get("label", 0), x_center, y_center, width, height]
                })
            
            else:
                # 其他转换暂不实现
                converted.append(ann)
        
        return converted
    
    def save_annotations(
        self,
        annotations: Dict[str, Any],
        output_path: Path,
        format: str,
        image_width: int,
        image_height: int
    ) -> bool:
        """
        保存标注文件
        
        Args:
            annotations: 标注数据
            output_path: 输出路径
            format: 格式 (yolo/coco/voc)
            image_width: 图像宽度
            image_height: 图像高度
            
        Returns:
            是否成功
        """
        try:
            if format == "yolo":
                with open(output_path, 'w') as f:
                    for box, label in zip(annotations.get("boxes", []), annotations.get("labels", [])):
                        # box 应该是 [x1, y1, x2, y2] 归一化格式
                        x_center = (box[0] + box[2]) / 2
                        y_center = (box[1] + box[3]) / 2
                        width = box[2] - box[0]
                        height = box[3] - box[1]
                        f.write(f"{label} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
            
            elif format == "coco":
                # COCO 格式需要整个数据集的信息，这里只保存单个图像的标注
                coco_ann = {
                    "images": [{"id": 0, "width": image_width, "height": image_height}],
                    "annotations": [],
                    "categories": []
                }
                
                for i, (box, label) in enumerate(zip(annotations.get("boxes", []), annotations.get("labels", []))):
                    x1, y1, x2, y2 = box
                    width = x2 - x1
                    height = y2 - y1
                    
                    coco_ann["annotations"].append({
                        "id": i,
                        "image_id": 0,
                        "category_id": label,
                        "bbox": [x1 * image_width, y1 * image_height, width * image_width, height * image_height],
                        "area": width * height * image_width * image_height,
                        "iscrowd": 0
                    })
                
                with open(output_path, 'w') as f:
                    json.dump(coco_ann, f, indent=2)
            
            elif format == "voc":
                # Pascal VOC XML 格式
                # 简化实现，实际需要生成完整的 XML
                import xml.etree.ElementTree as ET
                
                root = ET.Element("annotation")
                ET.SubElement(root, "filename").text = output_path.stem + ".jpg"
                
                size = ET.SubElement(root, "size")
                ET.SubElement(size, "width").text = str(image_width)
                ET.SubElement(size, "height").text = str(image_height)
                ET.SubElement(size, "depth").text = "3"
                
                for box, label in zip(annotations.get("boxes", []), annotations.get("labels", [])):
                    obj = ET.SubElement(root, "object")
                    ET.SubElement(obj, "name").text = str(label)
                    ET.SubElement(obj, "difficult").text = "0"
                    
                    bndbox = ET.SubElement(obj, "bndbox")
                    ET.SubElement(bndbox, "xmin").text = str(int(box[0] * image_width))
                    ET.SubElement(bndbox, "ymin").text = str(int(box[1] * image_height))
                    ET.SubElement(bndbox, "xmax").text = str(int(box[2] * image_width))
                    ET.SubElement(bndbox, "ymax").text = str(int(box[3] * image_height))
                
                tree = ET.ElementTree(root)
                tree.write(output_path, encoding="utf-8", xml_declaration=True)
            
            return True
            
        except Exception as e:
            logger.error(f"保存标注失败: {e}")
            return False
    
    # ==================== 质量报告 ====================
    
    def generate_quality_report(
        self,
        results: Dict[str, Any],
        task_id: str
    ) -> Dict[str, Any]:
        """
        生成质量报告
        
        Args:
            results: 生成结果
            task_id: 任务ID
            
        Returns:
            质量报告
        """
        quality_scores = results.get("quality_scores", [])
        errors = results.get("errors", [])
        
        # 计算质量分布
        quality_distribution = {
            "excellent": sum(1 for s in quality_scores if s >= 0.8),
            "good": sum(1 for s in quality_scores if 0.6 <= s < 0.8),
            "fair": sum(1 for s in quality_scores if 0.4 <= s < 0.6),
            "poor": sum(1 for s in quality_scores if s < 0.4)
        }
        
        report = {
            "task_id": task_id,
            "total_images": results.get("success_count", 0) + results.get("failed_count", 0),
            "success_count": results.get("success_count", 0),
            "failed_count": results.get("failed_count", 0),
            "average_quality_score": np.mean(quality_scores) if quality_scores else 0,
            "quality_distribution": quality_distribution,
            "failed_images": errors
        }
        
        return report


# 全局服务实例
_generation_service: Optional[GenerationService] = None


def get_generation_service() -> GenerationService:
    """获取生成服务单例"""
    global _generation_service
    if _generation_service is None:
        _generation_service = GenerationService()
    return _generation_service
