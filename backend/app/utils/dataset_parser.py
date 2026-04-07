"""
数据集解析工具模块

支持YOLO、COCO、VOC三种格式的解析和相互转换。

示例用法:
    >>> from app.utils.dataset_parser import YOLOParser, COCOParser, VOCParser
    >>> 
    >>> # 解析YOLO格式
    >>> parser = YOLOParser("/path/to/yolo/dataset")
    >>> dataset = await parser.parse_async()
    >>> 
    >>> # 转换为COCO格式
    >>> from app.utils.dataset_parser import DatasetConverter
    >>> converter = DatasetConverter()
    >>> await converter.to_coco_async(dataset, "/output/path")
"""

import os
import json
import xml.etree.ElementTree as ET
import shutil
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union, Any
from dataclasses import dataclass, field
from enum import Enum
from PIL import Image
import logging

# 配置日志
logger = logging.getLogger(__name__)


class DatasetFormat(Enum):
    """数据集格式枚举"""
    YOLO = "yolo"
    COCO = "coco"
    VOC = "voc"


@dataclass
class BBox:
    """
    边界框数据类
    
    Attributes:
        x: 边界框左上角x坐标（或中心x，取决于格式）
        y: 边界框左上角y坐标（或中心y，取决于格式）
        width: 边界框宽度
        height: 边界框高度
        class_id: 类别ID
        class_name: 类别名称（可选）
        confidence: 置信度分数（可选，用于预测结果）
    """
    x: float
    y: float
    width: float
    height: float
    class_id: int
    class_name: Optional[str] = None
    confidence: Optional[float] = None

    def to_yolo_format(self, img_width: int, img_height: int) -> str:
        """
        转换为YOLO格式字符串
        
        YOLO格式: <class_id> <x_center> <y_center> <width> <height>
        所有值都是相对于图像尺寸的归一化值 (0-1)
        
        Args:
            img_width: 图像宽度
            img_height: 图像高度
            
        Returns:
            YOLO格式标注字符串
        """
        x_center = (self.x + self.width / 2) / img_width
        y_center = (self.y + self.height / 2) / img_height
        norm_width = self.width / img_width
        norm_height = self.height / img_height
        return f"{self.class_id} {x_center:.6f} {y_center:.6f} {norm_width:.6f} {norm_height:.6f}"

    def to_voc_format(self) -> Dict[str, float]:
        """
        转换为VOC格式字典
        
        VOC格式使用绝对坐标: xmin, ymin, xmax, ymax
        
        Returns:
            VOC格式边界框字典
        """
        return {
            "xmin": self.x,
            "ymin": self.y,
            "xmax": self.x + self.width,
            "ymax": self.y + self.height
        }

    def to_coco_format(self) -> List[float]:
        """
        转换为COCO格式列表
        
        COCO格式: [x, y, width, height] 使用绝对坐标
        
        Returns:
            COCO格式边界框列表
        """
        return [self.x, self.y, self.width, self.height]


@dataclass
class DatasetImage:
    """
    数据集图像数据类
    
    Attributes:
        id: 图像唯一标识
        filename: 图像文件名
        filepath: 图像文件路径
        width: 图像宽度
        height: 图像高度
        bboxes: 边界框列表
        split: 数据划分（train/val/test）
    """
    id: str
    filename: str
    filepath: str
    width: int = 0
    height: int = 0
    bboxes: List[BBox] = field(default_factory=list)
    split: str = "train"

    @property
    def has_annotations(self) -> bool:
        """检查是否有标注信息"""
        return len(self.bboxes) > 0


@dataclass
class DatasetInfo:
    """
    数据集信息数据类
    
    Attributes:
        name: 数据集名称
        format: 数据集格式
        path: 数据集路径
        class_names: 类别名称列表
        images: 图像列表
        splits: 划分统计
    """
    name: str
    format: DatasetFormat
    path: str
    class_names: List[str] = field(default_factory=list)
    images: List[DatasetImage] = field(default_factory=list)
    splits: Dict[str, int] = field(default_factory=dict)

    @property
    def total_images(self) -> int:
        """获取图像总数"""
        return len(self.images)

    @property
    def total_annotations(self) -> int:
        """获取标注总数"""
        return sum(len(img.bboxes) for img in self.images)

    @property
    def num_classes(self) -> int:
        """获取类别数量"""
        return len(self.class_names)

    def get_class_distribution(self) -> Dict[str, int]:
        """
        获取类别分布统计
        
        Returns:
            类别到数量的映射字典
        """
        distribution: Dict[str, int] = {}
        for img in self.images:
            for bbox in img.bboxes:
                class_name = bbox.class_name or str(bbox.class_id)
                distribution[class_name] = distribution.get(class_name, 0) + 1
        return distribution

    def get_split_distribution(self) -> Dict[str, int]:
        """
        获取划分分布统计
        
        Returns:
            划分到数量的映射字典
        """
        distribution: Dict[str, int] = {}
        for img in self.images:
            distribution[img.split] = distribution.get(img.split, 0) + 1
        return distribution


class DatasetParserError(Exception):
    """数据集解析错误基类"""
    pass


class InvalidFormatError(DatasetParserError):
    """无效格式错误"""
    pass


class FileNotFoundError(DatasetParserError):
    """文件未找到错误"""
    pass


class BaseParser:
    """
    数据集解析器基类
    
    所有具体解析器都应继承此类并实现parse方法。
    """

    def __init__(self, dataset_path: str, max_images: Optional[int] = None):
        """
        初始化解析器
        
        Args:
            dataset_path: 数据集根目录路径
            max_images: 最大解析图像数量（None表示不限制）
        """
        self.dataset_path = Path(dataset_path)
        self.max_images = max_images
        self.errors: List[str] = []

    def parse(self) -> DatasetInfo:
        """
        解析数据集（同步方法）
        
        Returns:
            DatasetInfo对象
            
        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError("子类必须实现parse方法")

    async def parse_async(self) -> DatasetInfo:
        """
        异步解析数据集
        
        Returns:
            DatasetInfo对象
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.parse)

    def _validate_path(self) -> bool:
        """
        验证数据集路径是否存在
        
        Returns:
            路径是否存在
        """
        if not self.dataset_path.exists():
            self.errors.append(f"数据集路径不存在: {self.dataset_path}")
            return False
        return True

    def _get_image_size(self, image_path: Path) -> Tuple[int, int]:
        """
        获取图像尺寸
        
        Args:
            image_path: 图像文件路径
            
        Returns:
            (width, height)元组
            
        Raises:
            DatasetParserError: 图像读取失败时抛出
        """
        try:
            with Image.open(image_path) as img:
                return img.size
        except Exception as e:
            raise DatasetParserError(f"无法读取图像 {image_path}: {e}")


