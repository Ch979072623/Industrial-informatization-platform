"""
数据集处理任务模块

提供数据集上传处理、划分、格式转换等异步任务。
"""
import logging
import os
import zipfile
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from celery import shared_task
from PIL import Image
import random

logger = logging.getLogger(__name__)

# 支持的图像格式
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}

# 支持的标注格式
SUPPORTED_ANNOTATION_FORMATS = {'YOLO', 'COCO', 'VOC'}


@shared_task(bind=True, max_retries=3)
def process_dataset_upload(
    self,
    dataset_id: str,
    zip_path: str,
    extract_path: str,
    production_line_id: str,
    created_by: str
) -> Dict[str, Any]:
    """
    处理数据集上传任务
    
    解压上传的ZIP文件，解析数据集结构，检测格式，生成缩略图，
    并更新数据库记录。
    
    Args:
        self: Celery Task 实例
        dataset_id: 数据集ID
        zip_path: 上传的ZIP文件路径
        extract_path: 解压目标路径
        production_line_id: 所属产线ID
        created_by: 创建者ID
        
    Returns:
        处理结果，包含以下字段：
        - dataset_id: 数据集ID
        - status: 处理状态 (completed/failed)
        - format: 检测到的数据格式
        - total_images: 图像总数
        - class_names: 类别名称列表
        - message: 处理结果消息
        
    Raises:
        Exception: 处理失败时会重试，超过最大重试次数后抛出异常
    """
    logger.info(f"开始处理数据集上传: dataset_id={dataset_id}, zip_path={zip_path}")
    
    try:
        # 更新任务状态：开始解压
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 10,
                "stage": "extracting",
                "message": "正在解压数据集文件..."
            }
        )
        
        # 1. 解压ZIP文件
        extracted_files = _extract_zip_file(zip_path, extract_path)
        logger.info(f"数据集解压完成: {len(extracted_files)} 个文件")
        
        # 更新任务状态：检测格式
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 30,
                "stage": "detecting_format",
                "message": "正在检测数据集格式..."
            }
        )
        
        # 2. 检测数据集格式
        detected_format = _detect_dataset_format(extract_path)
        if detected_format not in SUPPORTED_ANNOTATION_FORMATS:
            raise ValueError(f"不支持的数据集格式: {detected_format}")
        logger.info(f"检测到数据集格式: {detected_format}")
        
        # 更新任务状态：解析标注
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 50,
                "stage": "parsing_annotations",
                "message": "正在解析标注文件..."
            }
        )
        
        # 3. 解析标注文件
        images_info, class_names = _parse_annotations(
            extract_path, 
            detected_format
        )
        total_images = len(images_info)
        logger.info(f"标注解析完成: {total_images} 张图像, {len(class_names)} 个类别")
        
        # 更新任务状态：生成缩略图
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 70,
                "stage": "generating_thumbnails",
                "message": "正在生成缩略图..."
            }
        )
        
        # 4. 生成缩略图
        thumbnail_dir = os.path.join(extract_path, 'thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        thumbnail_count = 0
        for img_info in images_info[:20]:  # 只为前20张图像生成缩略图
            try:
                _generate_thumbnail(
                    img_info['filepath'],
                    os.path.join(thumbnail_dir, f"thumb_{img_info['filename']}"),
                    size=(256, 256)
                )
                thumbnail_count += 1
            except Exception as e:
                logger.warning(f"生成缩略图失败 {img_info['filename']}: {e}")
        
        logger.info(f"缩略图生成完成: {thumbnail_count} 个")
        
        # 更新任务状态：更新数据库
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 90,
                "stage": "updating_database",
                "message": "正在更新数据库记录..."
            }
        )
        
        # 5. 更新数据库记录 (TODO: 实际项目中需要调用数据库服务)
        # 这里模拟数据库更新
        logger.info(f"更新数据集记录: dataset_id={dataset_id}")
        
        # 清理原始ZIP文件
        if os.path.exists(zip_path):
            os.remove(zip_path)
            logger.info(f"清理ZIP文件: {zip_path}")
        
        # 任务完成
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 100,
                "stage": "completed",
                "message": "数据集处理完成"
            }
        )
        
        result = {
            "dataset_id": dataset_id,
            "status": "completed",
            "format": detected_format,
            "total_images": total_images,
            "class_names": class_names,
            "thumbnail_count": thumbnail_count,
            "extract_path": extract_path,
            "message": "数据集上传处理成功"
        }
        
        logger.info(f"数据集上传处理完成: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"数据集上传处理失败: {exc}", exc_info=True)
        
        # 清理临时文件
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(extract_path):
                shutil.rmtree(extract_path)
        except Exception as cleanup_exc:
            logger.warning(f"清理临时文件失败: {cleanup_exc}")
        
        # 重试任务
        self.retry(exc=exc, countdown=60)
        raise


@shared_task(bind=True, max_retries=3)
def split_dataset(
    self,
    dataset_id: str,
    dataset_path: str,
    split_ratio: Dict[str, float],
    random_seed: Optional[int] = None
) -> Dict[str, Any]:
    """
    执行数据集划分任务
    
    根据指定的比例将数据集划分为训练集、验证集和测试集。
    
    Args:
        self: Celery Task 实例
        dataset_id: 数据集ID
        dataset_path: 数据集路径
        split_ratio: 划分比例，例如 {"train": 0.7, "val": 0.2, "test": 0.1}
        random_seed: 随机种子，用于保证划分结果可复现
        
    Returns:
        划分结果，包含以下字段：
        - dataset_id: 数据集ID
        - status: 处理状态
        - split_stats: 各划分集合的统计信息
        - message: 处理结果消息
        
    Raises:
        ValueError: 划分比例无效
        Exception: 处理失败时会重试
    """
    logger.info(f"开始数据集划分: dataset_id={dataset_id}, ratio={split_ratio}")
    
    try:
        # 验证划分比例
        total_ratio = sum(split_ratio.values())
        if not 0.99 <= total_ratio <= 1.01:  # 允许少量浮点误差
            raise ValueError(f"划分比例总和必须等于1.0，当前为: {total_ratio}")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 20,
                "stage": "scanning_images",
                "message": "正在扫描图像文件..."
            }
        )
        
        # 1. 扫描所有图像文件
        image_files = _scan_image_files(dataset_path)
        if not image_files:
            raise ValueError(f"在路径 {dataset_path} 中未找到图像文件")
        
        total = len(image_files)
        logger.info(f"扫描到 {total} 张图像")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 40,
                "stage": "shuffling",
                "message": "正在随机打乱数据..."
            }
        )
        
        # 2. 随机打乱
        if random_seed is not None:
            random.seed(random_seed)
        random.shuffle(image_files)
        
        # 3. 计算各集合数量
        train_count = int(total * split_ratio.get('train', 0.7))
        val_count = int(total * split_ratio.get('val', 0.2))
        # 测试集取剩余部分，避免舍入误差
        test_count = total - train_count - val_count
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 60,
                "stage": "splitting",
                "message": f"正在划分数据: 训练集({train_count}), 验证集({val_count}), 测试集({test_count})..."
            }
        )
        
        # 4. 划分数据集
        splits = {
            'train': image_files[:train_count],
            'val': image_files[train_count:train_count + val_count],
            'test': image_files[train_count + val_count:]
        }
        
        # 5. 创建划分后的目录结构并移动文件
        split_stats = {}
        for split_name, files in splits.items():
            if not files:
                continue
                
            split_dir = os.path.join(dataset_path, split_name)
            os.makedirs(split_dir, exist_ok=True)
            os.makedirs(os.path.join(split_dir, 'images'), exist_ok=True)
            os.makedirs(os.path.join(split_dir, 'labels'), exist_ok=True)
            
            # 移动文件到对应目录
            for img_path in files:
                img_name = os.path.basename(img_path)
                shutil.copy2(
                    img_path,
                    os.path.join(split_dir, 'images', img_name)
                )
                # 同时复制对应的标注文件
                _copy_annotation_file(img_path, split_dir)
            
            split_stats[split_name] = len(files)
            logger.info(f"{split_name} 集合: {len(files)} 个文件")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 90,
                "stage": "saving_config",
                "message": "正在保存划分配置..."
            }
        )
        
        # 6. 保存划分配置
        split_config = {
            "dataset_id": dataset_id,
            "split_ratio": split_ratio,
            "random_seed": random_seed,
            "split_stats": split_stats,
            "total_images": total
        }
        config_path = os.path.join(dataset_path, 'split_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(split_config, f, ensure_ascii=False, indent=2)
        
        # 任务完成
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 100,
                "stage": "completed",
                "message": "数据集划分完成"
            }
        )
        
        result = {
            "dataset_id": dataset_id,
            "status": "completed",
            "split_stats": split_stats,
            "split_ratio": split_ratio,
            "config_path": config_path,
            "message": "数据集划分成功"
        }
        
        logger.info(f"数据集划分完成: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"数据集划分失败: {exc}", exc_info=True)
        self.retry(exc=exc, countdown=60)
        raise


@shared_task(bind=True, max_retries=3)
def convert_dataset_format(
    self,
    dataset_id: str,
    source_path: str,
    target_path: str,
    source_format: str,
    target_format: str,
    class_names: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    转换数据集格式任务
    
    将数据集从一种标注格式转换为另一种格式，支持 YOLO、COCO、VOC 之间的转换。
    
    Args:
        self: Celery Task 实例
        dataset_id: 数据集ID
        source_path: 源数据集路径
        target_path: 目标数据集路径
        source_format: 源格式 (YOLO/COCO/VOC)
        target_format: 目标格式 (YOLO/COCO/VOC)
        class_names: 类别名称列表，某些格式转换时需要
        
    Returns:
        转换结果，包含以下字段：
        - dataset_id: 数据集ID
        - status: 处理状态
        - converted_images: 转换的图像数量
        - target_format: 目标格式
        - message: 处理结果消息
        
    Raises:
        ValueError: 格式不支持或转换参数无效
        Exception: 处理失败时会重试
    """
    logger.info(
        f"开始格式转换: dataset_id={dataset_id}, "
        f"{source_format} -> {target_format}"
    )
    
    try:
        # 验证格式
        if source_format not in SUPPORTED_ANNOTATION_FORMATS:
            raise ValueError(f"不支持的源格式: {source_format}")
        if target_format not in SUPPORTED_ANNOTATION_FORMATS:
            raise ValueError(f"不支持的目标格式: {target_format}")
        if source_format == target_format:
            raise ValueError("源格式和目标格式不能相同")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 10,
                "stage": "preparing",
                "message": f"准备转换: {source_format} -> {target_format}..."
            }
        )
        
        # 创建目标目录
        os.makedirs(target_path, exist_ok=True)
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 30,
                "stage": "loading_source",
                "message": "正在加载源数据集..."
            }
        )
        
        # 1. 加载源数据集的标注
        annotations = _load_annotations(source_path, source_format, class_names)
        total = len(annotations)
        logger.info(f"加载了 {total} 个标注文件")
        
        if total == 0:
            raise ValueError("源数据集中未找到有效的标注文件")
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 50,
                "stage": "converting",
                "message": f"正在转换格式 (0/{total})..."
            }
        )
        
        # 2. 执行格式转换
        converted_count = 0
        for idx, (img_path, anno_data) in enumerate(annotations.items()):
            try:
                # 复制图像文件
                img_name = os.path.basename(img_path)
                target_img_path = os.path.join(target_path, img_name)
                shutil.copy2(img_path, target_img_path)
                
                # 转换标注格式
                converted_anno = _convert_annotation(
                    anno_data,
                    source_format,
                    target_format,
                    img_path
                )
                
                # 保存转换后的标注
                _save_annotation(
                    converted_anno,
                    target_path,
                    img_name,
                    target_format
                )
                
                converted_count += 1
                
                # 每10个文件更新一次进度
                if (idx + 1) % 10 == 0:
                    progress = 50 + int((idx + 1) / total * 40)
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "progress": progress,
                            "stage": "converting",
                            "message": f"正在转换格式 ({idx + 1}/{total})..."
                        }
                    )
                    
            except Exception as e:
                logger.warning(f"转换文件失败 {img_path}: {e}")
                continue
        
        # 更新任务状态
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 95,
                "stage": "saving_metadata",
                "message": "正在保存元数据..."
            }
        )
        
        # 3. 保存格式转换后的元数据
        metadata = {
            "dataset_id": dataset_id,
            "source_format": source_format,
            "target_format": target_format,
            "converted_images": converted_count,
            "class_names": class_names or []
        }
        metadata_path = os.path.join(target_path, 'convert_metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 任务完成
        self.update_state(
            state="PROGRESS",
            meta={
                "progress": 100,
                "stage": "completed",
                "message": "格式转换完成"
            }
        )
        
        result = {
            "dataset_id": dataset_id,
            "status": "completed",
            "source_format": source_format,
            "target_format": target_format,
            "converted_images": converted_count,
            "target_path": target_path,
            "message": f"格式转换成功: {source_format} -> {target_format}"
        }
        
        logger.info(f"格式转换完成: {result}")
        return result
        
    except Exception as exc:
        logger.error(f"格式转换失败: {exc}", exc_info=True)
        # 清理目标目录
        try:
            if os.path.exists(target_path):
                shutil.rmtree(target_path)
        except Exception as cleanup_exc:
            logger.warning(f"清理目标目录失败: {cleanup_exc}")
        
        self.retry(exc=exc, countdown=60)
        raise


# ==================== 辅助函数 ====================

def _extract_zip_file(zip_path: str, extract_path: str) -> List[str]:
    """
    解压ZIP文件
    
    Args:
        zip_path: ZIP文件路径
        extract_path: 解压目标路径
        
    Returns:
        解压后的文件列表
    """
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"ZIP文件不存在: {zip_path}")
    
    os.makedirs(extract_path, exist_ok=True)
    extracted_files = []
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # 安全检查：防止Zip Slip漏洞
        for member in zip_ref.namelist():
            member_path = os.path.join(extract_path, member)
            if not os.path.commonpath([extract_path, member_path]) == extract_path:
                raise ValueError(f"ZIP文件包含恶意路径: {member}")
        
        zip_ref.extractall(extract_path)
        extracted_files = zip_ref.namelist()
    
    return extracted_files


def _detect_dataset_format(dataset_path: str) -> str:
    """
    检测数据集格式
    
    Args:
        dataset_path: 数据集路径
        
    Returns:
        检测到的格式 (YOLO/COCO/VOC)
    """
    # 检查YOLO格式特征
    yaml_files = list(Path(dataset_path).glob('*.yaml'))
    if yaml_files:
        return 'YOLO'
    
    # 检查是否有YOLO格式的标注文件
    txt_files = list(Path(dataset_path).rglob('*.txt'))
    if txt_files:
        # 检查第一个txt文件是否是YOLO格式
        try:
            with open(txt_files[0], 'r') as f:
                first_line = f.readline().strip()
                parts = first_line.split()
                if len(parts) == 5:  # class_id x_center y_center width height
                    return 'YOLO'
        except:
            pass
    
    # 检查COCO格式特征
    json_files = list(Path(dataset_path).glob('*.json'))
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                if 'images' in data and 'annotations' in data:
                    return 'COCO'
        except:
            pass
    
    # 检查VOC格式特征
    xml_files = list(Path(dataset_path).rglob('*.xml'))
    if xml_files:
        try:
            with open(xml_files[0], 'r') as f:
                content = f.read()
                if '<annotation>' in content and '<object>' in content:
                    return 'VOC'
        except:
            pass
    
    # 默认返回YOLO
    return 'YOLO'


def _parse_annotations(
    dataset_path: str,
    format_type: str
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    解析标注文件
    
    Args:
        dataset_path: 数据集路径
        format_type: 标注格式
        
    Returns:
        (图像信息列表, 类别名称列表)
    """
    images_info = []
    class_names = set()
    
    # 扫描图像文件
    for root, _, files in os.walk(dataset_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in SUPPORTED_IMAGE_FORMATS:
                img_path = os.path.join(root, file)
                
                # 获取图像尺寸
                try:
                    with Image.open(img_path) as img:
                        width, height = img.size
                except:
                    width, height = None, None
                
                # 查找对应的标注文件
                anno_path = _find_annotation_file(img_path, format_type)
                
                # 解析类别信息
                if anno_path and os.path.exists(anno_path):
                    img_classes = _extract_classes_from_annotation(
                        anno_path, format_type
                    )
                    class_names.update(img_classes)
                
                images_info.append({
                    'filename': file,
                    'filepath': img_path,
                    'width': width,
                    'height': height,
                    'annotation_path': anno_path
                })
    
    return images_info, sorted(list(class_names))


def _find_annotation_file(img_path: str, format_type: str) -> Optional[str]:
    """查找图像对应的标注文件"""
    base_name = os.path.splitext(img_path)[0]
    
    if format_type == 'YOLO':
        anno_path = base_name + '.txt'
        if os.path.exists(anno_path):
            return anno_path
        # 检查labels目录
        dir_name = os.path.dirname(img_path)
        labels_dir = os.path.join(os.path.dirname(dir_name), 'labels')
        if os.path.exists(labels_dir):
            anno_path = os.path.join(labels_dir, os.path.basename(base_name) + '.txt')
            if os.path.exists(anno_path):
                return anno_path
    
    elif format_type == 'VOC':
        anno_path = base_name + '.xml'
        if os.path.exists(anno_path):
            return anno_path
        # 检查Annotations目录
        dir_name = os.path.dirname(img_path)
        anno_dir = os.path.join(os.path.dirname(dir_name), 'Annotations')
        if os.path.exists(anno_dir):
            anno_path = os.path.join(anno_dir, os.path.basename(base_name) + '.xml')
            if os.path.exists(anno_path):
                return anno_path
    
    return None


def _extract_classes_from_annotation(
    anno_path: str,
    format_type: str
) -> List[str]:
    """从标注文件中提取类别名称"""
    classes = []
    
    try:
        if format_type == 'YOLO':
            with open(anno_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        class_id = int(parts[0])
                        classes.append(f"class_{class_id}")
        
        elif format_type == 'VOC':
            import xml.etree.ElementTree as ET
            tree = ET.parse(anno_path)
            root = tree.getroot()
            for obj in root.findall('object'):
                name = obj.find('name')
                if name is not None:
                    classes.append(name.text)
    
    except Exception as e:
        logger.warning(f"解析标注文件失败 {anno_path}: {e}")
    
    return classes


def _generate_thumbnail(
    img_path: str,
    thumb_path: str,
    size: Tuple[int, int] = (256, 256)
) -> None:
    """
    生成缩略图
    
    Args:
        img_path: 原始图像路径
        thumb_path: 缩略图保存路径
        size: 缩略图尺寸
    """
    with Image.open(img_path) as img:
        # 转换为RGB模式（处理RGBA、P等模式）
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # 使用高质量缩放
        img.thumbnail(size, Image.Resampling.LANCZOS)
        img.save(thumb_path, 'JPEG', quality=85)


def _scan_image_files(dataset_path: str) -> List[str]:
    """扫描目录中的所有图像文件"""
    image_files = []
    for root, _, files in os.walk(dataset_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in SUPPORTED_IMAGE_FORMATS:
                image_files.append(os.path.join(root, file))
    return image_files


def _copy_annotation_file(img_path: str, target_dir: str) -> None:
    """复制图像对应的标注文件"""
    base_name = os.path.splitext(os.path.basename(img_path))[0]
    img_dir = os.path.dirname(img_path)
    
    # 尝试复制YOLO格式的txt文件
    txt_path = os.path.join(img_dir, base_name + '.txt')
    if os.path.exists(txt_path):
        shutil.copy2(
            txt_path,
            os.path.join(target_dir, 'labels', base_name + '.txt')
        )
        return
    
    # 尝试从labels目录复制
    labels_dir = os.path.join(os.path.dirname(img_dir), 'labels')
    if os.path.exists(labels_dir):
        txt_path = os.path.join(labels_dir, base_name + '.txt')
        if os.path.exists(txt_path):
            shutil.copy2(
                txt_path,
                os.path.join(target_dir, 'labels', base_name + '.txt')
            )


def _load_annotations(
    source_path: str,
    source_format: str,
    class_names: Optional[List[str]]
) -> Dict[str, Dict[str, Any]]:
    """加载源数据集的标注信息"""
    annotations = {}
    
    image_files = _scan_image_files(source_path)
    
    for img_path in image_files:
        anno_path = _find_annotation_file(img_path, source_format)
        
        if anno_path and os.path.exists(anno_path):
            try:
                anno_data = _parse_annotation_file(anno_path, source_format)
                annotations[img_path] = {
                    'annotation': anno_data,
                    'class_names': class_names
                }
            except Exception as e:
                logger.warning(f"解析标注文件失败 {anno_path}: {e}")
        else:
            # 没有标注文件也保留图像
            annotations[img_path] = {'annotation': [], 'class_names': class_names}
    
    return annotations


def _parse_annotation_file(anno_path: str, format_type: str) -> List[Dict[str, Any]]:
    """解析单个标注文件"""
    annotations = []
    
    if format_type == 'YOLO':
        with open(anno_path, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    annotations.append({
                        'class_id': int(parts[0]),
                        'bbox': [float(x) for x in parts[1:5]]
                    })
    
    elif format_type == 'VOC':
        import xml.etree.ElementTree as ET
        tree = ET.parse(anno_path)
        root = tree.getroot()
        
        size = root.find('size')
        img_width = int(size.find('width').text) if size is not None else 1
        img_height = int(size.find('height').text) if size is not None else 1
        
        for obj in root.findall('object'):
            name = obj.find('name')
            bndbox = obj.find('bndbox')
            
            if name is not None and bndbox is not None:
                xmin = float(bndbox.find('xmin').text) / img_width
                ymin = float(bndbox.find('ymin').text) / img_height
                xmax = float(bndbox.find('xmax').text) / img_width
                ymax = float(bndbox.find('ymax').text) / img_height
                
                annotations.append({
                    'class_name': name.text,
                    'bbox': [
                        (xmin + xmax) / 2,  # x_center
                        (ymin + ymax) / 2,  # y_center
                        xmax - xmin,        # width
                        ymax - ymin         # height
                    ]
                })
    
    return annotations


def _convert_annotation(
    anno_data: Dict[str, Any],
    source_format: str,
    target_format: str,
    img_path: str
) -> Dict[str, Any]:
    """转换单个标注的格式"""
    # 目前支持的转换：YOLO <-> VOC (都使用归一化坐标)
    # 实际项目中可能需要更复杂的转换逻辑
    
    annotations = anno_data.get('annotation', [])
    class_names = anno_data.get('class_names', [])
    
    converted = []
    for anno in annotations:
        if target_format == 'YOLO':
            # 转换为YOLO格式
            if source_format == 'VOC':
                # VOC使用class_name，需要转换为class_id
                class_name = anno.get('class_name', '')
                if class_name in class_names:
                    class_id = class_names.index(class_name)
                else:
                    class_id = 0
                
                converted.append({
                    'class_id': class_id,
                    'bbox': anno.get('bbox', [0, 0, 0, 0])
                })
            else:
                converted.append(anno)
        
        elif target_format == 'VOC':
            # 转换为VOC格式
            if source_format == 'YOLO':
                class_id = anno.get('class_id', 0)
                if class_names and class_id < len(class_names):
                    class_name = class_names[class_id]
                else:
                    class_name = f"class_{class_id}"
                
                bbox = anno.get('bbox', [0, 0, 0, 0])
                x_center, y_center, width, height = bbox
                
                converted.append({
                    'class_name': class_name,
                    'bbox': [
                        x_center - width / 2,  # xmin
                        y_center - height / 2,  # ymin
                        x_center + width / 2,  # xmax
                        y_center + height / 2   # ymax
                    ]
                })
            else:
                converted.append(anno)
        
        else:
            converted.append(anno)
    
    return {'annotations': converted, 'class_names': class_names}


def _save_annotation(
    converted_anno: Dict[str, Any],
    target_path: str,
    img_name: str,
    target_format: str
) -> None:
    """保存转换后的标注文件"""
    base_name = os.path.splitext(img_name)[0]
    
    if target_format == 'YOLO':
        anno_path = os.path.join(target_path, base_name + '.txt')
        with open(anno_path, 'w') as f:
            for anno in converted_anno.get('annotations', []):
                bbox = anno.get('bbox', [0, 0, 0, 0])
                f.write(f"{anno.get('class_id', 0)} {' '.join(map(str, bbox))}\n")
    
    elif target_format == 'VOC':
        anno_path = os.path.join(target_path, base_name + '.xml')
        with open(anno_path, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<annotation>\n')
            f.write(f'  <filename>{img_name}</filename>\n')
            f.write('  <size>\n')
            f.write('    <width>0</width>\n')
            f.write('    <height>0</height>\n')
            f.write('    <depth>3</depth>\n')
            f.write('  </size>\n')
            
            for anno in converted_anno.get('annotations', []):
                bbox = anno.get('bbox', [0, 0, 0, 0])
                f.write('  <object>\n')
                f.write(f'    <name>{anno.get("class_name", "unknown")}</name>\n')
                f.write('    <bndbox>\n')
                f.write(f'      <xmin>{bbox[0]}</xmin>\n')
                f.write(f'      <ymin>{bbox[1]}</ymin>\n')
                f.write(f'      <xmax>{bbox[2]}</xmax>\n')
                f.write(f'      <ymax>{bbox[3]}</ymax>\n')
                f.write('    </bndbox>\n')
                f.write('  </object>\n')
            
            f.write('</annotation>\n')
