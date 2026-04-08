"""
缺陷迁移生成器

基于 LAB 颜色空间匹配的缺陷迁移生成器（论文方法实现）
支持多种颜色匹配模式和放置策略
"""
import os
import cv2
import json
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from dataclasses import dataclass

from app.ml.generation.base import BaseGenerator, GenerationResult, GenerationError
from app.ml.generation.registry import register_generator

logger = logging.getLogger(__name__)


@dataclass
class DefectRegion:
    """缺陷区域数据类"""
    image: np.ndarray  # 缺陷图像（RGB）
    mask: np.ndarray   # 缺陷掩码（二值）
    bbox: Tuple[int, int, int, int]  # (x, y, w, h) 像素坐标
    class_id: int
    class_name: str = ""


@dataclass
class PlacementResult:
    """放置结果数据类"""
    success: bool
    position: Optional[Tuple[int, int]] = None  # (x, y) 左上角位置
    error_message: Optional[str] = None


class ColorMatcher:
    """颜色匹配器 - LAB 颜色空间匹配"""
    
    @staticmethod
    def lab_match(
        defect_region: np.ndarray,
        target_region: np.ndarray,
        clip_limit: float = 2.0,
        tile_grid_size: int = 8,
        brightness_adjust: float = 1.0,
        contrast_factor: float = 1.5
    ) -> np.ndarray:
        """
        LAB 颜色空间匹配
        
        Args:
            defect_region: 缺陷区域图像（BGR）
            target_region: 目标区域图像（BGR）
            clip_limit: CLAHE clipLimit
            tile_grid_size: CLAHE tileGridSize
            brightness_adjust: 亮度调整强度
            contrast_factor: 对比度增强因子
            
        Returns:
            匹配后的缺陷区域（BGR）
        """
        try:
            # 转换到 LAB 颜色空间
            defect_lab = cv2.cvtColor(defect_region, cv2.COLOR_BGR2LAB).astype(np.float32)
            target_lab = cv2.cvtColor(target_region, cv2.COLOR_BGR2LAB).astype(np.float32)
            
            # 分离通道
            l_defect, a_defect, b_defect = cv2.split(defect_lab)
            l_target, a_target, b_target = cv2.split(target_lab)
            
            # L 通道：统计匹配
            mean_defect_l = np.mean(l_defect)
            std_defect_l = np.std(l_defect)
            mean_target_l = np.mean(l_target)
            std_target_l = np.std(l_target)
            
            if std_defect_l > 0:
                l_matched = (l_defect - mean_defect_l) * (std_target_l / std_defect_l) + mean_target_l
            else:
                l_matched = l_defect - mean_defect_l + mean_target_l
            
            # 应用 CLAHE
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_grid_size, tile_grid_size))
            l_enhanced = clahe.apply(np.clip(l_matched, 0, 255).astype(np.uint8))
            
            # 亮度调整
            if brightness_adjust != 1.0:
                l_enhanced = np.clip(l_enhanced * brightness_adjust, 0, 255).astype(np.uint8)
            
            # 对比度增强
            if contrast_factor != 1.0:
                mean_l = np.mean(l_enhanced)
                l_enhanced = np.clip((l_enhanced - mean_l) * contrast_factor + mean_l, 0, 255).astype(np.uint8)
            
            # AB 通道：轻度调整
            a_matched = a_defect * 0.7 + a_target.mean() * 0.3
            b_matched = b_defect * 0.7 + b_target.mean() * 0.3
            
            # 合并通道
            matched_lab = cv2.merge([
                l_enhanced.astype(np.float32),
                np.clip(a_matched, 0, 255),
                np.clip(b_matched, 0, 255)
            ])
            
            # 转换回 BGR
            result = cv2.cvtColor(matched_lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
            
            return result
            
        except Exception as e:
            logger.error(f"LAB 匹配失败: {e}")
            return defect_region


class PlacementStrategy:
    """放置策略类"""
    
    def __init__(
        self,
        strategy_type: str = "random",
        image_shape: Tuple[int, int] = (0, 0),
        roi: Optional[Tuple[int, int, int, int]] = None,
        heatmap: Optional[np.ndarray] = None,
        heatmap_config: Optional[Dict[str, Any]] = None,
        grid_config: Optional[Dict[str, int]] = None,
        max_attempts: int = 20,
        allow_overlap: bool = False,
        max_overlap_ratio: float = 0.3
    ):
        """
        初始化放置策略
        
        Args:
            strategy_type: 策略类型 (random/region/grid/heatmap/preference)
            image_shape: 图像尺寸 (H, W)
            roi: 感兴趣区域 (x, y, w, h)
            heatmap: 热力图（概率分布）
            heatmap_config: 热力图配置 {'type': str, ...}
            grid_config: 网格配置 {'rows': int, 'cols': int}
            max_attempts: 最大尝试次数
            allow_overlap: 是否允许重叠
            max_overlap_ratio: 最大重叠比例
        """
        self.strategy_type = strategy_type
        self.image_shape = image_shape
        self.roi = roi
        self.heatmap = heatmap
        self.heatmap_config = heatmap_config or {}
        self.grid_config = grid_config
        self.max_attempts = max_attempts
        self.allow_overlap = allow_overlap
        self.max_overlap_ratio = max_overlap_ratio
        self.placed_boxes: List[Tuple[int, int, int, int]] = []
    
    def get_placement(
        self,
        defect_width: int,
        defect_height: int,
        seed: Optional[int] = None
    ) -> PlacementResult:
        """
        获取放置位置
        
        Args:
            defect_width: 缺陷宽度
            defect_height: 缺陷高度
            seed: 随机种子
            
        Returns:
            PlacementResult
        """
        if seed is not None:
            np.random.seed(seed)
        
        for attempt in range(self.max_attempts):
            position = self._calculate_position(defect_width, defect_height)
            
            if position is None:
                continue
            
            x, y = position
            new_box = (x, y, defect_width, defect_height)
            
            # 检查边界
            if not self._check_boundary(new_box):
                continue
            
            # 检查重叠
            if not self.allow_overlap and self._check_overlap(new_box):
                continue
            
            self.placed_boxes.append(new_box)
            return PlacementResult(success=True, position=position)
        
        return PlacementResult(
            success=False,
            error_message=f"经过 {self.max_attempts} 次尝试未能找到合适位置"
        )
    
    def _calculate_position(
        self,
        defect_width: int,
        defect_height: int
    ) -> Optional[Tuple[int, int]]:
        """计算放置位置"""
        h, w = self.image_shape
        
        if self.strategy_type == "random":
            # 完全随机
            x = np.random.randint(0, max(1, w - defect_width))
            y = np.random.randint(0, max(1, h - defect_height))
            return (x, y)
        
        elif self.strategy_type == "region" and self.roi:
            # 指定区域内随机
            rx, ry, rw, rh = self.roi
            x = np.random.randint(rx, max(rx + 1, rx + rw - defect_width))
            y = np.random.randint(ry, max(ry + 1, ry + rh - defect_height))
            return (x, y)
        
        elif self.strategy_type == "heatmap":
            # 热力图引导
            heatmap_to_use = self.heatmap
            
            # 如果没有提供热力图，根据配置生成
            if heatmap_to_use is None and self.heatmap_config:
                heatmap_to_use = self._generate_heatmap_from_config(h, w)
            
            if heatmap_to_use is not None:
                # 确保热力图尺寸匹配
                if heatmap_to_use.shape != (h, w):
                    heatmap_resized = cv2.resize(heatmap_to_use, (w, h))
                else:
                    heatmap_resized = heatmap_to_use
                
                # 归一化
                heatmap_norm = heatmap_resized / heatmap_resized.sum() if heatmap_resized.sum() > 0 else heatmap_resized
                
                # 采样
                flat_probs = heatmap_norm.flatten()
                flat_probs = np.maximum(flat_probs, 0)  # 确保非负
                if flat_probs.sum() > 0:
                    flat_probs = flat_probs / flat_probs.sum()
                    idx = np.random.choice(len(flat_probs), p=flat_probs)
                    y, x = divmod(idx, w)
                    x = min(x, w - defect_width)
                    y = min(y, h - defect_height)
                    return (max(0, x), max(0, y))
            
            # 热力图为空或生成失败，退化为随机
            x = np.random.randint(0, max(1, w - defect_width))
            y = np.random.randint(0, max(1, h - defect_height))
            return (x, y)
        
        elif self.strategy_type == "center":
            # 中心优先
            center_x, center_y = w // 2, h // 2
            max_offset = min(w, h) // 4
            x = center_x + np.random.randint(-max_offset, max_offset) - defect_width // 2
            y = center_y + np.random.randint(-max_offset, max_offset) - defect_height // 2
            return (max(0, min(x, w - defect_width)), max(0, min(y, h - defect_height)))
        
        elif self.strategy_type == "edge":
            # 边缘优先
            edge_width = min(w, h) // 10
            side = np.random.choice(['top', 'bottom', 'left', 'right'])
            if side == 'top':
                x = np.random.randint(0, max(1, w - defect_width))
                y = np.random.randint(0, edge_width)
            elif side == 'bottom':
                x = np.random.randint(0, max(1, w - defect_width))
                y = np.random.randint(max(0, h - edge_width - defect_height), h - defect_height)
            elif side == 'left':
                x = np.random.randint(0, edge_width)
                y = np.random.randint(0, max(1, h - defect_height))
            else:  # right
                x = np.random.randint(max(0, w - edge_width - defect_width), w - defect_width)
                y = np.random.randint(0, max(1, h - defect_height))
            return (max(0, x), max(0, y))
        
        elif self.strategy_type == "grid":
            # 网格式均匀分布
            # 从配置获取行列数，默认为 3x3
            grid_config = getattr(self, 'grid_config', None) or {'rows': 3, 'cols': 3}
            rows = grid_config.get('rows', 3)
            cols = grid_config.get('cols', 3)
            
            # 计算每个网格的大小
            cell_w = w // cols
            cell_h = h // rows
            
            # 确保缺陷能放入网格
            if cell_w < defect_width or cell_h < defect_height:
                # 网格太小，退化为随机
                x = np.random.randint(0, max(1, w - defect_width))
                y = np.random.randint(0, max(1, h - defect_height))
                return (x, y)
            
            # 随机选择一个网格
            row = np.random.randint(0, rows)
            col = np.random.randint(0, cols)
            
            # 在网格内随机放置
            x = col * cell_w + np.random.randint(0, max(1, cell_w - defect_width))
            y = row * cell_h + np.random.randint(0, max(1, cell_h - defect_height))
            
            return (x, y)
        
        else:
            # 默认随机
            x = np.random.randint(0, max(1, w - defect_width))
            y = np.random.randint(0, max(1, h - defect_height))
            return (x, y)
    
    def _check_boundary(self, box: Tuple[int, int, int, int]) -> bool:
        """检查边界"""
        x, y, w, h = box
        img_h, img_w = self.image_shape
        return 0 <= x and x + w <= img_w and 0 <= y and y + h <= img_h
    
    def _check_overlap(self, new_box: Tuple[int, int, int, int]) -> bool:
        """检查重叠"""
        nx, ny, nw, nh = new_box
        n_area = nw * nh
        
        for box in self.placed_boxes:
            bx, by, bw, bh = box
            
            # 计算交集
            ix = max(0, min(nx + nw, bx + bw) - max(nx, bx))
            iy = max(0, min(ny + nh, by + bh) - max(ny, by))
            inter_area = ix * iy
            
            if n_area > 0 and inter_area / n_area > self.max_overlap_ratio:
                return True
        
        return False
    
    def _generate_heatmap_from_config(self, h: int, w: int) -> Optional[np.ndarray]:
        """根据配置生成热力图"""
        try:
            heatmap_type = self.heatmap_config.get('type', 'gaussian')
            
            if heatmap_type == 'gaussian':
                # 高斯分布热力图
                center_x = int(self.heatmap_config.get('center_x', 50) / 100 * w)
                center_y = int(self.heatmap_config.get('center_y', 50) / 100 * h)
                sigma = int(self.heatmap_config.get('sigma', 30) / 100 * min(w, h))
                
                x = np.arange(w)
                y = np.arange(h)
                x, y = np.meshgrid(x, y)
                
                heatmap = np.exp(-((x - center_x) ** 2 + (y - center_y) ** 2) / (2 * sigma ** 2))
                return (heatmap * 255).astype(np.uint8)
                
            elif heatmap_type == 'edge':
                # 边缘偏好热力图
                edge_width = int(self.heatmap_config.get('edge_width', 10) / 100 * min(w, h))
                
                heatmap = np.zeros((h, w), dtype=np.float32)
                heatmap[:edge_width, :] = 1  # 上边缘
                heatmap[-edge_width:, :] = 1  # 下边缘
                heatmap[:, :edge_width] = 1  # 左边缘
                heatmap[:, -edge_width:] = 1  # 右边缘
                
                # 应用高斯模糊使边缘平滑
                heatmap = cv2.GaussianBlur(heatmap, (21, 21), 0)
                return (heatmap * 255).astype(np.uint8)
                
            elif heatmap_type == 'center':
                # 中心偏好热力图（高斯分布的简化版）
                center_x, center_y = w // 2, h // 2
                max_dist = np.sqrt((w/2) ** 2 + (h/2) ** 2)
                sigma = max_dist / 2
                
                x = np.arange(w)
                y = np.arange(h)
                x, y = np.meshgrid(x, y)
                
                heatmap = np.exp(-((x - center_x) ** 2 + (y - center_y) ** 2) / (2 * sigma ** 2))
                return (heatmap * 255).astype(np.uint8)
            
            else:
                return None
                
        except Exception as e:
            logger.warning(f"生成热力图失败: {e}")
            return None


@register_generator
class DefectMigrationGenerator(BaseGenerator):
    """
    缺陷迁移生成器
    
    基于 LAB 颜色空间匹配的缺陷迁移生成器
    支持多种颜色匹配模式和放置策略
    """
    
    _name = "defect_migration"
    _description = "基于 LAB 颜色空间匹配的缺陷迁移生成器（论文方法）"
    _is_builtin = True
    _supported_formats = ["yolo", "coco", "voc"]
    
    def __init__(self):
        super().__init__()
        self.color_matcher = ColorMatcher()
        self.defect_library: List[DefectRegion] = []
        self.base_images: List[np.ndarray] = []
    
    def get_name(self) -> str:
        return "defect_migration"
    
    def get_description(self) -> str:
        return "基于 LAB 颜色空间匹配的缺陷迁移生成器（论文方法）"
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_type": {
                    "type": "string",
                    "enum": ["dataset", "upload"],
                    "title": "缺陷源类型",
                    "default": "dataset",
                    "description": "缺陷来源类型：数据集或上传"
                },
                "source_dataset_id": {
                    "type": "string",
                    "title": "缺陷源数据集ID",
                    "description": "source_type=dataset 时必填"
                },
                "source_image_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "缺陷源图像路径列表",
                    "description": "source_type=upload 时必填"
                },
                "base_dataset_id": {
                    "type": "string",
                    "title": "基底数据集ID"
                },
                "base_image_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "基底图像路径列表",
                    "description": "不使用数据集时的替代方案"
                },
                "color_match_mode": {
                    "type": "string",
                    "enum": ["light", "standard", "strong", "custom"],
                    "title": "颜色匹配模式",
                    "default": "standard",
                    "description": "light: 轻度匹配, standard: 标准匹配, strong: 强匹配, custom: 自定义"
                },
                "color_match_params": {
                    "type": "object",
                    "title": "颜色匹配参数（custom 模式时有效）",
                    "properties": {
                        "invert_colors": {"type": "boolean", "default": False},
                        "brightness_adjust": {"type": "number", "minimum": 0, "maximum": 2, "default": 1.0},
                        "clip_limit": {"type": "number", "minimum": 1, "maximum": 10, "default": 2.0},
                        "tile_grid_size": {"type": "integer", "minimum": 4, "maximum": 16, "default": 8},
                        "contrast_factor": {"type": "number", "minimum": 1, "maximum": 2, "default": 1.5}
                    }
                },
                "placement_strategy": {
                    "type": "object",
                    "title": "放置策略",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["random", "region", "grid", "heatmap", "center", "edge"],
                            "default": "random"
                        },
                        "roi": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "感兴趣区域 [x, y, w, h]"
                        },
                        "heatmap_path": {"type": "string"},
                        "defects_per_image": {
                            "type": "object",
                            "properties": {
                                "min": {"type": "integer", "minimum": 1, "default": 1},
                                "max": {"type": "integer", "minimum": 1, "default": 3}
                            }
                        }
                    }
                },
                "defect_size": {
                    "type": "object",
                    "title": "缺陷尺寸控制",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["original", "random_scale", "fixed"],
                            "default": "original"
                        },
                        "scale_range": {
                            "type": "array",
                            "items": {"type": "number"},
                            "default": [0.5, 1.5]
                        },
                        "fixed_size": {
                            "type": "object",
                            "properties": {
                                "width": {"type": "integer"},
                                "height": {"type": "integer"}
                            }
                        }
                    }
                },
                "overlap_strategy": {
                    "type": "object",
                    "properties": {
                        "allow_overlap": {"type": "boolean", "default": False},
                        "max_overlap_ratio": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.3}
                    }
                },
                "fusion_params": {
                    "type": "object",
                    "title": "融合参数",
                    "properties": {
                        "blur_kernel": {"type": "integer", "minimum": 3, "maximum": 15, "default": 5},
                        "fusion_strength": {"type": "number", "minimum": 0.3, "maximum": 1.0, "default": 0.7}
                    }
                },
                "class_mapping": {
                    "type": "object",
                    "title": "类别映射",
                    "description": "源类别ID到目标类别ID的映射，例如 {\"0\": 0, \"1\": 1}"
                }
            },
            "required": ["base_dataset_id"]
        }
    
    def _on_configure(self, config: Dict[str, Any]) -> None:
        """配置后的初始化"""
        # 数据将在生成时按需加载
        self.defect_library = []
        self.base_images = []
        self._defect_dataset_id = config.get("source_dataset_id")
        self._base_dataset_id = config.get("base_dataset_id")
    
    def load_defect_library_sync(self, dataset_path: str, class_names: List[str] = None) -> int:
        """
        同步加载缺陷库（从数据集中提取缺陷区域）
        
        Args:
            dataset_path: 数据集路径
            class_names: 类别名称列表
            
        Returns:
            提取的缺陷数量
        """
        import glob
        
        self.defect_library = []
        dataset_path = Path(dataset_path)
        
        # 查找所有图像文件
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
        image_files = []
        for ext in image_extensions:
            image_files.extend(dataset_path.rglob(ext))
        
        logger.info(f"在数据集 {dataset_path} 中找到 {len(image_files)} 张图像")
        
        for img_path in image_files:
            # 查找对应的标注文件
            label_path = img_path.parent.parent / 'labels' / f"{img_path.stem}.txt"
            
            if not label_path.exists():
                continue
            
            try:
                # 读取图像
                image = cv2.imread(str(img_path))
                if image is None:
                    continue
                
                h, w = image.shape[:2]
                
                # 读取YOLO格式标注
                with open(label_path, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) < 5:
                            continue
                        
                        class_id = int(parts[0])
                        x_center = float(parts[1])
                        y_center = float(parts[2])
                        width = float(parts[3])
                        height = float(parts[4])
                        
                        # 转换为像素坐标
                        x1 = int((x_center - width / 2) * w)
                        y1 = int((y_center - height / 2) * h)
                        x2 = int((x_center + width / 2) * w)
                        y2 = int((y_center + height / 2) * h)
                        
                        # 确保坐标在图像范围内
                        x1 = max(0, x1)
                        y1 = max(0, y1)
                        x2 = min(w, x2)
                        y2 = min(h, y2)
                        
                        if x2 <= x1 or y2 <= y1:
                            continue
                        
                        # 提取缺陷区域
                        defect_img = image[y1:y2, x1:x2].copy()
                        
                        # 创建掩码（假设缺陷区域是矩形）
                        mask = np.ones((y2 - y1, x2 - x1), dtype=np.uint8) * 255
                        
                        # 添加到缺陷库
                        self.defect_library.append(DefectRegion(
                            image=defect_img,
                            mask=mask,
                            bbox=(x1, y1, x2 - x1, y2 - y1),
                            class_id=class_id,
                            class_name=class_names[class_id] if class_names and class_id < len(class_names) else str(class_id)
                        ))
                        
            except Exception as e:
                logger.warning(f"处理图像 {img_path} 失败: {e}")
                continue
        
        logger.info(f"从数据集提取了 {len(self.defect_library)} 个缺陷")
        return len(self.defect_library)
    
    def load_base_images_sync(self, dataset_path: str, max_images: int = 100) -> int:
        """
        同步加载基底图像
        
        Args:
            dataset_path: 数据集路径
            max_images: 最大加载图像数
            
        Returns:
            加载的图像数量
        """
        import glob
        
        self.base_images = []
        dataset_path = Path(dataset_path)
        
        logger.info(f"开始加载基底图像，路径: {dataset_path}, 存在: {dataset_path.exists()}")
        
        # 查找所有图像文件
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp']
        image_files = []
        for ext in image_extensions:
            found = list(dataset_path.rglob(ext))
            if found:
                logger.info(f"  找到 {len(found)} 个 {ext} 文件")
            image_files.extend(found)
        
        # 限制数量
        image_files = image_files[:max_images]
        
        logger.info(f"在基底数据集 {dataset_path} 中找到 {len(image_files)} 张图像")
        
        if len(image_files) == 0:
            # 列出目录内容帮助调试
            try:
                logger.info(f"目录内容: {list(dataset_path.iterdir())}")
            except Exception as e:
                logger.warning(f"无法列出目录内容: {e}")
        
        for img_path in image_files:
            try:
                image = cv2.imread(str(img_path))
                if image is not None:
                    self.base_images.append(image)
            except Exception as e:
                logger.warning(f"加载图像 {img_path} 失败: {e}")
                continue
        
        logger.info(f"加载了 {len(self.base_images)} 张基底图像")
        return len(self.base_images)
    
    def _get_color_match_params(self, mode: str) -> Dict[str, Any]:
        """获取颜色匹配参数"""
        presets = {
            "light": {
                "clip_limit": 1.0,
                "tile_grid_size": 8,
                "brightness_adjust": 1.0,
                "contrast_factor": 1.0
            },
            "standard": {
                "clip_limit": 2.0,
                "tile_grid_size": 8,
                "brightness_adjust": 1.0,
                "contrast_factor": 1.5
            },
            "strong": {
                "clip_limit": 4.0,
                "tile_grid_size": 8,
                "brightness_adjust": 1.2,
                "contrast_factor": 1.8
            }
        }
        
        if mode in presets:
            return presets[mode]
        elif mode == "custom":
            return self._config.get("color_match_params", presets["standard"])
        else:
            return presets["standard"]
    
    def generate_single(
        self,
        base_image: Optional[np.ndarray] = None,
        seed: Optional[int] = None,
        **kwargs
    ) -> GenerationResult:
        """
        生成单张图像
        
        Args:
            base_image: 基底图像（可选，不传则随机选择）
            seed: 随机种子
            
        Returns:
            GenerationResult
        """
        try:
            if seed is not None:
                np.random.seed(seed)
            
            # 获取基底图像
            if base_image is None:
                if not self.base_images:
                    raise GenerationError("没有可用的基底图像")
                base_image = self.base_images[np.random.randint(len(self.base_images))]
            
            # 确保图像格式正确
            if len(base_image.shape) == 2:
                base_image = cv2.cvtColor(base_image, cv2.COLOR_GRAY2BGR)
            elif base_image.shape[2] == 4:
                base_image = cv2.cvtColor(base_image, cv2.COLOR_RGBA2BGR)
            
            base_h, base_w = base_image.shape[:2]
            result_image = base_image.copy()
            
            # 获取配置
            placement_config = self._config.get("placement_strategy", {})
            color_mode = self._config.get("color_match_mode", "standard")
            fusion_params = self._config.get("fusion_params", {})
            defect_size_config = self._config.get("defect_size", {})
            overlap_config = self._config.get("overlap_strategy", {})
            
            # 确定缺陷数量
            defects_per_image = placement_config.get("defects_per_image", {"min": 1, "max": 3})
            num_defects = np.random.randint(
                defects_per_image.get("min", 1),
                defects_per_image.get("max", 3) + 1
            )
            
            if not self.defect_library:
                raise GenerationError("缺陷库为空")
            
            # 选择缺陷
            selected_defects = np.random.choice(
                self.defect_library,
                size=min(num_defects, len(self.defect_library)),
                replace=False
            )
            
            # 初始化放置策略
            strategy = PlacementStrategy(
                strategy_type=placement_config.get("type", "random"),
                image_shape=(base_h, base_w),
                roi=tuple(placement_config["roi"]) if "roi" in placement_config else None,
                grid_config=placement_config.get("grid"),
                heatmap_config=placement_config.get("heatmap"),
                allow_overlap=overlap_config.get("allow_overlap", False),
                max_overlap_ratio=overlap_config.get("max_overlap_ratio", 0.3)
            )
            
            # 获取颜色匹配参数
            match_params = self._get_color_match_params(color_mode)
            
            # 融合参数
            blur_kernel = fusion_params.get("blur_kernel", 5)
            fusion_strength = fusion_params.get("fusion_strength", 0.7)
            
            # 生成标注
            boxes = []
            labels = []
            quality_scores = []
            
            for defect in selected_defects:
                # 调整缺陷尺寸
                defect_img, defect_mask = self._resize_defect(
                    defect, defect_size_config, base_w, base_h
                )
                
                defect_h, defect_w = defect_img.shape[:2]
                
                # 获取放置位置
                placement = strategy.get_placement(defect_w, defect_h)
                
                if not placement.success:
                    logger.warning(f"放置失败: {placement.error_message}")
                    continue
                
                x, y = placement.position
                
                # 提取目标区域
                target_region = result_image[y:y+defect_h, x:x+defect_w]
                
                # 颜色匹配
                matched_defect = self.color_matcher.lab_match(
                    defect_img,
                    target_region,
                    **match_params
                )
                
                # 融合
                fused_region = self._fuse_defect(
                    target_region,
                    matched_defect,
                    defect_mask,
                    blur_kernel,
                    fusion_strength
                )
                
                result_image[y:y+defect_h, x:x+defect_w] = fused_region
                
                # 记录标注
                boxes.append([
                    x / base_w,
                    y / base_h,
                    (x + defect_w) / base_w,
                    (y + defect_h) / base_h
                ])
                labels.append(defect.class_id)
                
                # 计算质量分数（基于边缘平滑度）
                quality_score = self._compute_quality_score(target_region, fused_region, defect_mask)
                quality_scores.append(quality_score)
            
            # 转换为 RGB
            result_image_rgb = cv2.cvtColor(result_image, cv2.COLOR_BGR2RGB)
            
            return GenerationResult(
                image=result_image_rgb,
                annotations={
                    "boxes": boxes,
                    "labels": labels,
                    "scores": [1.0] * len(boxes)
                },
                success=True,
                metadata={
                    "num_defects": len(boxes),
                    "color_match_mode": color_mode,
                    "placement_strategy": placement_config.get("type", "random"),
                    "fusion_quality_scores": quality_scores,
                    "average_quality": np.mean(quality_scores) if quality_scores else 0
                },
                quality_score=np.mean(quality_scores) if quality_scores else 0
            )
            
        except Exception as e:
            logger.error(f"生成失败: {e}")
            return GenerationResult(
                success=False,
                error_message=str(e)
            )
    
    def _resize_defect(
        self,
        defect: DefectRegion,
        size_config: Dict[str, Any],
        base_w: int,
        base_h: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """调整缺陷尺寸"""
        mode = size_config.get("mode", "original")
        defect_img = defect.image.copy()
        defect_mask = defect.mask.copy()
        
        if mode == "random_scale":
            scale_range = size_config.get("scale_range", [0.5, 1.5])
            scale = np.random.uniform(scale_range[0], scale_range[1])
            new_w = int(defect_img.shape[1] * scale)
            new_h = int(defect_img.shape[0] * scale)
            defect_img = cv2.resize(defect_img, (new_w, new_h))
            defect_mask = cv2.resize(defect_mask, (new_w, new_h))
        
        elif mode == "fixed":
            fixed_size = size_config.get("fixed_size", {})
            new_w = fixed_size.get("width", defect_img.shape[1])
            new_h = fixed_size.get("height", defect_img.shape[0])
            defect_img = cv2.resize(defect_img, (new_w, new_h))
            defect_mask = cv2.resize(defect_mask, (new_w, new_h))
        
        return defect_img, defect_mask
    
    def _fuse_defect(
        self,
        background: np.ndarray,
        defect: np.ndarray,
        mask: np.ndarray,
        blur_kernel: int,
        strength: float
    ) -> np.ndarray:
        """
        融合缺陷到背景
        
        Args:
            background: 背景区域
            defect: 缺陷图像
            mask: 缺陷掩码
            blur_kernel: 高斯模糊核大小
            strength: 融合强度
            
        Returns:
            融合后的区域
        """
        # 确保尺寸匹配
        h, w = background.shape[:2]
        defect = cv2.resize(defect, (w, h))
        mask = cv2.resize(mask, (w, h))
        
        # 归一化掩码
        mask_norm = mask.astype(np.float32) / 255.0
        
        # 边缘模糊
        if blur_kernel > 1:
            mask_blurred = cv2.GaussianBlur(mask_norm, (blur_kernel, blur_kernel), 0)
        else:
            mask_blurred = mask_norm
        
        # 调整融合强度
        mask_blurred = mask_blurred * strength
        
        # 融合
        mask_3ch = np.stack([mask_blurred] * 3, axis=2)
        result = (defect.astype(np.float32) * mask_3ch + 
                  background.astype(np.float32) * (1 - mask_3ch))
        
        return result.astype(np.uint8)
    
    def _compute_quality_score(
        self,
        original: np.ndarray,
        fused: np.ndarray,
        mask: np.ndarray
    ) -> float:
        """
        计算融合质量分数
        
        基于边缘平滑度和颜色一致性
        """
        try:
            # 调整尺寸
            h, w = original.shape[:2]
            mask = cv2.resize(mask, (w, h))
            
            # 提取掩码边缘
            kernel = np.ones((3, 3), np.uint8)
            mask_dilated = cv2.dilate(mask, kernel, iterations=1)
            mask_eroded = cv2.erode(mask, kernel, iterations=1)
            edge_mask = mask_dilated - mask_eroded
            
            if edge_mask.sum() == 0:
                return 1.0
            
            # 计算边缘梯度差异
            gray_original = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
            gray_fused = cv2.cvtColor(fused, cv2.COLOR_BGR2GRAY)
            
            sobel_orig = cv2.Sobel(gray_original, cv2.CV_64F, 1, 1, ksize=3)
            sobel_fused = cv2.Sobel(gray_fused, cv2.CV_64F, 1, 1, ksize=3)
            
            # 边缘区域梯度差异
            edge_diff = np.abs(sobel_orig - sobel_fused) * (edge_mask > 0)
            
            # 计算分数（差异越小越好）
            max_diff = 255 * 2  # Sobel 最大可能差异
            mean_diff = edge_diff.sum() / (edge_mask.sum() + 1e-6)
            score = 1.0 - (mean_diff / max_diff)
            
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.warning(f"计算质量分数失败: {e}")
            return 0.5
    
    def estimate_time(self, count: int) -> float:
        """估算生成时间"""
        # 基于经验：每张图像约 0.5-2 秒
        avg_time = 1.0
        return count * avg_time