class YOLOParser(BaseParser):
    """
    YOLO格式数据集解析器
    
    YOLO格式目录结构:
        dataset/
        ├── images/
        │   ├── train/
        │   ├── val/
        │   └── test/
        └── labels/
            ├── train/
            ├── val/
            └── test/
    
    每个label文件对应一个image文件，使用相同文件名，扩展名为.txt
    格式: <class_id> <x_center> <y_center> <width> <height>（均为归一化值）
    """

    def __init__(self, dataset_path: str, class_names: Optional[List[str]] = None, max_images: Optional[int] = None):
        """
        初始化YOLO解析器
        
        Args:
            dataset_path: 数据集根目录路径
            class_names: 类别名称列表（可选，会从data.yaml读取）
            max_images: 最大解析图像数量（None表示不限制）
        """
        super().__init__(dataset_path, max_images)
        self.class_names = class_names or []

    def parse(self) -> DatasetInfo:
        """
        解析YOLO格式数据集
        
        支持多种目录结构:
        1. 标准YOLO: images/train, images/val, images/test
        2. 子目录结构: dataset_name/images/train
        3. 扁平结构: train/images, val/images
        
        Returns:
            DatasetInfo对象
            
        Raises:
            InvalidFormatError: 格式无效时抛出
            FileNotFoundError: 必要文件缺失时抛出
        """
        logger.info(f"YOLOParser.parse() 开始解析: {self.dataset_path}")
        
        if not self._validate_path():
            raise FileNotFoundError(f"数据集路径不存在: {self.dataset_path}")

        # 尝试读取data.yaml获取类别信息
        self._load_yaml_config()
        logger.info(f"YOLOParser 加载YAML后 class_names: {self.class_names}")

        images: List[DatasetImage] = []
        splits: Dict[str, int] = {}

        # 查找images目录（支持多种结构）
        images_dir, labels_dir = self._find_images_and_labels_dirs()
        
        if not images_dir or not images_dir.exists():
            logger.error(f"YOLOParser 未找到images目录: {self.dataset_path}")
            raise InvalidFormatError(f"未找到images目录，路径: {self.dataset_path}")

        # 检测是否是扁平结构（images_dir == labels_dir 表示是数据集根目录）
        is_flat_structure = images_dir == labels_dir
        logger.info(f"YOLOParser 结构检测: images_dir={images_dir}, is_flat={is_flat_structure}, max_images={self.max_images}")

        # 遍历所有划分（train/val/test）
        total_parsed = 0
        for split in ["train", "val", "test"]:
            # 如果已达到最大解析数量，停止解析
            if self.max_images is not None and total_parsed >= self.max_images:
                logger.info(f"已达到最大解析数量 {self.max_images}，停止解析")
                break
            
            if is_flat_structure:
                # 扁平结构: dataset_name/train/images/, dataset_name/train/labels/
                split_images_dir = images_dir / split / "images"
                split_labels_dir = labels_dir / split / "labels"
                # 也检查 valid 别名
                if not split_images_dir.exists() and split == "val":
                    split_images_dir = images_dir / "valid" / "images"
                    split_labels_dir = labels_dir / "valid" / "labels"
            else:
                # 标准结构: images/train/, labels/train/
                split_images_dir = images_dir / split
                split_labels_dir = labels_dir / split

            logger.debug(f"检查split {split}: images={split_images_dir}, exists={split_images_dir.exists()}")
            
            if not split_images_dir.exists():
                continue

            image_files = list(split_images_dir.glob("*"))
            image_files = [f for f in image_files if f.suffix.lower() in 
                          ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']]

            splits[split] = len(image_files)
            logger.info(f"Split {split}: 找到 {len(image_files)} 个图像")

            for img_file in image_files:
                # 如果已达到最大解析数量，停止解析
                if self.max_images is not None and total_parsed >= self.max_images:
                    logger.info(f"已达到最大解析数量 {self.max_images}，停止解析")
                    break
                
                try:
                    dataset_img = self._parse_image(img_file, split_labels_dir, split)
                    images.append(dataset_img)
                    total_parsed += 1
                except Exception as e:
                    logger.warning(f"解析图像失败 {img_file}: {e}")
                    self.errors.append(f"解析图像失败 {img_file}: {e}")

        return DatasetInfo(
            name=self.dataset_path.name,
            format=DatasetFormat.YOLO,
            path=str(self.dataset_path),
            class_names=self.class_names,
            images=images,
            splits=splits
        )

    def _find_images_and_labels_dirs(self) -> Tuple[Optional[Path], Optional[Path]]:
        """
        查找images和labels目录
        
        支持多种目录结构:
        1. 标准YOLO: ./images/, ./labels/ (包含 train/val/test 子目录)
        2. 子目录: ./dataset_name/images/, ./dataset_name/labels/
        3. 扁平结构: ./dataset_name/train/images/, ./dataset_name/valid/images/
        4. 嵌套: ./extracted/dataset_name/
        
        Returns:
            (images_dir, labels_dir) 元组 - 注意对于扁平结构返回的是数据集根目录，需要特殊处理
        """
        logger.info(f"_find_images_and_labels_dirs: 数据集路径={self.dataset_path}")
        
        # 首先尝试标准YOLO结构: images/, labels/
        images_dir = self.dataset_path / "images"
        labels_dir = self.dataset_path / "labels"
        logger.debug(f"检查标准结构: images={images_dir}, exists={images_dir.exists()}")
        
        if images_dir.exists():
            logger.info(f"找到标准YOLO结构: {images_dir}")
            return images_dir, labels_dir
        
        # 查找扁平结构: dataset_name/train/images/, dataset_name/valid/images/
        # 这种情况下返回数据集根目录，parse方法需要特殊处理
        logger.debug(f"检查扁平结构 (split/images)...")
        for split_name in ["train", "valid", "val", "test"]:
            split_dir = self.dataset_path / split_name
            if split_dir.exists():
                img_dir = split_dir / "images"
                lbl_dir = split_dir / "labels"
                if img_dir.exists():
                    # 找到扁平结构，返回数据集根目录
                    logger.info(f"找到扁平YOLO结构: {self.dataset_path} (包含 {split_name}/images)")
                    return self.dataset_path, self.dataset_path  # 根目录，parse方法会从子目录读取
        
        # 查找子目录中的结构 (如 dataset_name/images/ 或 dataset_name/train/images/)
        logger.debug(f"检查子目录结构...")
        for subdir in self.dataset_path.iterdir():
            if subdir.is_dir():
                # 首先检查子目录中的标准结构: subdir/images/
                img_dir = subdir / "images"
                lbl_dir = subdir / "labels"
                logger.debug(f"  检查子目录: {subdir.name}, images={img_dir}, exists={img_dir.exists()}")
                if img_dir.exists():
                    logger.info(f"找到子目录YOLO结构: {img_dir}")
                    return img_dir, lbl_dir
                
                # 然后检查子目录中的扁平结构: subdir/train/images/
                for split_name in ["train", "valid", "val", "test"]:
                    split_img_dir = subdir / split_name / "images"
                    split_lbl_dir = subdir / split_name / "labels"
                    if split_img_dir.exists():
                        logger.info(f"找到子目录扁平YOLO结构: {subdir} (包含 {split_name}/images)")
                        return subdir, subdir  # 返回子目录作为根目录，parse方法会从子目录读取
        
        logger.warning(f"未找到任何images目录，路径: {self.dataset_path}")
        return None, None

    def _load_yaml_config(self) -> None:
        """加载YAML配置文件
        
        尝试查找多种可能的YAML文件名:
        - data.yaml (YOLO标准)
        - dataset.yaml
        - config.yaml
        
        会在根目录和第一层子目录中查找
        """
        yaml_names = ["data.yaml", "dataset.yaml", "config.yaml"]
        
        def _try_load_yaml(yaml_file: Path) -> bool:
            """尝试加载单个YAML文件，成功找到names字段返回True"""
            if not yaml_file.exists():
                return False
            try:
                import yaml
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                if 'names' in config:
                    names = config['names']
                    if isinstance(names, dict):
                        self.class_names = [names[i] for i in sorted(names.keys())]
                    elif isinstance(names, list):
                        self.class_names = names
                    logger.info(f"从 {yaml_file} 加载了 {len(self.class_names)} 个类别")
                    return True  # 只有成功加载names才返回True停止查找
                return False  # 文件存在但没有names字段，继续查找
            except ImportError:
                logger.warning("未安装pyyaml，无法解析YAML文件")
                return True  # 停止查找
            except Exception as e:
                logger.warning(f"解析{yaml_file}失败: {e}")
                return False
        
        # 首先在根目录查找
        for yaml_name in yaml_names:
            if _try_load_yaml(self.dataset_path / yaml_name):
                return
        
        # 如果在根目录没找到，在第一层子目录中查找
        try:
            for subdir in self.dataset_path.iterdir():
                if subdir.is_dir():
                    for yaml_name in yaml_names:
                        if _try_load_yaml(subdir / yaml_name):
                            return
        except Exception as e:
            logger.warning(f"扫描子目录查找YAML失败: {e}")

    def _parse_image(self, img_file: Path, labels_dir: Path, split: str) -> DatasetImage:
        """
        解析单个图像及其标注
        
        Args:
            img_file: 图像文件路径
            labels_dir: 标注目录路径
            split: 数据划分
            
        Returns:
            DatasetImage对象
        """
        # 获取图像尺寸
        width, height = self._get_image_size(img_file)

        # 查找对应的标注文件
        label_file = labels_dir / f"{img_file.stem}.txt"
        bboxes: List[BBox] = []

        if label_file.exists():
            bboxes = self._parse_label_file(label_file, width, height)

        return DatasetImage(
            id=img_file.stem,
            filename=img_file.name,
            filepath=str(img_file),
            width=width,
            height=height,
            bboxes=bboxes,
            split=split
        )

    def _parse_label_file(self, label_file: Path, img_width: int, img_height: int) -> List[BBox]:
        """
        解析YOLO标注文件
        
        Args:
            label_file: 标注文件路径
            img_width: 图像宽度
            img_height: 图像高度
            
        Returns:
            BBox对象列表
        """
        bboxes: List[BBox] = []

        with open(label_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parts = line.split()
                if len(parts) < 5:
                    continue

                try:
                    class_id = int(parts[0])
                    x_center = float(parts[1]) * img_width
                    y_center = float(parts[2]) * img_height
                    norm_width = float(parts[3]) * img_width
                    norm_height = float(parts[4]) * img_height

                    # 转换为左上角坐标
                    x = x_center - norm_width / 2
                    y = y_center - norm_height / 2

                    class_name = self.class_names[class_id] if class_id < len(self.class_names) else None

                    bboxes.append(BBox(
                        x=x,
                        y=y,
                        width=norm_width,
                        height=norm_height,
                        class_id=class_id,
                        class_name=class_name
                    ))
                except (ValueError, IndexError) as e:
                    logger.warning(f"解析标注行失败: {line} - {e}")

        return bboxes


class COCOParser(BaseParser):
    """
    COCO格式数据集解析器
    
    COCO格式使用单个JSON文件包含所有标注信息:
        dataset/
        ├── annotations/
        │   ├── instances_train.json
        │   └── instances_val.json
        └── images/
            ├── train/
            └── val/
    
    JSON结构包含: info, images, annotations, categories
    """

    def __init__(self, dataset_path: str, annotation_file: Optional[str] = None, max_images: Optional[int] = None):
        """
        初始化COCO解析器
        
        Args:
            dataset_path: 数据集根目录路径
            annotation_file: 标注文件路径（可选，默认查找annotations目录）
            max_images: 最大解析图像数量（None表示不限制）
        """
        super().__init__(dataset_path, max_images)
        self.annotation_file = annotation_file

    def parse(self) -> DatasetInfo:
        """
        解析COCO格式数据集
        
        Returns:
            DatasetInfo对象
            
        Raises:
            InvalidFormatError: 格式无效时抛出
            FileNotFoundError: 必要文件缺失时抛出
        """
        if not self._validate_path():
            raise FileNotFoundError(f"数据集路径不存在: {self.dataset_path}")

        # 查找标注文件
        annotation_files = self._find_annotation_files()
        if not annotation_files:
            raise FileNotFoundError(f"未找到COCO标注文件: {self.dataset_path}")

        all_images: List[DatasetImage] = []
        all_class_names: List[str] = []
        splits: Dict[str, int] = {}

        for anno_file, split in annotation_files:
            # 如果已达到最大解析数量，停止解析
            if self.max_images is not None and len(all_images) >= self.max_images:
                logger.info(f"已达到最大解析数量 {self.max_images}，停止解析")
                break
            
            try:
                images, class_names = self._parse_annotation_file(anno_file, split)
                all_images.extend(images)
                splits[split] = len(images)
                if not all_class_names and class_names:
                    all_class_names = class_names
            except Exception as e:
                logger.error(f"解析标注文件失败 {anno_file}: {e}")
                self.errors.append(f"解析标注文件失败 {anno_file}: {e}")

        return DatasetInfo(
            name=self.dataset_path.name,
            format=DatasetFormat.COCO,
            path=str(self.dataset_path),
            class_names=all_class_names,
            images=all_images,
            splits=splits
        )

    def _find_annotation_files(self) -> List[Tuple[Path, str]]:
        """
        查找所有标注文件
        
        Returns:
            (文件路径, 划分名称)列表
        """
        files: List[Tuple[Path, str]] = []

        if self.annotation_file:
            anno_path = Path(self.annotation_file)
            if anno_path.exists():
                split = self._extract_split_from_filename(anno_path.name)
                files.append((anno_path, split))
            return files

        # 查找annotations目录
        anno_dir = self.dataset_path / "annotations"
        if not anno_dir.exists():
            return files

        # 查找instances_*.json文件
        for json_file in anno_dir.glob("instances_*.json"):
            split = self._extract_split_from_filename(json_file.name)
            files.append((json_file, split))

        return files

    def _extract_split_from_filename(self, filename: str) -> str:
        """从文件名提取划分名称"""
        filename_lower = filename.lower()
        if "train" in filename_lower:
            return "train"
        elif "val" in filename_lower or "valid" in filename_lower:
            return "val"
        elif "test" in filename_lower:
            return "test"
        return "train"

    def _parse_annotation_file(self, anno_file: Path, split: str) -> Tuple[List[DatasetImage], List[str]]:
        """
        解析单个标注文件
        
        Args:
            anno_file: 标注文件路径
            split: 数据划分
            
        Returns:
            (图像列表, 类别名称列表)
        """
        with open(anno_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 解析类别
        categories = {cat['id']: cat['name'] for cat in data.get('categories', [])}
        class_names = [categories[i] for i in sorted(categories.keys())]

        # 解析图像（限制数量）
        image_dict: Dict[str, DatasetImage] = {}
        all_images = data.get('images', [])
        
        # 如果设置了最大数量，截断图像列表
        if self.max_images is not None:
            # 计算该split最多可以解析多少张图片
            remaining = self.max_images - sum(1 for img in image_dict.values())
            all_images = all_images[:remaining]
        
        for img_info in all_images:
            img_id = str(img_info['id'])
            image_dict[img_id] = DatasetImage(
                id=img_id,
                filename=img_info['file_name'],
                filepath=str(self.dataset_path / "images" / split / img_info['file_name']),
                width=img_info.get('width', 0),
                height=img_info.get('height', 0),
                split=split
            )

        # 解析标注
        for anno in data.get('annotations', []):
            img_id = str(anno['image_id'])
            if img_id not in image_dict:
                continue

            bbox_data = anno['bbox']  # [x, y, width, height]
            category_id = anno['category_id']

            bbox = BBox(
                x=bbox_data[0],
                y=bbox_data[1],
                width=bbox_data[2],
                height=bbox_data[3],
                class_id=category_id,
                class_name=categories.get(category_id)
            )
            image_dict[img_id].bboxes.append(bbox)

        return list(image_dict.values()), class_names


class VOCParser(BaseParser):
    """
    VOC格式数据集解析器
    
    VOC格式使用XML文件存储标注:
        dataset/
        ├── Annotations/
        │   └── *.xml
        ├── JPEGImages/
        │   └── *.jpg
        ├── ImageSets/
        │   └── Main/
        │       ├── train.txt
        │       ├── val.txt
        │       └── test.txt
        └── labels.txt (类别列表，可选)
    
    XML结构包含: filename, size, object[bndbox, name]
    """

    def __init__(self, dataset_path: str, class_names: Optional[List[str]] = None, max_images: Optional[int] = None):
        """
        初始化VOC解析器
        
        Args:
            dataset_path: 数据集根目录路径
            class_names: 类别名称列表（可选）
            max_images: 最大解析图像数量（None表示不限制）
        """
        super().__init__(dataset_path, max_images)
        self.class_names = class_names or []
        self.class_to_id: Dict[str, int] = {}

    def parse(self) -> DatasetInfo:
        """
        解析VOC格式数据集
        
        Returns:
            DatasetInfo对象
            
        Raises:
            InvalidFormatError: 格式无效时抛出
            FileNotFoundError: 必要文件缺失时抛出
        """
        if not self._validate_path():
            raise FileNotFoundError(f"数据集路径不存在: {self.dataset_path}")

        # 加载类别列表
        self._load_class_names()

        # 获取图像划分
        image_splits = self._load_image_splits()

        annotations_dir = self.dataset_path / "Annotations"
        images_dir = self.dataset_path / "JPEGImages"

        if not annotations_dir.exists():
            raise InvalidFormatError(f"未找到Annotations目录: {annotations_dir}")
        if not images_dir.exists():
            raise InvalidFormatError(f"未找到JPEGImages目录: {images_dir}")

        images: List[DatasetImage] = []
        splits: Dict[str, int] = {"train": 0, "val": 0, "test": 0}

        # 获取所有XML文件
        all_xml_files = list(annotations_dir.rglob("*.xml"))
        
        # 如果设置了最大数量，截断列表
        if self.max_images is not None:
            all_xml_files = all_xml_files[:self.max_images]
            logger.info(f"VOC解析限制: 只解析前 {self.max_images} 张图像")

        # 解析XML文件
        for xml_file in all_xml_files:
            # 如果已达到最大解析数量，停止解析
            if self.max_images is not None and len(images) >= self.max_images:
                logger.info(f"已达到最大解析数量 {self.max_images}，停止解析")
                break
            
            try:
                image_name = xml_file.stem
                split = image_splits.get(image_name, "train")
                dataset_img = self._parse_xml(xml_file, images_dir, image_name, split)
                if dataset_img:
                    images.append(dataset_img)
                    splits[split] = splits.get(split, 0) + 1
            except Exception as e:
                logger.warning(f"解析XML失败 {xml_file}: {e}")
                self.errors.append(f"解析XML失败 {xml_file}: {e}")

        return DatasetInfo(
            name=self.dataset_path.name,
            format=DatasetFormat.VOC,
            path=str(self.dataset_path),
            class_names=self.class_names,
            images=images,
            splits=splits
        )

    def _load_class_names(self) -> None:
        """加载类别名称列表"""
        labels_file = self.dataset_path / "labels.txt"
        if labels_file.exists():
            with open(labels_file, 'r', encoding='utf-8') as f:
                self.class_names = [line.strip() for line in f if line.strip()]
        
        # 建立类别到ID的映射
        self.class_to_id = {name: idx for idx, name in enumerate(self.class_names)}

    def _load_image_splits(self) -> Dict[str, str]:
        """
        加载图像划分信息
        
        Returns:
            图像名称到划分的映射字典
        """
        splits: Dict[str, str] = {}
        image_sets_dir = self.dataset_path / "ImageSets" / "Main"

        if not image_sets_dir.exists():
            return splits

        for split in ["train", "val", "test"]:
            split_file = image_sets_dir / f"{split}.txt"
            if split_file.exists():
                with open(split_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        image_name = line.strip().split()[0]
                        splits[image_name] = split

        return splits

    def _parse_xml(self, xml_file: Path, images_dir: Path, image_name: str, split: str) -> Optional[DatasetImage]:
        """
        解析单个XML文件
        
        Args:
            xml_file: XML文件路径
            images_dir: 图像目录路径
            image_name: 图像名称
            split: 数据划分
            
        Returns:
            DatasetImage对象或None
        """
        tree = ET.parse(xml_file)
        root = tree.getroot()

        # 获取文件名
        filename_elem = root.find('filename')
        if filename_elem is None or not filename_elem.text:
            return None
        filename = filename_elem.text

        # 获取图像尺寸
        size_elem = root.find('size')
        width = 0
        height = 0
        if size_elem is not None:
            width_elem = size_elem.find('width')
            height_elem = size_elem.find('height')
            if width_elem is not None and width_elem.text:
                width = int(width_elem.text)
            if height_elem is not None and height_elem.text:
                height = int(height_elem.text)

        # 如果XML中没有尺寸信息，从图像读取
        # 首先尝试在子目录中查找（如 JPEGImages/train/*.jpg）
        img_path = images_dir / split / filename
        if not img_path.exists():
            # 回退到直接在 images_dir 中查找
            img_path = images_dir / filename
        
        if (width == 0 or height == 0) and img_path.exists():
            width, height = self._get_image_size(img_path)

        # 解析目标
        bboxes: List[BBox] = []
        for obj in root.findall('object'):
            name_elem = obj.find('name')
            if name_elem is None or not name_elem.text:
                continue

            class_name = name_elem.text
            if class_name not in self.class_to_id:
                # 动态添加新类别
                class_id = len(self.class_names)
                self.class_names.append(class_name)
                self.class_to_id[class_name] = class_id
            else:
                class_id = self.class_to_id[class_name]

            bndbox = obj.find('bndbox')
            if bndbox is None:
                continue

            try:
                xmin = float(bndbox.find('xmin').text)
                ymin = float(bndbox.find('ymin').text)
                xmax = float(bndbox.find('xmax').text)
                ymax = float(bndbox.find('ymax').text)

                bboxes.append(BBox(
                    x=xmin,
                    y=ymin,
                    width=xmax - xmin,
                    height=ymax - ymin,
                    class_id=class_id,
                    class_name=class_name
                ))
            except (ValueError, AttributeError) as e:
                logger.warning(f"解析边界框失败: {e}")

        # 构建相对于数据集根目录的路径
        if img_path.exists():
            try:
                # 尝试获取相对路径
                filepath = str(img_path.relative_to(self.dataset_path))
            except ValueError:
                # 如果无法获取相对路径，使用绝对路径
                filepath = str(img_path)
        else:
            # 图像不存在，使用预期路径
            filepath = str(images_dir.relative_to(self.dataset_path) / split / filename)
        
        return DatasetImage(
            id=image_name,
            filename=filename,
            filepath=filepath,
            width=width,
            height=height,
            bboxes=bboxes,
            split=split
        )


class DatasetConverter:
    """
    数据集格式转换器
    
    支持YOLO、COCO、VOC三种格式之间的相互转换。
    
    示例用法:
        >>> converter = DatasetConverter()
        >>> dataset = await converter.parse_async("/path/to/yolo", DatasetFormat.YOLO)
        >>> await converter.to_coco_async(dataset, "/output/coco")
    """

    def __init__(self):
        """初始化转换器"""
        self.errors: List[str] = []

    def parse(self, dataset_path: str, format_type: DatasetFormat) -> DatasetInfo:
        """
        解析指定格式的数据集
        
        Args:
            dataset_path: 数据集路径
            format_type: 数据集格式
            
        Returns:
            DatasetInfo对象
        """
        if format_type == DatasetFormat.YOLO:
            parser: BaseParser = YOLOParser(dataset_path)
        elif format_type == DatasetFormat.COCO:
            parser = COCOParser(dataset_path)
        elif format_type == DatasetFormat.VOC:
            parser = VOCParser(dataset_path)
        else:
            raise InvalidFormatError(f"不支持的格式: {format_type}")

        return parser.parse()

    async def parse_async(self, dataset_path: str, format_type: DatasetFormat) -> DatasetInfo:
        """
        异步解析指定格式的数据集
        
        Args:
            dataset_path: 数据集路径
            format_type: 数据集格式
            
        Returns:
            DatasetInfo对象
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.parse, dataset_path, format_type)

    def to_yolo(self, dataset: DatasetInfo, output_path: str, 
                preserve_structure: bool = True) -> str:
        """
        转换为YOLO格式
        
        Args:
            dataset: 数据集信息对象
            output_path: 输出目录路径
            preserve_structure: 是否保留原划分结构
            
        Returns:
            输出目录路径
        """
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 创建目录结构
        (output_dir / "images" / "train").mkdir(parents=True, exist_ok=True)
        (output_dir / "images" / "val").mkdir(parents=True, exist_ok=True)
        (output_dir / "images" / "test").mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / "train").mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / "val").mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / "test").mkdir(parents=True, exist_ok=True)

        # 复制图像并生成标注
        for img in dataset.images:
            try:
                self._convert_image_to_yolo(img, output_dir, preserve_structure, Path(dataset.path))
            except Exception as e:
                logger.error(f"转换图像失败 {img.filename}: {e}")
                self.errors.append(f"转换图像失败 {img.filename}: {e}")

        # 生成data.yaml
        self._generate_yolo_yaml(dataset, output_dir)

        return str(output_dir)

    def _convert_image_to_yolo(self, img: DatasetImage, output_dir: Path, 
                               preserve_structure: bool, dataset_path: Path) -> None:
        """转换单个图像到YOLO格式"""
        split = img.split if preserve_structure else "train"

        # 复制图像
        src_path = Path(img.filepath)
        
        # 处理路径 - 如果 filepath 已经是相对于工作目录的完整路径，直接使用
        if not src_path.is_absolute():
            # 检查 filepath 是否已经包含 dataset_path 的部分
            if str(src_path).startswith(str(dataset_path.name)) or str(src_path).startswith(str(dataset_path)):
                # filepath 已经是相对于工作目录的完整路径
                pass
            else:
                # 真正的相对路径，需要拼接
                src_path = dataset_path / src_path
        
        dst_img_dir = output_dir / "images" / split
        dst_img_path = dst_img_dir / img.filename

        if src_path.exists():
            shutil.copy2(src_path, dst_img_path)

        # 生成标注文件
        dst_label_path = output_dir / "labels" / split / f"{Path(img.filename).stem}.txt"

        with open(dst_label_path, 'w', encoding='utf-8') as f:
            for bbox in img.bboxes:
                yolo_line = bbox.to_yolo_format(img.width, img.height)
                f.write(yolo_line + "\n")

    def _generate_yolo_yaml(self, dataset: DatasetInfo, output_dir: Path) -> None:
        """生成YOLO的data.yaml文件"""
        yaml_path = output_dir / "data.yaml"

        data = {
            "path": str(output_dir.absolute()),
            "train": "images/train",
            "val": "images/val",
            "test": "images/test" if dataset.splits.get("test", 0) > 0 else None,
            "nc": len(dataset.class_names),
            "names": {i: name for i, name in enumerate(dataset.class_names)}
        }

        try:
            import yaml
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
        except ImportError:
            # 手动生成简单YAML
            with open(yaml_path, 'w', encoding='utf-8') as f:
                f.write(f"path: {data['path']}\n")
                f.write(f"train: {data['train']}\n")
                f.write(f"val: {data['val']}\n")
                if data['test']:
                    f.write(f"test: {data['test']}\n")
                f.write(f"nc: {data['nc']}\n")
                f.write("names:\n")
                for i, name in data['names'].items():
                    f.write(f"  {i}: {name}\n")

    async def to_yolo_async(self, dataset: DatasetInfo, output_path: str,
                           preserve_structure: bool = True) -> str:
        """
        异步转换为YOLO格式
        
        Args:
            dataset: 数据集信息对象
            output_path: 输出目录路径
            preserve_structure: 是否保留原划分结构
            
        Returns:
            输出目录路径
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.to_yolo, dataset, output_path, preserve_structure)

    def to_coco(self, dataset: DatasetInfo, output_path: str) -> str:
        """
        转换为COCO格式
        
        Args:
            dataset: 数据集信息对象
            output_path: 输出目录路径
            
        Returns:
            输出目录路径
        """
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 创建目录结构
        (output_dir / "images" / "train").mkdir(parents=True, exist_ok=True)
        (output_dir / "images" / "val").mkdir(parents=True, exist_ok=True)
        (output_dir / "images" / "test").mkdir(parents=True, exist_ok=True)
        (output_dir / "annotations").mkdir(parents=True, exist_ok=True)

        # 按划分分组
        split_images: Dict[str, List[DatasetImage]] = {"train": [], "val": [], "test": []}
        for img in dataset.images:
            split = img.split if img.split in split_images else "train"
            split_images[split].append(img)

        # 为每个划分生成标注文件
        for split, images in split_images.items():
            if not images:
                continue

            try:
                self._generate_coco_json(dataset, images, output_dir, split)
            except Exception as e:
                logger.error(f"生成COCO JSON失败 {split}: {e}")
                self.errors.append(f"生成COCO JSON失败 {split}: {e}")

        return str(output_dir)

    def _generate_coco_json(self, dataset: DatasetInfo, images: List[DatasetImage],
                           output_dir: Path, split: str) -> None:
        """生成COCO格式的JSON文件"""
        coco_data = {
            "info": {
                "description": dataset.name,
                "version": "1.0",
                "year": 2024,
                "contributor": "",
                "date_created": ""
            },
            "images": [],
            "annotations": [],
            "categories": []
        }

        # 添加类别 - 使用 0-based 连续索引
        for idx, name in enumerate(dataset.class_names):
            coco_data["categories"].append({
                "id": idx,
                "name": name,
                "supercategory": ""
            })

        # 添加图像和标注
        annotation_id = 1
        img_id_counter = 1
        for img in images:
            img_id = img_id_counter  # 使用递增ID避免冲突
            img_id_counter += 1

            # 复制图像
            src_path = Path(img.filepath)
            # 处理相对路径 - 如果 filepath 已经是相对于工作目录的完整路径，直接使用
            if not src_path.is_absolute():
                # 检查 filepath 是否已经包含 dataset.path 的部分
                if str(src_path).startswith(str(Path(dataset.path).name)) or str(src_path).startswith(str(dataset.path)):
                    # filepath 已经是相对于工作目录的完整路径
                    pass
                else:
                    # 真正的相对路径，需要拼接
                    src_path = Path(dataset.path) / src_path
            
            dst_path = output_dir / "images" / split / img.filename
            
            logger.debug(f"COCO复制图像: {img.filename}, src={src_path}, exists={src_path.exists()}, dst={dst_path}")
            
            if src_path.exists():
                shutil.copy2(src_path, dst_path)
                logger.debug(f"COCO复制成功: {dst_path}")
            else:
                logger.warning(f"COCO复制失败: 源文件不存在 {src_path}")

            # 添加图像信息
            coco_data["images"].append({
                "id": img_id,
                "file_name": img.filename,
                "width": img.width,
                "height": img.height
            })

            # 添加标注 - 确保 category_id 在有效范围内
            for bbox in img.bboxes:
                # 确保 class_id 在有效范围内 [0, len(class_names)-1]
                category_id = bbox.class_id
                if category_id < 0 or category_id >= len(dataset.class_names):
                    logger.warning(f"类别ID {category_id} 超出范围，使用0代替")
                    category_id = 0
                    
                coco_data["annotations"].append({
                    "id": annotation_id,
                    "image_id": img_id,
                    "category_id": category_id,
                    "bbox": bbox.to_coco_format(),
                    "area": bbox.width * bbox.height,
                    "iscrowd": 0
                })
                annotation_id += 1

        # 保存JSON
        json_path = output_dir / "annotations" / f"instances_{split}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(coco_data, f, indent=2, ensure_ascii=False)

    async def to_coco_async(self, dataset: DatasetInfo, output_path: str) -> str:
        """
        异步转换为COCO格式
        
        Args:
            dataset: 数据集信息对象
            output_path: 输出目录路径
            
        Returns:
            输出目录路径
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.to_coco, dataset, output_path)

    def to_voc(self, dataset: DatasetInfo, output_path: str) -> str:
        """
        转换为VOC格式
        
        Args:
            dataset: 数据集信息对象
            output_path: 输出目录路径
            
        Returns:
            输出目录路径
        """
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 创建目录结构 - 支持按分割组织
        splits = ["train", "val", "test"]
        for split in splits:
            (output_dir / "Annotations" / split).mkdir(parents=True, exist_ok=True)
            (output_dir / "JPEGImages" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "ImageSets" / "Main").mkdir(parents=True, exist_ok=True)

        # 生成每个图像的XML
        split_images: Dict[str, List[str]] = {"train": [], "val": [], "test": []}

        dataset_path = Path(dataset.path)
        for img in dataset.images:
            try:
                split = img.split if img.split in split_images else "train"
                self._generate_voc_xml(img, output_dir, split, dataset_path)
                split_images[split].append(Path(img.filename).stem)
            except Exception as e:
                logger.error(f"生成VOC XML失败 {img.filename}: {e}")
                self.errors.append(f"生成VOC XML失败 {img.filename}: {e}")

        # 生成ImageSets
        for split, image_names in split_images.items():
            split_file = output_dir / "ImageSets" / "Main" / f"{split}.txt"
            with open(split_file, 'w', encoding='utf-8') as f:
                for name in image_names:
                    f.write(f"{name}\n")

        # 生成labels.txt
        labels_file = output_dir / "labels.txt"
        with open(labels_file, 'w', encoding='utf-8') as f:
            for name in dataset.class_names:
                f.write(f"{name}\n")

        return str(output_dir)

    def _generate_voc_xml(self, img: DatasetImage, output_dir: Path, split: str = "train", dataset_path: Path = None) -> None:
        """生成单个图像的VOC XML"""
        # 复制图像
        src_path = Path(img.filepath)
        
        # 处理路径 - 如果 filepath 已经是相对于工作目录的完整路径，直接使用
        # 否则相对于 dataset_path
        if not src_path.is_absolute() and dataset_path:
            # 检查 filepath 是否已经包含 dataset_path 的部分
            if str(src_path).startswith(str(dataset_path.name)) or str(src_path).startswith(str(dataset_path)):
                # filepath 已经是相对于工作目录的完整路径
                pass
            else:
                # 真正的相对路径，需要拼接
                src_path = dataset_path / src_path
        
        dst_path = output_dir / "JPEGImages" / split / img.filename
        
        # 调试日志
        logger.debug(f"VOC复制图像: {img.filename}, src={src_path}, exists={src_path.exists()}, dst={dst_path}")
        
        if src_path.exists():
            shutil.copy2(src_path, dst_path)
            logger.debug(f"VOC复制成功: {dst_path}")
        else:
            logger.warning(f"VOC复制失败: 源文件不存在 {src_path}")

        # 创建XML
        root = ET.Element("annotation")

        # 文件名
        filename_elem = ET.SubElement(root, "filename")
        filename_elem.text = img.filename

        # 尺寸
        size_elem = ET.SubElement(root, "size")
        width_elem = ET.SubElement(size_elem, "width")
        width_elem.text = str(img.width)
        height_elem = ET.SubElement(size_elem, "height")
        height_elem.text = str(img.height)
        depth_elem = ET.SubElement(size_elem, "depth")
        depth_elem.text = "3"

        # 目标
        for bbox in img.bboxes:
            obj_elem = ET.SubElement(root, "object")
            
            name_elem = ET.SubElement(obj_elem, "name")
            name_elem.text = bbox.class_name or str(bbox.class_id)
            
            pose_elem = ET.SubElement(obj_elem, "pose")
            pose_elem.text = "Unspecified"
            
            truncated_elem = ET.SubElement(obj_elem, "truncated")
            truncated_elem.text = "0"
            
            difficult_elem = ET.SubElement(obj_elem, "difficult")
            difficult_elem.text = "0"
            
            bndbox_elem = ET.SubElement(obj_elem, "bndbox")
            voc_bbox = bbox.to_voc_format()
            
            xmin_elem = ET.SubElement(bndbox_elem, "xmin")
            xmin_elem.text = str(int(voc_bbox["xmin"]))
            
            ymin_elem = ET.SubElement(bndbox_elem, "ymin")
            ymin_elem.text = str(int(voc_bbox["ymin"]))
            
            xmax_elem = ET.SubElement(bndbox_elem, "xmax")
            xmax_elem.text = str(int(voc_bbox["xmax"]))
            
            ymax_elem = ET.SubElement(bndbox_elem, "ymax")
            ymax_elem.text = str(int(voc_bbox["ymax"]))

        # 保存XML
        xml_path = output_dir / "Annotations" / split / f"{Path(img.filename).stem}.xml"
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    async def to_voc_async(self, dataset: DatasetInfo, output_path: str) -> str:
        """
        异步转换为VOC格式
        
        Args:
            dataset: 数据集信息对象
            output_path: 输出目录路径
            
        Returns:
            输出目录路径
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.to_voc, dataset, output_path)


class ThumbnailGenerator:
    """
    缩略图生成器
    
    用于生成数据集的缩略图预览。
    
    示例用法:
        >>> generator = ThumbnailGenerator(size=(256, 256))
        >>> await generator.generate_for_dataset_async(dataset, "/output/thumbs")
    """

    def __init__(self, size: Tuple[int, int] = (256, 256), quality: int = 85):
        """
        初始化缩略图生成器
        
        Args:
            size: 缩略图尺寸 (宽, 高)
            quality: JPEG质量 (1-100)
        """
        self.size = size
        self.quality = quality
        self.errors: List[str] = []

    def generate(self, image_path: str, output_path: str, 
                 draw_boxes: bool = False, bboxes: Optional[List[BBox]] = None) -> bool:
        """
        生成单张图像的缩略图
        
        Args:
            image_path: 原图像路径
            output_path: 输出缩略图路径
            draw_boxes: 是否绘制边界框
            bboxes: 边界框列表（draw_boxes为True时使用）
            
        Returns:
            是否成功生成
        """
        try:
            with Image.open(image_path) as img:
                # 转换为RGB（处理RGBA等模式）
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')

                # 生成缩略图（保持纵横比）
                img.thumbnail(self.size, Image.Resampling.LANCZOS)

                # 绘制边界框
                if draw_boxes and bboxes:
                    img = self._draw_bounding_boxes(img, bboxes)

                # 确保输出目录存在
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)

                # 保存
                img.save(output_path, "JPEG", quality=self.quality)
                return True

        except Exception as e:
            logger.error(f"生成缩略图失败 {image_path}: {e}")
            self.errors.append(f"生成缩略图失败 {image_path}: {e}")
            return False

    def _draw_bounding_boxes(self, img: Image.Image, bboxes: List[BBox]) -> Image.Image:
        """
        在图像上绘制边界框
        
        Args:
            img: PIL图像对象
            bboxes: 边界框列表
            
        Returns:
            绘制后的图像
        """
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(img)
        width, height = img.size

        # 缩放因子（原图到缩略图）
        original_path = getattr(img, 'filename', None)
        if original_path:
            try:
                with Image.open(original_path) as orig:
                    orig_width, orig_height = orig.size
                    scale_x = width / orig_width
                    scale_y = height / orig_height
            except:
                scale_x = scale_y = 1
        else:
            scale_x = scale_y = 1

        for bbox in bboxes:
            # 计算缩放后的坐标
            x1 = int(bbox.x * scale_x)
            y1 = int(bbox.y * scale_y)
            x2 = int((bbox.x + bbox.width) * scale_x)
            y2 = int((bbox.y + bbox.height) * scale_y)

            # 绘制边界框
            draw.rectangle([x1, y1, x2, y2], outline="red", width=2)

            # 绘制标签
            label = bbox.class_name or f"class_{bbox.class_id}"
            draw.text((x1, y1 - 10), label, fill="red")

        return img

    async def generate_async(self, image_path: str, output_path: str,
                            draw_boxes: bool = False, bboxes: Optional[List[BBox]] = None) -> bool:
        """
        异步生成单张图像的缩略图
        
        Args:
            image_path: 原图像路径
            output_path: 输出缩略图路径
            draw_boxes: 是否绘制边界框
            bboxes: 边界框列表
            
        Returns:
            是否成功生成
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate, image_path, output_path, draw_boxes, bboxes)

    def generate_for_dataset(self, dataset: DatasetInfo, output_dir: str,
                             max_images: int = 100, draw_boxes: bool = False) -> List[str]:
        """
        为数据集生成缩略图
        
        Args:
            dataset: 数据集信息对象
            output_dir: 输出目录
            max_images: 最大生成数量（每类采样）
            draw_boxes: 是否绘制边界框
            
        Returns:
            生成的缩略图路径列表
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        generated: List[str] = []
        images_to_process = dataset.images[:max_images]

        for img in images_to_process:
            thumb_path = output_path / f"{img.id}_thumb.jpg"
            success = self.generate(
                img.filepath, 
                str(thumb_path), 
                draw_boxes=draw_boxes,
                bboxes=img.bboxes if draw_boxes else None
            )
            if success:
                generated.append(str(thumb_path))

        return generated

    async def generate_for_dataset_async(self, dataset: DatasetInfo, output_dir: str,
                                          max_images: int = 100, draw_boxes: bool = False) -> List[str]:
        """
        异步为数据集生成缩略图
        
        Args:
            dataset: 数据集信息对象
            output_dir: 输出目录
            max_images: 最大生成数量
            draw_boxes: 是否绘制边界框
            
        Returns:
            生成的缩略图路径列表
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.generate_for_dataset, dataset, output_dir, max_images, draw_boxes
        )


class DatasetStatistics:
    """
    数据集统计工具
    
    用于计算数据集的各类统计信息。
    
    示例用法:
        >>> stats = DatasetStatistics(dataset)
        >>> info = stats.get_full_statistics()
        >>> print(info["class_distribution"])
    """

    def __init__(self, dataset: DatasetInfo):
        """
        初始化统计工具
        
        Args:
            dataset: 数据集信息对象
        """
        self.dataset = dataset

    def get_basic_info(self) -> Dict[str, Any]:
        """
        获取基本信息
        
        Returns:
            基本信息字典
        """
        return {
            "name": self.dataset.name,
            "format": self.dataset.format.value,
            "total_images": self.dataset.total_images,
            "total_annotations": self.dataset.total_annotations,
            "num_classes": self.dataset.num_classes,
            "class_names": self.dataset.class_names
        }

    def get_class_statistics(self) -> Dict[str, Any]:
        """
        获取类别统计
        
        Returns:
            类别统计字典
        """
        distribution = self.dataset.get_class_distribution()
        total = sum(distribution.values())

        return {
            "distribution": distribution,
            "total": total,
            "per_class_average": total / len(distribution) if distribution else 0,
            "min_count": min(distribution.values()) if distribution else 0,
            "max_count": max(distribution.values()) if distribution else 0
        }

    def get_split_statistics(self) -> Dict[str, Any]:
        """
        获取划分统计
        
        Returns:
            划分统计字典
        """
        distribution = self.dataset.get_split_distribution()
        total = sum(distribution.values())

        percentages = {}
        if total > 0:
            for split, count in distribution.items():
                percentages[split] = round(count / total * 100, 2)

        return {
            "distribution": distribution,
            "percentages": percentages,
            "total": total
        }

    def get_bbox_statistics(self) -> Dict[str, Any]:
        """
        获取边界框统计
        
        Returns:
            边界框统计字典
        """
        bbox_areas: List[float] = []
        bbox_widths: List[float] = []
        bbox_heights: List[float] = []
        aspect_ratios: List[float] = []

        for img in self.dataset.images:
            for bbox in img.bboxes:
                area = bbox.width * bbox.height
                bbox_areas.append(area)
                bbox_widths.append(bbox.width)
                bbox_heights.append(bbox.height)
                if bbox.height > 0:
                    aspect_ratios.append(bbox.width / bbox.height)

        if not bbox_areas:
            return {
                "average_area": 0,
                "average_width": 0,
                "average_height": 0,
                "average_aspect_ratio": 0,
                "min_area": 0,
                "max_area": 0
            }

        return {
            "average_area": sum(bbox_areas) / len(bbox_areas),
            "average_width": sum(bbox_widths) / len(bbox_widths),
            "average_height": sum(bbox_heights) / len(bbox_heights),
            "average_aspect_ratio": sum(aspect_ratios) / len(aspect_ratios),
            "min_area": min(bbox_areas),
            "max_area": max(bbox_areas)
        }

    def get_image_size_statistics(self) -> Dict[str, Any]:
        """
        获取图像尺寸统计
        
        Returns:
            图像尺寸统计字典
        """
        widths: List[int] = []
        heights: List[int] = []

        for img in self.dataset.images:
            if img.width > 0 and img.height > 0:
                widths.append(img.width)
                heights.append(img.height)

        if not widths:
            return {
                "average_width": 0,
                "average_height": 0,
                "min_width": 0,
                "max_width": 0,
                "min_height": 0,
                "max_height": 0
            }

        return {
            "average_width": sum(widths) / len(widths),
            "average_height": sum(heights) / len(heights),
            "min_width": min(widths),
            "max_width": max(widths),
            "min_height": min(heights),
            "max_height": max(heights)
        }

    def get_annotations_per_image(self) -> Dict[str, Any]:
        """
        获取每张图像的标注数量统计
        
        Returns:
            标注数量统计字典
        """
        anno_counts: List[int] = [len(img.bboxes) for img in self.dataset.images]

        if not anno_counts:
            return {
                "average": 0,
                "min": 0,
                "max": 0,
                "images_without_annotations": 0
            }

        return {
            "average": sum(anno_counts) / len(anno_counts),
            "min": min(anno_counts),
            "max": max(anno_counts),
            "images_without_annotations": sum(1 for c in anno_counts if c == 0)
        }

    def get_full_statistics(self) -> Dict[str, Any]:
        """
        获取完整统计信息
        
        Returns:
            包含所有统计信息的字典
        """
        return {
            "basic": self.get_basic_info(),
            "classes": self.get_class_statistics(),
            "splits": self.get_split_statistics(),
            "bounding_boxes": self.get_bbox_statistics(),
            "image_sizes": self.get_image_size_statistics(),
            "annotations_per_image": self.get_annotations_per_image()
        }

    def export_statistics(self, output_path: str, format: str = "json") -> str:
        """
        导出统计信息到文件
        
        Args:
            output_path: 输出文件路径
            format: 输出格式 (json/csv)
            
        Returns:
            输出文件路径
        """
        stats = self.get_full_statistics()
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if format.lower() == "json":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
        elif format.lower() == "csv":
            # 简化的CSV导出
            import csv
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Metric", "Value"])
                writer.writerow(["Total Images", stats["basic"]["total_images"]])
                writer.writerow(["Total Annotations", stats["basic"]["total_annotations"]])
                writer.writerow(["Num Classes", stats["basic"]["num_classes"]])
                for cls, count in stats["classes"]["distribution"].items():
                    writer.writerow([f"Class {cls}", count])

        return str(output_file)


# 便捷函数

def parse_dataset(dataset_path: str, format_type: Union[str, DatasetFormat]) -> DatasetInfo:
    """
    便捷函数：解析数据集
    
    Args:
        dataset_path: 数据集路径
        format_type: 数据集格式字符串或枚举
        
    Returns:
        DatasetInfo对象
        
    示例:
        >>> dataset = parse_dataset("/path/to/yolo", "yolo")
    """
    if isinstance(format_type, str):
        format_type = DatasetFormat(format_type.lower())
    
    converter = DatasetConverter()
    return converter.parse(dataset_path, format_type)


async def parse_dataset_async(dataset_path: str, format_type: Union[str, DatasetFormat]) -> DatasetInfo:
    """
    便捷函数：异步解析数据集
    
    Args:
        dataset_path: 数据集路径
        format_type: 数据集格式字符串或枚举
        
    Returns:
        DatasetInfo对象
    """
    if isinstance(format_type, str):
        format_type = DatasetFormat(format_type.lower())
    
    converter = DatasetConverter()
    return await converter.parse_async(dataset_path, format_type)


def convert_dataset(
    source_path: str, 
    source_format: Union[str, DatasetFormat],
    target_path: str,
    target_format: Union[str, DatasetFormat]
) -> str:
    """
    便捷函数：转换数据集格式
    
    Args:
        source_path: 源数据集路径
        source_format: 源格式
        target_path: 目标路径
        target_format: 目标格式
        
    Returns:
        输出目录路径
        
    示例:
        >>> convert_dataset("/path/to/yolo", "yolo", "/path/to/coco", "coco")
    """
    if isinstance(source_format, str):
        source_format = DatasetFormat(source_format.lower())
    if isinstance(target_format, str):
        target_format = DatasetFormat(target_format.lower())

    converter = DatasetConverter()
    dataset = converter.parse(source_path, source_format)

    if target_format == DatasetFormat.YOLO:
        return converter.to_yolo(dataset, target_path)
    elif target_format == DatasetFormat.COCO:
        return converter.to_coco(dataset, target_path)
    elif target_format == DatasetFormat.VOC:
        return converter.to_voc(dataset, target_path)
    else:
        raise InvalidFormatError(f"不支持的目标格式: {target_format}")


async def convert_dataset_async(
    source_path: str,
    source_format: Union[str, DatasetFormat],
    target_path: str,
    target_format: Union[str, DatasetFormat]
) -> str:
    """
    便捷函数：异步转换数据集格式
    
    Args:
        source_path: 源数据集路径
        source_format: 源格式
        target_path: 目标路径
        target_format: 目标格式
        
    Returns:
        输出目录路径
    """
    if isinstance(source_format, str):
        source_format = DatasetFormat(source_format.lower())
    if isinstance(target_format, str):
        target_format = DatasetFormat(target_format.lower())

    converter = DatasetConverter()
    dataset = await converter.parse_async(source_path, source_format)

    if target_format == DatasetFormat.YOLO:
        return await converter.to_yolo_async(dataset, target_path)
    elif target_format == DatasetFormat.COCO:
        return await converter.to_coco_async(dataset, target_path)
    elif target_format == DatasetFormat.VOC:
        return await converter.to_voc_async(dataset, target_path)
    else:
        raise InvalidFormatError(f"不支持的目标格式: {target_format}")



class DatasetAnalyzer:
    """
    数据集分析器
    
    提供数据集统计、标签分析、预览等功能。
    """
    
    def __init__(self, dataset_path: str, format: str = "yolo"):
        """
        初始化分析器
        
        Args:
            dataset_path: 数据集根目录路径
            format: 数据集格式 (yolo/coco/voc)
        """
        self.dataset_path = Path(dataset_path)
        self.format = format.lower()
        self._parser = None
        self._dataset_info = None
    
    def _get_parser(self, max_images: Optional[int] = None) -> BaseParser:
        """
        获取对应格式的解析器
        
        Args:
            max_images: 最大解析图像数量（None表示不限制）
            
        Returns:
            BaseParser: 对应格式的解析器实例
        """
        if self._parser is None or getattr(self._parser, 'max_images', None) != max_images:
            if self.format == "yolo":
                self._parser = YOLOParser(str(self.dataset_path), max_images=max_images)
            elif self.format == "coco":
                self._parser = COCOParser(str(self.dataset_path), max_images=max_images)
            elif self.format == "voc":
                self._parser = VOCParser(str(self.dataset_path), max_images=max_images)
            else:
                raise InvalidFormatError(f"不支持的格式: {self.format}")
        return self._parser
    
    def analyze_labels(self) -> Dict[str, Any]:
        """
        分析数据集标签
        
        Returns:
            {
                "class_names": ["defect1", "defect2", ...],
                "class_count": 5,
                "annotations_per_class": {
                    "defect1": 150,
                    "defect2": 230,
                    ...
                },
                "images_per_class": {
                    "defect1": 120,
                    "defect2": 180,
                    ...
                },
                "yaml_config": {...}  # 如果存在data.yaml
            }
        """
        # 尝试从YAML读取类别名称
        yaml_config = self._load_yaml_config()
        class_names = yaml_config.get("names", []) if yaml_config else []
        logger.info(f"DatasetAnalyzer 从YAML读取类别名称: {class_names}, yaml_config={yaml_config is not None}")
        
        # 解析数据集获取详细统计
        parser = self._get_parser()
        
        # 如果从YAML读取了类别名称，同步到parser
        if class_names:
            parser.class_names = class_names
            logger.info(f"已将YAML类别名称同步到parser: {class_names}")
        else:
            logger.warning(f"未从YAML读取到类别名称，路径: {self.dataset_path}")
        
        try:
            logger.info(f"开始调用 parser.parse()...")
            dataset_info = parser.parse()
            self._dataset_info = dataset_info
            logger.info(f"parser.parse() 成功，图像数量: {len(dataset_info.images)}")
            
            # 统计每个类别的标注数量
            annotations_per_class: Dict[str, int] = {}
            images_per_class: Dict[str, int] = {}
            
            for image in dataset_info.images:
                classes_in_image = set()
                for bbox in image.bboxes:
                    class_name = bbox.class_name or f"class_{bbox.class_id}"
                    
                    # 如果提供了class_names，使用映射的名称
                    if bbox.class_id < len(class_names):
                        class_name = class_names[bbox.class_id]
                    
                    annotations_per_class[class_name] = annotations_per_class.get(class_name, 0) + 1
                    classes_in_image.add(class_name)
                
                # 统计包含每个类别的图像数量
                for class_name in classes_in_image:
                    images_per_class[class_name] = images_per_class.get(class_name, 0) + 1
            
            # 如果没有从YAML获取到类别名称，使用发现的类别
            if not class_names:
                class_names = sorted(annotations_per_class.keys())
            
            return {
                "class_names": class_names,
                "class_count": len(class_names),
                "annotations_per_class": annotations_per_class,
                "images_per_class": images_per_class,
                "total_annotations": sum(annotations_per_class.values()),
                "yaml_config": yaml_config
            }
            
        except Exception as e:
            logger.error(f"分析数据集失败: {e}", exc_info=True)
            return {
                "class_names": class_names,
                "class_count": len(class_names),
                "annotations_per_class": {},
                "images_per_class": {},
                "total_annotations": 0,
                "yaml_config": yaml_config,
                "error": str(e)
            }
    
    def _load_yaml_config(self) -> Optional[Dict]:
        """加载YAML配置文件
        
        尝试查找多种可能的YAML文件名:
        - data.yaml (YOLO标准)
        - dataset.yaml
        - config.yaml
        
        会在根目录和第一层子目录中查找
        """
        yaml_names = ["data.yaml", "dataset.yaml", "config.yaml"]
        logger.info(f"开始查找YAML文件，路径: {self.dataset_path}")
        
        # 首先在根目录查找
        for yaml_name in yaml_names:
            yaml_file = self.dataset_path / yaml_name
            logger.debug(f"检查根目录YAML: {yaml_file}, 存在: {yaml_file.exists()}")
            if yaml_file.exists():
                try:
                    import yaml
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                        logger.info(f"成功加载YAML配置: {yaml_file}")
                        return config
                except Exception as e:
                    logger.warning(f"解析{yaml_name}失败: {e}")
        
        # 如果在根目录没找到，在第一层子目录中查找
        # 这适用于数据集打包时有一个根目录包裹的情况
        logger.info(f"在根目录未找到YAML，开始扫描子目录...")
        try:
            for subdir in self.dataset_path.iterdir():
                if subdir.is_dir():
                    logger.debug(f"检查子目录: {subdir.name}")
                    for yaml_name in yaml_names:
                        yaml_file = subdir / yaml_name
                        if yaml_file.exists():
                            try:
                                import yaml
                                with open(yaml_file, 'r', encoding='utf-8') as f:
                                    config = yaml.safe_load(f)
                                    logger.info(f"成功加载YAML配置: {yaml_file}")
                                    return config
                            except Exception as e:
                                logger.warning(f"解析{yaml_file}失败: {e}")
        except Exception as e:
            logger.warning(f"扫描子目录查找YAML失败: {e}")
        
        logger.warning(f"未找到任何YAML配置文件")
        return None
        
        return None
    
    def get_preview_images(self, count: int = 20) -> List[Dict[str, Any]]:
        """
        获取预览图片列表
        
        优化：只解析需要数量的图片，而不是整个数据集
        
        Args:
            count: 返回的图片数量
            
        Returns:
            [
                {
                    "id": "image_id",
                    "filename": "image.jpg",
                    "filepath": "/path/to/image.jpg",
                    "width": 640,
                    "height": 480,
                    "split": "train",
                    "annotation_count": 5,
                    "bboxes": [...]
                },
                ...
            ]
        """
        # 如果已有缓存的数据集信息且数量足够，直接使用
        if self._dataset_info is not None and len(self._dataset_info.images) >= count:
            logger.debug(f"使用缓存的数据集信息，共 {len(self._dataset_info.images)} 张图像")
        else:
            # 否则，使用限制数量的解析器重新解析
            try:
                logger.info(f"开始解析数据集获取预览图片，限制数量: {count}")
                parser = self._get_parser(max_images=count)
                self._dataset_info = parser.parse()
                logger.info(f"解析完成，获取 {len(self._dataset_info.images)} 张图像")
            except Exception as e:
                logger.error(f"解析数据集失败: {e}")
                return []
        
        # 返回前N张图片的信息
        preview = []
        for image in self._dataset_info.images[:count]:
            preview.append({
                "id": image.id,
                "filename": image.filename,
                "filepath": image.filepath,
                "width": image.width,
                "height": image.height,
                "split": image.split,
                "annotation_count": len(image.bboxes),
                "bboxes": [
                    {
                        "x": bbox.x,
                        "y": bbox.y,
                        "width": bbox.width,
                        "height": bbox.height,
                        "class_id": bbox.class_id,
                        "class_name": bbox.class_name
                    }
                    for bbox in image.bboxes
                ]
            })
        
        return preview
    
    def update_class_names(self, class_names: List[str]) -> bool:
        """
        更新类别名称
        
        Args:
            class_names: 新的类别名称列表
            
        Returns:
            是否成功
        """
        try:
            import yaml
            yaml_file = self.dataset_path / "data.yaml"
            
            # 读取现有配置或创建新配置
            config = {}
            if yaml_file.exists():
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            
            # 更新类别名称
            config["names"] = class_names
            
            # 如果没有path和train/val，添加默认值
            if "path" not in config:
                config["path"] = "."
            if "train" not in config:
                config["train"] = "images/train"
            if "val" not in config:
                config["val"] = "images/val"
            
            # 保存YAML文件
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, sort_keys=False)
            
            return True
            
        except Exception as e:
            logger.error(f"更新类别名称失败: {e}")
            return False
    
    def save_yaml_config(self, config: Dict[str, Any]) -> bool:
        """
        保存YAML配置
        
        Args:
            config: YAML配置字典
            
        Returns:
            是否成功
        """
        try:
            import yaml
            yaml_file = self.dataset_path / "data.yaml"
            
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, sort_keys=False)
            
            return True
            
        except Exception as e:
            logger.error(f"保存YAML配置失败: {e}")
            return False


# 便捷函数
def analyze_dataset_labels(dataset_path: str, format: str = "yolo") -> Dict[str, Any]:
    """
    便捷函数：分析数据集标签
    
    Args:
        dataset_path: 数据集路径
        format: 数据集格式
        
    Returns:
        标签分析结果
    """
    analyzer = DatasetAnalyzer(dataset_path, format)
    return analyzer.analyze_labels()


def get_dataset_preview(dataset_path: str, format: str = "yolo", count: int = 20) -> List[Dict[str, Any]]:
    """
    便捷函数：获取数据集预览
    
    Args:
        dataset_path: 数据集路径
        format: 数据集格式
        count: 预览图片数量
        
    Returns:
        预览图片列表
    """
    analyzer = DatasetAnalyzer(dataset_path, format)
    return analyzer.get_preview_images(count)


async def analyze_dataset_labels_async(dataset_path: str, format: str = "yolo") -> Dict[str, Any]:
    """异步版本：分析数据集标签"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_dataset_labels, dataset_path, format)


async def get_dataset_preview_async(dataset_path: str, format: str = "yolo", count: int = 20) -> List[Dict[str, Any]]:
    """异步版本：获取数据集预览"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_dataset_preview, dataset_path, format, count)
