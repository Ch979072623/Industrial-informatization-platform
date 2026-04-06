"""
数据集统计服务模块

提供数据集统计分析功能，包括：
- 扫描labels文件并计算统计数据
- 自动检测labels变化并更新统计
- 生成图表数据

示例用法:
    >>> from app.services.dataset_statistics_service import DatasetStatisticsService
    >>> service = DatasetStatisticsService(db_session)
    >>> stats = await service.analyze_and_save(dataset_id)
    >>> # 或获取现有统计（如果不存在则自动分析）
    >>> stats = await service.get_or_create_statistics(dataset_id)
"""

import os
import hashlib
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.dataset import Dataset, DatasetImage
from app.models.dataset_statistics import DatasetStatistics
from app.utils.dataset_parser import YOLOParser, COCOParser, VOCParser, DatasetFormat

# 配置日志
logger = logging.getLogger(__name__)


class DatasetStatisticsError(Exception):
    """数据集统计错误基类"""
    pass


class DatasetNotFoundError(DatasetStatisticsError):
    """数据集不存在错误"""
    pass


class DatasetAnalysisError(DatasetStatisticsError):
    """数据集分析错误"""
    pass


class DatasetStatisticsService:
    """
    数据集统计服务类
    
    提供完整的数据集统计功能，包括扫描labels、计算统计数据、保存到数据库等。
    """
    
    # 目标大小阈值（像素）
    SMALL_BBOX_THRESHOLD = 32 * 32  # 小目标: < 32x32
    MEDIUM_BBOX_THRESHOLD = 96 * 96  # 中目标: 32x32 ~ 96x96
    
    def __init__(self, db: AsyncSession):
        """
        初始化统计服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def get_or_create_statistics(
        self, 
        dataset_id: str, 
        force_refresh: bool = False
    ) -> DatasetStatistics:
        """
        获取或创建数据集统计信息
        
        如果统计信息不存在或已过期，自动进行分析并保存。
        
        Args:
            dataset_id: 数据集ID
            force_refresh: 是否强制重新分析
            
        Returns:
            DatasetStatistics对象
            
        Raises:
            DatasetNotFoundError: 数据集不存在
            DatasetAnalysisError: 分析过程中出错
        """
        # 获取数据集
        dataset = await self._get_dataset(dataset_id)
        if not dataset:
            raise DatasetNotFoundError(f"数据集不存在: {dataset_id}")
        
        # 检查现有统计
        existing_stats = await self._get_existing_statistics(dataset_id)
        
        if existing_stats and not force_refresh:
            # 检查 split_distribution 是否完整（包含 train/val/test）
            split_dist = existing_stats.split_distribution or {}
            has_train = split_dist.get("train", 0) > 0
            has_val = split_dist.get("val", 0) > 0
            has_test = split_dist.get("test", 0) > 0
            
            # 如果只有 val 而没有 train 和 test，说明数据损坏，需要重新分析
            if has_val and not has_train and not has_test:
                logger.warning(f"数据集 {dataset_id} split_distribution 数据损坏: {split_dist}，将重新分析")
                force_refresh = True
            elif existing_stats.scan_status == "completed" and not existing_stats.labels_hash:
                # 如果统计状态是 completed 且 labels_hash 为空（划分的数据集），直接返回
                logger.info(f"数据集 {dataset_id} 是划分数据集，统计信息已完成，无需更新")
                return existing_stats
            
            if not force_refresh:
                # 检查是否需要更新（labels文件是否变化）
                current_hash = await self._calculate_labels_hash(dataset.path, dataset.format)
                if existing_stats.labels_hash == current_hash and not existing_stats.is_stale():
                    logger.info(f"数据集 {dataset_id} 统计信息已是最新，无需更新")
                    return existing_stats
        
        # 执行分析
        return await self.analyze_and_save(dataset_id)
    
    async def analyze_and_save(self, dataset_id: str) -> DatasetStatistics:
        """
        分析数据集并保存统计信息
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            保存后的DatasetStatistics对象
            
        Raises:
            DatasetNotFoundError: 数据集不存在
            DatasetAnalysisError: 分析失败
        """
        # 获取数据集
        dataset = await self._get_dataset(dataset_id)
        if not dataset:
            raise DatasetNotFoundError(f"数据集不存在: {dataset_id}")
        
        logger.info(f"开始分析数据集 {dataset_id}: {dataset.name}")
        
        try:
            # 扫描labels文件
            analysis_result = await self._scan_labels(dataset)
            logger.info(f"_scan_labels 返回: class_names={analysis_result.get('class_names', [])}")
            
            # 计算统计数据
            statistics_data = self._calculate_statistics(analysis_result)
            logger.info(f"_calculate_statistics 返回: class_names={statistics_data.get('class_names', [])}")
            
            # 计算labels文件哈希
            labels_hash = await self._calculate_labels_hash(dataset.path, dataset.format)
            statistics_data["labels_hash"] = labels_hash
            
            # 保存到数据库
            stats = await self._save_statistics(dataset_id, statistics_data)
            
            logger.info(f"数据集 {dataset_id} 分析完成，共 {stats.total_images} 张图像，{stats.total_annotations} 个标注")
            return stats
            
        except Exception as e:
            logger.error(f"分析数据集 {dataset_id} 失败: {str(e)}")
            # 保存错误状态
            await self._save_error_status(dataset_id, str(e))
            raise DatasetAnalysisError(f"分析失败: {str(e)}")
    
    async def get_statistics(self, dataset_id: str) -> Optional[DatasetStatistics]:
        """
        获取数据集统计信息（不自动创建）
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            DatasetStatistics对象，不存在返回None
        """
        return await self._get_existing_statistics(dataset_id)
    
    async def delete_statistics(self, dataset_id: str) -> bool:
        """
        删除数据集统计信息
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            是否成功删除
        """
        stats = await self._get_existing_statistics(dataset_id)
        if stats:
            await self.db.delete(stats)
            await self.db.commit()
            logger.info(f"已删除数据集 {dataset_id} 的统计信息")
            return True
        return False
    
    async def get_chart_data(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """
        获取图表展示数据
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            图表数据字典，不存在返回None
        """
        stats = await self.get_or_create_statistics(dataset_id)
        if stats:
            return stats.to_chart_data()
        return None
    
    async def _get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """
        获取数据集信息
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            Dataset对象或None
        """
        result = await self.db.execute(
            select(Dataset).where(Dataset.id == dataset_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_existing_statistics(self, dataset_id: str) -> Optional[DatasetStatistics]:
        """
        获取现有的统计信息
        
        Args:
            dataset_id: 数据集ID
            
        Returns:
            DatasetStatistics对象或None
        """
        result = await self.db.execute(
            select(DatasetStatistics).where(DatasetStatistics.dataset_id == dataset_id)
        )
        return result.scalar_one_or_none()
    
    async def _scan_labels(self, dataset: Dataset) -> Dict[str, Any]:
        """
        扫描数据集labels文件
        
        支持多种目录结构，包括标准YOLO格式和扁平结构。
        
        Args:
            dataset: 数据集对象
            
        Returns:
            分析结果字典
        """
        import os
        from PIL import Image as PILImage
        
        dataset_path = dataset.path
        format_type = dataset.format.lower()
        
        logger.info(f"扫描数据集路径: {dataset_path}, 格式: {format_type}")
        
        # 检查路径是否存在
        path_obj = Path(dataset_path)
        if not path_obj.exists():
            logger.error(f"数据集路径不存在: {dataset_path}")
            return self._empty_analysis(dataset.class_names)
        
        try:
            # 首先尝试使用 DatasetAnalyzer
            from app.utils.dataset_parser import DatasetAnalyzer
            analyzer = DatasetAnalyzer(dataset_path, format_type)
            label_analysis = analyzer.analyze_labels()
            logger.info(f"DatasetAnalyzer analyze_labels 返回: class_names={label_analysis.get('class_names', [])}, annotations_per_class keys={list(label_analysis.get('annotations_per_class', {}).keys())}")
            
            preview_images = analyzer.get_preview_images(10000)  # 获取大量图像
            
            # 强制从YAML重新读取类别名称，确保正确性
            yaml_class_names = self._load_yaml_class_names(path_obj)
            logger.info(f"_load_yaml_class_names 返回: {yaml_class_names}")
            if yaml_class_names:
                logger.info(f"从YAML强制读取类别名称: {yaml_class_names}")
                label_analysis["class_names"] = yaml_class_names
            
            if len(preview_images) > 0:
                logger.info(f"DatasetAnalyzer 找到 {len(preview_images)} 张图像, class_names={label_analysis.get('class_names', [])}")
                result = self._build_analysis_from_preview(preview_images, label_analysis)
                logger.info(f"_build_analysis_from_preview 返回: class_names={result.get('class_names', [])}")
                return result
            
            # 如果 DatasetAnalyzer 没有找到图像，使用手动扫描
            logger.info("DatasetAnalyzer 未找到图像，使用手动扫描...")
            return await self._manual_scan(path_obj, dataset.class_names)
            
        except Exception as e:
            logger.error(f"扫描数据集失败: {e}", exc_info=True)
            return self._empty_analysis(dataset.class_names)
    
    def _load_yaml_class_names(self, path_obj: Path) -> List[str]:
        """
        直接从YAML文件读取类别名称
        
        支持多种YAML文件名和位置（根目录或子目录）
        自动修复YAML中因换行导致的类别名称断裂问题（如 'pitted_sur face' -> 'pitted_surface'）
        """
        yaml_names = ["data.yaml", "dataset.yaml", "config.yaml"]
        
        def _fix_broken_class_names(names: List[str]) -> List[str]:
            """修复因YAML换行导致的类别名称断裂"""
            fixed = []
            for name in names:
                # 如果类别名称包含空格，尝试合并（可能是换行导致的）
                if ' ' in name:
                    fixed_name = name.replace(' ', '')
                    logger.info(f"修复类别名称: '{name}' -> '{fixed_name}'")
                    fixed.append(fixed_name)
                else:
                    fixed.append(name)
            return fixed
        
        # 首先在根目录查找
        for yaml_name in yaml_names:
            yaml_file = path_obj / yaml_name
            if yaml_file.exists():
                try:
                    import yaml
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    if config and 'names' in config:
                        names = config['names']
                        if isinstance(names, dict):
                            class_names = [names[i] for i in sorted(names.keys())]
                            return _fix_broken_class_names(class_names)
                        elif isinstance(names, list):
                            return _fix_broken_class_names(names)
                except Exception as e:
                    logger.warning(f"解析{yaml_file}失败: {e}")
        
        # 在第一层子目录中查找
        try:
            for subdir in path_obj.iterdir():
                if subdir.is_dir():
                    for yaml_name in yaml_names:
                        yaml_file = subdir / yaml_name
                        if yaml_file.exists():
                            try:
                                import yaml
                                with open(yaml_file, 'r', encoding='utf-8') as f:
                                    config = yaml.safe_load(f)
                                if config and 'names' in config:
                                    names = config['names']
                                    if isinstance(names, dict):
                                        class_names = [names[i] for i in sorted(names.keys())]
                                        return _fix_broken_class_names(class_names)
                                    elif isinstance(names, list):
                                        return _fix_broken_class_names(names)
                            except Exception as e:
                                logger.warning(f"解析{yaml_file}失败: {e}")
        except Exception as e:
            logger.warning(f"扫描子目录查找YAML失败: {e}")
        
        return []
    
    def _empty_analysis(self, class_names: list) -> Dict[str, Any]:
        """返回空的分析结果"""
        return {
            "images": [],
            "class_names": class_names or [],
            "class_distribution": {},
            "split_distribution": {},
        }
    
    def _build_analysis_from_preview(
        self, 
        preview_images: List[Dict], 
        label_analysis: Dict
    ) -> Dict[str, Any]:
        """从预览图像构建分析结果"""
        from dataclasses import dataclass, field
        
        @dataclass
        class SimpleImage:
            id: str
            filename: str
            filepath: str
            width: int
            height: int
            bboxes: list = field(default_factory=list)
            split: str = "train"
            
            @property
            def has_annotations(self):
                return len(self.bboxes) > 0
        
        images = []
        for img_info in preview_images:
            bboxes = []
            for bbox_info in img_info.get("bboxes", []):
                from app.utils.dataset_parser import BBox
                bboxes.append(BBox(
                    x=bbox_info.get("x", 0),
                    y=bbox_info.get("y", 0),
                    width=bbox_info.get("width", 0),
                    height=bbox_info.get("height", 0),
                    class_id=bbox_info.get("class_id", 0),
                    class_name=bbox_info.get("class_name")
                ))
            
            # 从文件路径推断 split（对于划分后的数据集）
            filepath = img_info.get("filepath", "")
            inferred_split = img_info.get("split", "train")
            
            # 如果 split 是默认值，尝试从路径推断
            if inferred_split == "train" and filepath:
                path_lower = filepath.lower()
                if "/val/" in path_lower or "\\val\\" in path_lower:
                    inferred_split = "val"
                elif "/test/" in path_lower or "\\test\\" in path_lower:
                    inferred_split = "test"
                elif "/train/" in path_lower or "\\train\\" in path_lower:
                    inferred_split = "train"
            
            img = SimpleImage(
                id=img_info.get("id", ""),
                filename=img_info.get("filename", ""),
                filepath=filepath,
                width=img_info.get("width", 0),
                height=img_info.get("height", 0),
                bboxes=bboxes,
                split=inferred_split
            )
            images.append(img)
        
        # 获取类别名称（已经从YAML读取并修复）
        class_names = label_analysis.get("class_names", [])
        
        # 再次确保类别名称已修复
        if class_names:
            fixed_names = []
            for name in class_names:
                if ' ' in name:
                    fixed_name = name.replace(' ', '')
                    logger.info(f"_build_analysis_from_preview 修复类别名称: '{name}' -> '{fixed_name}'")
                    fixed_names.append(fixed_name)
                else:
                    fixed_names.append(name)
            class_names = fixed_names
        
        # 构建划分分布
        split_distribution = {}
        for img in images:
            split = img.split if img.split in ["train", "val", "test"] else "train"
            split_distribution[split] = split_distribution.get(split, 0) + 1
        
        logger.info(f"_build_analysis_from_preview: split_distribution={split_distribution}, class_names={class_names}")
        
        return {
            "images": images,
            "class_names": class_names,
            "class_distribution": label_analysis.get("annotations_per_class", {}),
            "split_distribution": split_distribution,
        }
    
    async def _manual_scan(self, path_obj: Path, class_names: list) -> Dict[str, Any]:
        """
        手动扫描目录查找图像和标签
        
        支持灵活的目录结构。
        会自动从YAML文件读取类别名称（如果提供的是默认class_开头的名称）。
        """
        from dataclasses import dataclass, field
        from PIL import Image as PILImage
        
        @dataclass
        class SimpleImage:
            id: str
            filename: str
            filepath: str
            width: int
            height: int
            bboxes: list = field(default_factory=list)
            split: str = "train"
            
            @property
            def has_annotations(self):
                return len(self.bboxes) > 0
        
        # 如果传入的是默认类别名称或空，尝试从YAML读取
        original_class_names = class_names
        if not class_names or all(name.startswith('class_') for name in class_names):
            yaml_class_names = self._load_yaml_class_names(path_obj)
            if yaml_class_names:
                logger.info(f"_manual_scan 从YAML读取类别名称: {yaml_class_names}，替换传入的: {original_class_names}")
                class_names = yaml_class_names
            else:
                logger.warning(f"_manual_scan 未从YAML读取到类别名称，使用传入的: {class_names}")
        else:
            logger.info(f"_manual_scan 使用传入的类别名称（非默认）: {class_names}")
        
        images = []
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        
        # 递归查找所有图像文件
        debug_count = 0
        for img_file in path_obj.rglob("*"):
            if not img_file.is_file():
                continue
            
            if img_file.suffix.lower() not in image_extensions:
                continue
            
            # 调试：打印前5个图像的路径
            debug_count += 1
            if debug_count <= 5:
                logger.info(f"_manual_scan 图像路径: {img_file}, parts: {img_file.parts}")
            
            try:
                # 获取图像尺寸
                with PILImage.open(img_file) as pil_img:
                    width, height = pil_img.size
                
                # 尝试查找对应的标签文件
                bboxes = []
                
                # 构建标签文件路径 - 基于图像路径推断
                # 图像通常在: path/to/images/train/image.jpg
                # 标签通常在: path/to/labels/train/image.txt
                # 或者:       path/to/train/labels/image.txt (如 neu/train/labels/)
                
                possible_label_paths = []
                img_path = img_file
                img_parent = img_file.parent  # 例如: .../train
                img_grandparent = img_file.parent.parent  # 例如: .../images
                
                # 1. 标准YOLO结构: 同级的 labels 目录
                # 图像: dataset/images/train/img.jpg -> 标签: dataset/labels/train/img.txt
                possible_label_paths.append(
                    img_grandparent.parent / "labels" / img_parent.name / img_file.with_suffix(".txt").name
                )
                
                # 2. 如果图像在 xxx/images/train/ 下，标签在 xxx/labels/train/
                if img_grandparent.name == "images":
                    possible_label_paths.append(
                        img_grandparent.parent / "labels" / img_parent.name / img_file.with_suffix(".txt").name
                    )
                
                # 3. 如果图像在 neu/train/images/ 下，标签在 neu/train/labels/
                # 检查是否存在同级的 labels 目录
                sibling_labels = img_parent / "labels"
                if sibling_labels.exists():
                    possible_label_paths.append(
                        sibling_labels / img_file.with_suffix(".txt").name
                    )
                
                # 4. 图像在子目录，标签在父目录的 labels 下
                possible_label_paths.append(
                    img_grandparent / "labels" / img_file.with_suffix(".txt").name
                )
                
                # 5. 同目录下的标签（扩展名改为 .txt）
                possible_label_paths.append(img_file.with_suffix(".txt"))
                
                # 6. 对于 neu/train/images/xxx.jpg -> neu/train/labels/xxx.txt 结构
                if "images" in img_file.parts:
                    # 找到 images 在路径中的位置，替换为 labels
                    parts = list(img_file.parts)
                    for i, part in enumerate(parts):
                        if part == "images":
                            parts[i] = "labels"
                            new_path = Path(*parts).with_suffix(".txt")
                            possible_label_paths.append(new_path)
                            break
                
                label_file = None
                for label_path in possible_label_paths:
                    if label_path.exists():
                        label_file = label_path
                        break
                
                # 如果找到标签文件，解析它
                if label_file:
                    bboxes = self._parse_yolo_label_file(label_file, width, height, class_names)
                
                # 确定 split（根据路径推断）
                # 只检查路径中的目录名，不包含文件名部分
                split = "train"
                # 获取文件的父目录路径（去掉文件名）
                path_parts = img_file.parts
                # 检查路径中的每个目录名
                for part in path_parts:
                    part_lower = part.lower()
                    if part_lower == "test":
                        split = "test"
                        break
                    elif part_lower in ("val", "valid"):
                        split = "val"
                        break
                    elif part_lower == "train":
                        split = "train"
                        break
                
                # 调试前5个图像
                if len(images) < 5:
                    logger.info(f"_manual_scan split推断: path={img_file}, parts={path_parts}, split={split}")
                
                img = SimpleImage(
                    id=img_file.stem,
                    filename=img_file.name,
                    filepath=str(img_file),
                    width=width,
                    height=height,
                    bboxes=bboxes,
                    split=split
                )
                images.append(img)
                
            except Exception as e:
                logger.warning(f"处理图像 {img_file} 失败: {e}")
                continue
        
        # 统计有标注的图像数量
        images_with_annotations = sum(1 for img in images if len(img.bboxes) > 0)
        total_annotations = sum(len(img.bboxes) for img in images)
        
        logger.info(f"手动扫描找到 {len(images)} 张图像，"
                   f"{images_with_annotations} 张有标注，"
                   f"共 {total_annotations} 个标注框")
        
        # 如果没有找到标注，记录调试信息
        if total_annotations == 0 and len(images) > 0:
            logger.warning(f"未找到任何标注框！请检查 labels 目录是否存在，以及标签文件格式是否正确。")
            
            # 列出数据集根目录内容
            try:
                all_items = list(path_obj.iterdir())
                dirs = [p.name for p in all_items if p.is_dir()]
                files = [p.name for p in all_items if p.is_file()]
                logger.info(f"数据集根目录内容 - 文件夹: {dirs}, 文件: {files}")
            except Exception as e:
                logger.warning(f"无法列出根目录内容: {e}")
        
        # 计算类别分布
        class_distribution = {}
        for img in images:
            for bbox in img.bboxes:
                class_name = bbox.class_name or f"class_{bbox.class_id}"
                class_distribution[class_name] = class_distribution.get(class_name, 0) + 1
        
        # 计算划分分布（尝试从文件路径推断 split）
        split_distribution = {}
        for img in images:
            split = img.split if img.split in ["train", "val", "test"] else "train"
            
            # 如果 split 是默认值，尝试从路径推断
            if split == "train" and img.filepath:
                path_lower = img.filepath.lower()
                if "/val/" in path_lower or "\\val\\" in path_lower:
                    split = "val"
                elif "/test/" in path_lower or "\\test\\" in path_lower:
                    split = "test"
                elif "/train/" in path_lower or "\\train\\" in path_lower:
                    split = "train"
            
            split_distribution[split] = split_distribution.get(split, 0) + 1
        
        logger.info(f"_manual_scan: split_distribution={split_distribution}")
        
        # 如果没有提供类别名称，从发现的类别生成
        if not class_names and class_distribution:
            class_names = sorted(class_distribution.keys())
        
        # 修复类别名称
        if class_names:
            fixed_names = []
            for name in class_names:
                if ' ' in name:
                    fixed_name = name.replace(' ', '')
                    logger.info(f"_manual_scan 修复类别名称: '{name}' -> '{fixed_name}'")
                    fixed_names.append(fixed_name)
                else:
                    fixed_names.append(name)
            class_names = fixed_names
        
        return {
            "images": images,
            "class_names": class_names or [],
            "class_distribution": class_distribution,
            "split_distribution": split_distribution,
        }
    
    def _parse_yolo_label_file(
        self, 
        label_file: Path, 
        img_width: int, 
        img_height: int,
        class_names: list
    ) -> list:
        """解析YOLO格式标签文件"""
        from app.utils.dataset_parser import BBox
        
        bboxes = []
        try:
            with open(label_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line:
                    continue
                
                parts = line.split()
                if len(parts) < 5:
                    logger.debug(f"标签文件 {label_file} 第 {line_num} 行格式错误: {line}")
                    continue
                
                try:
                    class_id = int(parts[0])
                    x_center_norm = float(parts[1])
                    y_center_norm = float(parts[2])
                    width_norm = float(parts[3])
                    height_norm = float(parts[4])
                    
                    # 转换为像素坐标
                    x_center = x_center_norm * img_width
                    y_center = y_center_norm * img_height
                    bbox_width = width_norm * img_width
                    bbox_height = height_norm * img_height
                    
                    # 转换为左上角坐标
                    x = x_center - bbox_width / 2
                    y = y_center - bbox_height / 2
                    
                    class_name = None
                    if class_id < len(class_names):
                        class_name = class_names[class_id]
                    
                    bboxes.append(BBox(
                        x=x, y=y,
                        width=bbox_width,
                        height=bbox_height,
                        class_id=class_id,
                        class_name=class_name
                    ))
                except (ValueError, IndexError) as e:
                    logger.debug(f"解析标签文件 {label_file} 第 {line_num} 行失败: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"解析标签文件 {label_file} 失败: {e}")
        
        return bboxes
    
    def _calculate_statistics(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算统计数据
        
        Args:
            analysis: 分析结果
            
        Returns:
            统计数据字典
        """
        from dataclasses import asdict
        
        images = analysis.get("images", [])
        class_names = analysis.get("class_names", [])
        class_distribution = analysis.get("class_distribution", {})
        split_distribution = analysis.get("split_distribution", {})
        
        logger.info(f"_calculate_statistics 输入: class_names={class_names}, class_distribution keys={list(class_distribution.keys())}")
        
        total_images = len(images)
        total_annotations = sum(len(img.bboxes) for img in images)
        
        # 图像统计
        images_with_annotations = sum(1 for img in images if img.has_annotations)
        images_without_annotations = total_images - images_with_annotations
        avg_annotations_per_image = total_annotations / total_images if total_images > 0 else 0
        
        # 如果有YAML中的类别名称，重新计算class_distribution
        if class_names:
            # 使用class_id统计，然后映射到类别名称
            class_id_distribution: Dict[int, int] = {}
            for img in images:
                for bbox in img.bboxes:
                    class_id_distribution[bbox.class_id] = class_id_distribution.get(bbox.class_id, 0) + 1
            
            # 映射到类别名称
            class_distribution = {}
            for class_id, count in class_id_distribution.items():
                if class_id < len(class_names):
                    class_name = class_names[class_id]
                else:
                    class_name = f"class_{class_id}"
                class_distribution[class_name] = count
            
            logger.info(f"使用YAML类别名称重新计算分布: {class_distribution}")
        
        # 类别统计
        class_count = len(class_names) if class_names else len(class_distribution)
        
        # 构建类别分布列表
        class_dist_list = []
        total_class_annotations = sum(class_distribution.values()) if class_distribution else 0
        
        for class_name, count in class_distribution.items():
            percentage = (count / total_class_annotations * 100) if total_class_annotations > 0 else 0
            class_dist_list.append({
                "class_name": class_name,
                "count": count,
                "percentage": round(percentage, 2)
            })
        
        # 按数量降序排序
        class_dist_list.sort(key=lambda x: x["count"], reverse=True)
        
        # 图像尺寸统计
        image_sizes = []
        size_map = {}
        total_width = 0
        total_height = 0
        
        for img in images:
            # 跳过无效的图像尺寸
            if img.width <= 0 or img.height <= 0:
                logger.warning(f"图像 {img.filename} 有无效尺寸: {img.width}x{img.height}")
                continue
                
            size_key = f"{img.width}x{img.height}"
            if size_key in size_map:
                size_map[size_key]["count"] += 1
            else:
                size_map[size_key] = {
                    "width": img.width,
                    "height": img.height,
                    "count": 1
                }
                image_sizes.append(size_map[size_key])
            
            total_width += img.width
            total_height += img.height
        
        logger.info(f"图像尺寸统计: 收集了 {len(image_sizes)} 种不同尺寸，"
                   f"示例: {image_sizes[:3] if image_sizes else 'N/A'}")
        
        avg_image_width = total_width / total_images if total_images > 0 else 0
        avg_image_height = total_height / total_images if total_images > 0 else 0
        
        # 标注框统计
        bbox_stats = self._calculate_bbox_statistics(images)
        
        return {
            "total_images": total_images,
            "total_annotations": total_annotations,
            "images_with_annotations": images_with_annotations,
            "images_without_annotations": images_without_annotations,
            "avg_annotations_per_image": avg_annotations_per_image,
            "class_count": class_count,
            "class_names": class_names,  # 添加类别名称列表
            "class_distribution": class_dist_list,
            "annotations_per_class": class_distribution,
            "image_sizes": image_sizes,
            "avg_image_width": avg_image_width,
            "avg_image_height": avg_image_height,
            "split_distribution": split_distribution,
            **bbox_stats,
            "scan_status": "completed",
            "last_scan_time": datetime.now(timezone.utc),
            "scan_error": None,
        }
    
    def _calculate_bbox_statistics(self, images: List[Any]) -> Dict[str, Any]:
        """
        计算标注框统计数据
        
        Args:
            images: 图像列表
            
        Returns:
            标注框统计数据
        """
        total_bbox_width = 0
        total_bbox_height = 0
        total_aspect_ratio = 0
        bbox_count = 0
        
        small_bboxes = 0
        medium_bboxes = 0
        large_bboxes = 0
        
        for img in images:
            for bbox in img.bboxes:
                width = bbox.width
                height = bbox.height
                area = width * height
                
                total_bbox_width += width
                total_bbox_height += height
                
                # 宽高比
                aspect_ratio = width / height if height > 0 else 1
                total_aspect_ratio += aspect_ratio
                
                bbox_count += 1
                
                # 目标大小分类
                if area < self.SMALL_BBOX_THRESHOLD:
                    small_bboxes += 1
                elif area < self.MEDIUM_BBOX_THRESHOLD:
                    medium_bboxes += 1
                else:
                    large_bboxes += 1
        
        avg_bbox_width = total_bbox_width / bbox_count if bbox_count > 0 else 0
        avg_bbox_height = total_bbox_height / bbox_count if bbox_count > 0 else 0
        avg_bbox_aspect_ratio = total_aspect_ratio / bbox_count if bbox_count > 0 else 1
        
        return {
            "avg_bbox_width": avg_bbox_width,
            "avg_bbox_height": avg_bbox_height,
            "avg_bbox_aspect_ratio": avg_bbox_aspect_ratio,
            "small_bboxes": small_bboxes,
            "medium_bboxes": medium_bboxes,
            "large_bboxes": large_bboxes,
        }
    
    async def _calculate_labels_hash(self, dataset_path: str, format_type: str) -> str:
        """
        计算labels文件的哈希值
        
        用于检测labels文件是否发生变化。
        
        Args:
            dataset_path: 数据集路径
            format_type: 数据集格式
            
        Returns:
            哈希字符串
        """
        try:
            path = Path(dataset_path)
            hash_obj = hashlib.md5()
            
            if format_type.lower() == "yolo":
                # 扫描labels目录下的所有txt文件
                labels_dir = path / "labels"
                if labels_dir.exists():
                    for txt_file in sorted(labels_dir.rglob("*.txt")):
                        try:
                            with open(txt_file, 'rb') as f:
                                hash_obj.update(f.read())
                        except Exception:
                            pass
                
                # 同时包含data.yaml
                yaml_file = path / "data.yaml"
                if yaml_file.exists():
                    with open(yaml_file, 'rb') as f:
                        hash_obj.update(f.read())
                        
            elif format_type.lower() == "coco":
                # 扫描annotations目录下的json文件
                anno_dir = path / "annotations"
                if anno_dir.exists():
                    for json_file in sorted(anno_dir.glob("*.json")):
                        try:
                            with open(json_file, 'rb') as f:
                                hash_obj.update(f.read())
                        except Exception:
                            pass
                            
            elif format_type.lower() == "voc":
                # 扫描Annotations目录下的xml文件
                anno_dir = path / "Annotations"
                if anno_dir.exists():
                    for xml_file in sorted(anno_dir.glob("*.xml")):
                        try:
                            with open(xml_file, 'rb') as f:
                                hash_obj.update(f.read())
                        except Exception:
                            pass
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            logger.warning(f"计算labels哈希失败: {e}")
            return ""
    
    async def _save_statistics(
        self, 
        dataset_id: str, 
        data: Dict[str, Any]
    ) -> DatasetStatistics:
        """
        保存统计信息到数据库
        
        Args:
            dataset_id: 数据集ID
            data: 统计数据
            
        Returns:
            保存后的DatasetStatistics对象
        """
        # 检查是否已存在
        existing = await self._get_existing_statistics(dataset_id)
        
        if existing:
            # 更新现有记录
            logger.info(f"_save_statistics 更新现有记录: dataset_id={dataset_id}")
            logger.info(f"  输入数据 split_distribution={data.get('split_distribution')}")
            for key, value in data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
                    if key == 'split_distribution':
                        logger.info(f"  已更新 split_distribution={value}")
            logger.info(f"  更新后 existing.split_distribution={existing.split_distribution}")
            stats = existing
        else:
            # 创建新记录 - 直接使用所有数据，让 SQLAlchemy 处理无效字段
            try:
                stats = DatasetStatistics(
                    dataset_id=dataset_id,
                    **data
                )
                self.db.add(stats)
            except TypeError as e:
                # 如果有无效字段，过滤掉后再试
                logger.warning(f"创建统计记录时有无效字段: {e}")
                valid_fields = {k: v for k, v in data.items() if k in [
                    'total_images', 'total_annotations', 'images_with_annotations',
                    'images_without_annotations', 'avg_annotations_per_image',
                    'class_count', 'class_distribution', 'annotations_per_class',
                    'image_sizes', 'avg_image_width', 'avg_image_height',
                    'split_distribution', 'avg_bbox_width', 'avg_bbox_height',
                    'avg_bbox_aspect_ratio', 'small_bboxes', 'medium_bboxes',
                    'large_bboxes', 'scan_status', 'last_scan_time', 'labels_hash'
                ]}
                stats = DatasetStatistics(
                    dataset_id=dataset_id,
                    **valid_fields
                )
                self.db.add(stats)
        
        await self.db.commit()
        await self.db.refresh(stats)
        
        # 同步更新 Dataset 模型的字段
        await self._sync_dataset_fields(dataset_id, data)
        
        return stats
    
    async def _sync_dataset_fields(
        self,
        dataset_id: str,
        data: Dict[str, Any]
    ) -> None:
        """
        同步更新 Dataset 模型的统计字段
        
        使 Dataset 模型的 total_images、class_names 等字段与统计信息保持一致
        
        Args:
            dataset_id: 数据集ID
            data: 统计数据
        """
        try:
            result = await self.db.execute(
                select(Dataset).where(Dataset.id == dataset_id)
            )
            dataset = result.scalar_one_or_none()
            
            if dataset:
                logger.info(f"同步 Dataset {dataset_id} 字段，输入数据: "
                           f"total_images={data.get('total_images')}, "
                           f"class_names={data.get('class_names')}")
                
                # 更新图像总数
                if "total_images" in data:
                    dataset.total_images = data["total_images"]
                
                # 更新标注框总数
                if "total_annotations" in data:
                    dataset.total_annotations = data["total_annotations"]
                
                # 从 class_names 或 annotations_per_class 更新类别名称
                class_names = data.get("class_names", [])
                if not class_names and "annotations_per_class" in data:
                    # 从类别分布中提取类别名称
                    class_names = list(data["annotations_per_class"].keys())
                
                # 修复类别名称（处理YAML换行导致的断裂）
                if class_names:
                    fixed_names = []
                    for name in class_names:
                        if ' ' in name:
                            fixed_name = name.replace(' ', '')
                            logger.info(f"_sync_dataset_fields 修复类别名称: '{name}' -> '{fixed_name}'")
                            fixed_names.append(fixed_name)
                        else:
                            fixed_names.append(name)
                    class_names = fixed_names
                
                if class_names:
                    old_names = dataset.class_names
                    dataset.class_names = class_names
                    logger.info(f"更新类别名称: {old_names} -> {class_names}")
                
                await self.db.commit()
                logger.info(f"已同步更新 Dataset {dataset_id} 的字段: "
                           f"total_images={dataset.total_images}, "
                           f"total_annotations={dataset.total_annotations}, "
                           f"class_names={dataset.class_names}")
        except Exception as e:
            logger.warning(f"同步 Dataset 字段失败: {e}")
            # 不影响主流程，仅记录警告
    
    async def _save_error_status(self, dataset_id: str, error_message: str) -> None:
        """
        保存错误状态
        
        Args:
            dataset_id: 数据集ID
            error_message: 错误信息
        """
        try:
            existing = await self._get_existing_statistics(dataset_id)
            if existing:
                existing.scan_status = "failed"
                existing.scan_error = error_message
                existing.last_scan_time = datetime.now(timezone.utc)
            else:
                stats = DatasetStatistics(
                    dataset_id=dataset_id,
                    scan_status="failed",
                    scan_error=error_message,
                    last_scan_time=datetime.now(timezone.utc)
                )
                self.db.add(stats)
            await self.db.commit()
        except Exception as e:
            logger.error(f"保存错误状态失败: {e}")


# 便捷函数
async def get_dataset_statistics(
    db: AsyncSession, 
    dataset_id: str,
    auto_create: bool = True
) -> Optional[DatasetStatistics]:
    """
    获取数据集统计信息的便捷函数
    
    Args:
        db: 数据库会话
        dataset_id: 数据集ID
        auto_create: 如果不存在是否自动创建
        
    Returns:
        DatasetStatistics对象或None
    """
    service = DatasetStatisticsService(db)
    if auto_create:
        return await service.get_or_create_statistics(dataset_id)
    return await service.get_statistics(dataset_id)
