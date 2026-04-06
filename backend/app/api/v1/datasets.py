"""
数据集管理 API 路由
提供数据集的 CRUD、上传、划分、转换等功能
"""
import os
import shutil
import zipfile
import logging
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

from fastapi import (
    APIRouter, Depends, HTTPException, status,
    UploadFile, File, Form, Query, Response
)
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import get_db, get_current_user
from app.core.security import require_roles, TokenData
from app.core.config import settings
from app.models.dataset import Dataset, DatasetImage
from app.models.production_line import ProductionLine
from app.schemas.dataset import (
    DatasetCreate, DatasetResponse, DatasetUpdate,
    DatasetDetailResponse, DatasetImageResponse,
    LabelAnalysisResponse, DatasetPreviewResponse,
    UpdateLabelsRequest, UpdateLabelsResponse,
    DatasetCardInfoResponse, PreviewImageInfo,
    DatasetStatisticsResponse, DatasetStatisticsCreate,
    DatasetChartDataResponse, DatasetConvertRequest
)
from app.services.dataset_statistics_service import DatasetStatisticsService, DatasetStatisticsError
from app.utils.dataset_parser import DatasetAnalyzer
from app.schemas.common import APIResponse, PaginatedResponse, PaginationParams

router = APIRouter(prefix="/datasets", tags=["数据集管理"])

# 允许的数据集格式
ALLOWED_DATASET_FORMATS = ["YOLO", "COCO", "VOC"]
# 最大上传文件大小 (500MB)
MAX_DATASET_SIZE = 500 * 1024 * 1024


def check_admin_permission(current_user: TokenData) -> None:
    """检查管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要管理员权限，当前角色: {current_user.role}"
        )


def check_dataset_access(dataset: Dataset, current_user: TokenData) -> None:
    """
    检查数据集访问权限
    
    - 管理员：可以访问所有数据集
    - 普通用户：只能访问自己创建的数据集
    """
    if current_user.role != "admin" and dataset.created_by != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限访问此数据集"
        )


@router.post("/upload", response_model=APIResponse[DatasetResponse])
async def upload_dataset(
    name: str = Form(..., min_length=1, max_length=100, description="数据集名称"),
    description: Optional[str] = Form(None, description="数据集描述"),
    format: str = Form("auto", description="数据格式 (YOLO/COCO/VOC/auto)"),
    production_line_id: Optional[str] = Form(None, description="所属产线ID"),
    file: UploadFile = File(..., description="数据集ZIP文件"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DatasetResponse]:
    """
    上传数据集ZIP文件
    
    - 支持 ZIP 格式压缩包
    - 自动解压并解析数据集结构
    - 支持 YOLO/COCO/VOC 格式
    """
    # 权限检查
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要管理员权限，当前角色: {current_user.role}"
        )
    # 验证文件类型
    if not file.filename or not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 ZIP 格式的压缩文件"
        )
    
    # 验证格式（auto 表示自动检测）
    format_upper = format.upper()
    if format_upper != "AUTO" and format_upper not in ALLOWED_DATASET_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的数据格式: {format}，支持的格式: {', '.join(ALLOWED_DATASET_FORMATS)} 或 auto"
        )
    
    # 验证产线是否存在（如果提供了产线ID）
    if production_line_id:
        production_line_result = await db.execute(
            select(ProductionLine).where(ProductionLine.id == production_line_id)
        )
        production_line = production_line_result.scalar_one_or_none()
        if not production_line:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="所属产线不存在"
            )
    else:
        production_line = None
    
    # 检查数据集名称是否已存在
    existing_result = await db.execute(
        select(Dataset).where(Dataset.name == name)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"数据集名称 '{name}' 已存在"
        )
    
    # 创建数据集目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_dir = os.path.join(settings.upload_dir, "datasets", f"{name}_{timestamp}")
    os.makedirs(dataset_dir, exist_ok=True)
    
    try:
        # 保存上传的ZIP文件
        zip_path = os.path.join(dataset_dir, file.filename)
        with open(zip_path, "wb") as f:
            content = await file.read()
            # 检查文件大小
            if len(content) > MAX_DATASET_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"文件大小超过限制 ({MAX_DATASET_SIZE // 1024 // 1024}MB)"
                )
            f.write(content)
        
        # 解压ZIP文件
        extract_dir = os.path.join(dataset_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # 删除ZIP文件以节省空间
        os.remove(zip_path)
        
        # 扫描数据集图像
        image_files = []
        for root, dirs, files in os.walk(extract_dir):
            for filename in files:
                if filename.lower().endswith(tuple(settings.allowed_image_extensions)):
                    filepath = os.path.join(root, filename)
                    image_files.append(filepath)
        
        # 自动读取YAML文件获取类别名称
        detected_format = format_upper if format_upper != "AUTO" else "YOLO"
        class_names = []
        try:
            analyzer = DatasetAnalyzer(extract_dir, format=detected_format.lower())
            label_analysis = analyzer.analyze_labels()
            class_names = label_analysis.get("class_names", [])
            if class_names:
                logger.info(f"从YAML文件读取到 {len(class_names)} 个类别: {class_names}")
        except Exception as e:
            logger.warning(f"自动读取YAML文件失败: {e}")
        
        # 创建数据集记录
        # 处理空字符串为 None
        actual_production_line_id = production_line_id if production_line_id else None
        
        dataset = Dataset(
            name=name,
            description=description,
            path=extract_dir,
            format=detected_format,
            total_images=len(image_files),
            class_names=class_names,
            split_ratio={"train": 0.7, "val": 0.2, "test": 0.1},
            production_line_id=actual_production_line_id,
            created_by=current_user.user_id
        )
        
        db.add(dataset)
        await db.flush()
        
        # 创建图像记录（分批提交避免事务过大）
        batch_size = 100
        for i in range(0, len(image_files), batch_size):
            batch = image_files[i:i + batch_size]
            for image_path in batch:
                # 根据路径判断 split
                path_lower = image_path.lower()
                if 'test' in path_lower:
                    split = "test"
                elif 'val' in path_lower or 'valid' in path_lower:
                    split = "val"
                else:
                    split = "train"
                
                filename = os.path.basename(image_path)
                # 使用文件名（不含扩展名）作为 name_id，与预览保持一致
                name_id = Path(filename).stem
                
                dataset_image = DatasetImage(
                    name_id=name_id,
                    dataset_id=dataset.id,
                    filename=filename,
                    filepath=image_path,
                    split=split
                )
                db.add(dataset_image)
            await db.flush()
        
        await db.commit()
        await db.refresh(dataset)
        
        # 构建成功消息
        success_msg = f"数据集上传成功，共导入 {len(image_files)} 张图像"
        if class_names:
            success_msg += f"，检测到 {len(class_names)} 个类别"
        
        # 记录敏感操作日志
        logger.warning(
            f"用户 {current_user.user_id} (角色: {current_user.role}) 上传数据集: "
            f"dataset_id={dataset.id}, name={name}, format={detected_format}, "
            f"images={len(image_files)}, classes={class_names}"
        )
        
        return APIResponse.success_response(
            data=DatasetResponse.model_validate(dataset),
            message=success_msg
        )
        
    except HTTPException:
        # 清理临时目录
        if os.path.exists(dataset_dir):
            shutil.rmtree(dataset_dir)
        raise
    except Exception as e:
        # 清理临时目录
        if os.path.exists(dataset_dir):
            shutil.rmtree(dataset_dir)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传数据集失败: {str(e)}"
        )


@router.get("/", response_model=APIResponse[PaginatedResponse[DatasetResponse]])
async def list_datasets(
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None, description="搜索关键词（名称或描述）"),
    format: Optional[str] = Query(None, description="格式筛选 (YOLO/COCO/VOC)"),
    production_line_id: Optional[str] = Query(None, description="产线ID筛选"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[PaginatedResponse[DatasetResponse]]:
    """
    获取数据集列表
    
    支持搜索、格式筛选、产线筛选和分页
    - 管理员：查看所有数据集
    - 普通用户：只能查看自己创建的数据集
    """
    # 构建查询条件
    conditions = []
    
    # 普通用户只能查看自己的数据集
    if current_user.role != "admin":
        conditions.append(Dataset.created_by == current_user.user_id)
    
    if search:
        search_filter = or_(
            Dataset.name.ilike(f"%{search}%"),
            Dataset.description.ilike(f"%{search}%")
        )
        conditions.append(search_filter)
    
    if format:
        conditions.append(Dataset.format == format.upper())
    
    if production_line_id:
        conditions.append(Dataset.production_line_id == production_line_id)
    
    # 构建基础查询
    base_query = select(Dataset)
    if conditions:
        base_query = base_query.where(and_(*conditions))
    
    # 获取总数
    count_query = select(func.count()).select_from(Dataset)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # 获取分页数据，使用 joinedload 避免 N+1 问题
    result = await db.execute(
        base_query
        .options(joinedload(Dataset.production_line))
        .offset(pagination.offset)
        .limit(pagination.page_size)
        .order_by(Dataset.created_at.desc())
    )
    datasets = result.scalars().all()
    
    dataset_responses = [DatasetResponse.model_validate(ds) for ds in datasets]
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=dataset_responses,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    )


@router.get("/{id}", response_model=APIResponse[DatasetDetailResponse])
async def get_dataset(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DatasetDetailResponse]:
    """
    获取数据集详情
    
    包含数据集元信息和图像列表
    - 管理员：可以查看所有数据集
    - 普通用户：只能查看自己创建的数据集
    """
    # 先获取数据集基本信息
    result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 单独查询图像列表（避免joinedload导致的重复行问题）
    images_result = await db.execute(
        select(DatasetImage).where(DatasetImage.dataset_id == id)
    )
    images = images_result.scalars().all()
    
    # 构建响应数据
    dataset_data = DatasetResponse.model_validate(dataset)
    dataset_detail = DatasetDetailResponse(
        **dataset_data.model_dump(),
        images=[DatasetImageResponse.model_validate(img) for img in images]
    )
    
    return APIResponse.success_response(data=dataset_detail)


class SplitDatasetRequest(BaseModel):
    """数据集划分请求"""
    train_ratio: float = Field(0.7, ge=0, le=1, description="训练集比例")
    val_ratio: float = Field(0.2, ge=0, le=1, description="验证集比例")
    test_ratio: float = Field(0.1, ge=0, le=1, description="测试集比例")


@router.post("/{id}/split", response_model=APIResponse[DatasetResponse])
async def split_dataset(
    id: str,
    request: SplitDatasetRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DatasetResponse]:
    """
    执行数据集划分
    
    按比例随机划分训练/验证/测试集，比例之和必须等于1。
    创建新的数据集，不修改原数据集。
    
    新数据集命名规则：原数据集名_train{比例}_val{比例}_test{比例}
    例如：neu_train70_val20_test10
    """
    check_admin_permission(current_user)
    
    # 从请求中获取比例
    train_ratio = request.train_ratio
    val_ratio = request.val_ratio
    test_ratio = request.test_ratio
    
    logger.info(f"收到划分请求: train={train_ratio}, val={val_ratio}, test={test_ratio}")
    
    # 验证比例
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 0.001:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"划分比例之和必须等于1，当前为 {total_ratio}"
        )
    
    # 获取原数据集
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    source_dataset = dataset_result.scalar_one_or_none()
    
    if not source_dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 获取所有图像
    images_result = await db.execute(
        select(DatasetImage).where(DatasetImage.dataset_id == id)
    )
    images = images_result.scalars().all()
    
    if not images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="数据集中没有图像"
        )
    
    # 检查前5个图像的路径格式
    logger.info(f"原数据集路径: {source_dataset.path}")
    for i, img in enumerate(images[:5]):
        logger.info(f"示例图像 {i+1}: filename={img.filename}, filepath={img.filepath}, split={img.split}")
    
    # 随机打乱并划分
    import random
    image_list = list(images)
    random.shuffle(image_list)
    
    total = len(image_list)
    train_count = int(total * train_ratio)
    val_count = int(total * val_ratio)
    
    logger.info(f"原数据集图像总数: {total}, 训练集: {train_count}, 验证集: {val_count}, 测试集: {total - train_count - val_count}")
    
    # 为每个图像分配split
    for idx, image in enumerate(image_list):
        if idx < train_count:
            image.split = "train"
        elif idx < train_count + val_count:
            image.split = "val"
        else:
            image.split = "test"
    
    # 生成新数据集名称
    train_pct = int(train_ratio * 100)
    val_pct = int(val_ratio * 100)
    test_pct = int(test_ratio * 100)
    new_dataset_name = f"{source_dataset.name}_train{train_pct}_val{val_pct}_test{test_pct}"
    
    # 创建新目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_dataset_dir = os.path.join(settings.upload_dir, "datasets", f"{new_dataset_name}_{timestamp}")
    os.makedirs(new_dataset_dir, exist_ok=True)
    
    logger.info(f"创建新数据集目录: {new_dataset_dir}")
    
    # 从YAML读取修复后的类别名称
    from app.services.dataset_statistics_service import DatasetStatisticsService
    service = DatasetStatisticsService(db)
    yaml_class_names = service._load_yaml_class_names(Path(source_dataset.path))
    # 使用修复后的类别名称，如果没有则使用原始名称
    class_names = yaml_class_names if yaml_class_names else source_dataset.class_names
    logger.info(f"新数据集使用类别名称: {class_names}")
    
    try:
        # 复制文件到新目录
        result = await _create_split_dataset(
            source_dataset=source_dataset,
            image_list=image_list,
            new_dataset_dir=new_dataset_dir,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio
        )
        
        # 创建新的数据集记录
        new_dataset = Dataset(
            name=new_dataset_name,
            description=f"从 {source_dataset.name} 划分生成: 训练集{train_pct}%, 验证集{val_pct}%, 测试集{test_pct}%",
            path=new_dataset_dir,
            format=source_dataset.format,
            total_images=total,
            total_annotations=source_dataset.total_annotations,
            class_names=class_names,
            split_ratio={"train": train_ratio, "val": val_ratio, "test": test_ratio},
            production_line_id=source_dataset.production_line_id,
            created_by=current_user.user_id
        )
        
        db.add(new_dataset)
        await db.flush()  # 获取新数据集的ID
        
        # 创建图像记录 - 使用相对路径
        for image in image_list:
            # 使用相对于新数据集目录的路径
            relative_path = os.path.join(image.split, "images", image.filename)
            # 使用文件名（不含扩展名）作为 name_id
            name_id = Path(image.filename).stem
            
            new_image = DatasetImage(
                name_id=name_id,
                dataset_id=new_dataset.id,
                filename=image.filename,
                filepath=relative_path,  # 存储相对路径
                split=image.split,
                width=image.width,
                height=image.height
            )
            db.add(new_image)
        
        await db.commit()
        await db.refresh(new_dataset)
        
        # 为新数据集创建统计信息记录（标记为已完成，因为划分时已经统计过了）
        from app.models.dataset_statistics import DatasetStatistics
        
        # 计算各split的数量
        test_count = total - train_count - val_count
        split_dist = {"train": train_count, "val": val_count, "test": test_count}
        logger.info(f"创建统计信息: total={total}, split_distribution={split_dist}")
        
        stats = DatasetStatistics(
            dataset_id=new_dataset.id,
            total_images=total,
            total_annotations=source_dataset.total_annotations,
            images_with_annotations=total,  # 假设所有图像都有标注
            images_without_annotations=0,
            avg_annotations_per_image=source_dataset.total_annotations / total if total > 0 else 0,
            class_count=len(source_dataset.class_names),
            class_distribution=[{"class_name": name, "count": 0, "percentage": 0} for name in source_dataset.class_names],
            annotations_per_class={name: 0 for name in source_dataset.class_names},
            image_sizes=[],
            avg_image_width=0,
            avg_image_height=0,
            split_distribution=split_dist,
            avg_bbox_width=0,
            avg_bbox_height=0,
            avg_bbox_aspect_ratio=1,
            small_bboxes=0,
            medium_bboxes=0,
            large_bboxes=0,
            scan_status="completed",
            last_scan_time=datetime.now(timezone.utc),
            labels_hash=""  # 划分的数据集不基于labels_hash检测变化
        )
        db.add(stats)
        logger.info(f"Before commit: stats.split_distribution={stats.split_distribution}")
        await db.commit()
        logger.info(f"After commit: stats.split_distribution={stats.split_distribution}")
        await db.refresh(stats)
        logger.info(f"After refresh: stats.split_distribution={stats.split_distribution}")
        
        logger.info(f"新数据集创建成功: {new_dataset.id}, 名称: {new_dataset_name}, 统计信息已创建")
        
        # 记录敏感操作日志
        logger.warning(
            f"用户 {current_user.user_id} (角色: {current_user.role}) 执行数据集划分: "
            f"source_id={id}, source_name={source_dataset.name}, "
            f"new_id={new_dataset.id}, new_name={new_dataset_name}, "
            f"ratios=train:{train_ratio},val:{val_ratio},test:{test_ratio}, "
            f"counts=train:{train_count},val:{val_count},test:{total - train_count - val_count}"
        )
        
        return APIResponse.success_response(
            data=DatasetResponse.model_validate(new_dataset),
            message=f"数据集划分完成，已创建新数据集 '{new_dataset_name}': 训练集 {train_count}, 验证集 {val_count}, 测试集 {total - train_count - val_count}"
        )
        
    except Exception as e:
        # 清理新创建的目录
        if os.path.exists(new_dataset_dir):
            shutil.rmtree(new_dataset_dir)
        logger.error(f"创建划分数据集失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建划分数据集失败: {str(e)}"
        )


async def _create_split_dataset(
    source_dataset: Dataset,
    image_list: list,
    new_dataset_dir: str,
    train_ratio: float,
    val_ratio: float,
    test_ratio: float
) -> dict:
    """
    创建划分后的数据集文件
    
    复制文件到新目录，创建标准YOLO结构
    
    Returns:
        划分统计信息
    """
    from pathlib import Path
    
    source_path = Path(source_dataset.path)
    target_path = Path(new_dataset_dir)
    
    logger.info(f"开始创建划分数据集: {source_path} -> {target_path}, 图像总数: {len(image_list)}")
    
    # 创建目录结构
    splits = ["train", "val", "test"]
    for split in splits:
        (target_path / split / "images").mkdir(parents=True, exist_ok=True)
        (target_path / split / "labels").mkdir(parents=True, exist_ok=True)
    
    stats = {"train": 0, "val": 0, "test": 0}
    missing_count = 0
    error_count = 0
    
    for idx, image in enumerate(image_list):
        split = image.split
        if split not in stats:
            logger.warning(f"未知的split: {split}, 图像: {image.filename}")
            continue
        
        # 源图像路径 - filepath 可能是相对路径或绝对路径
        src_image = Path(image.filepath)
        
        # 尝试多种路径组合来找到源文件
        possible_src_paths = [
            src_image,  # 原路径（可能是绝对路径）
            source_path / src_image,  # 相对于 source_path
            Path(os.getcwd()) / src_image,  # 相对于当前工作目录
        ]
        
        src_image = None
        for path in possible_src_paths:
            if path.exists():
                src_image = path
                break
        
        if src_image is None:
            logger.warning(f"源图像不存在，已尝试路径: {[str(p) for p in possible_src_paths]}, 原filepath: {image.filepath}")
            missing_count += 1
            continue
        
        # 目标路径
        dst_image = target_path / split / "images" / image.filename
        dst_label = target_path / split / "labels" / src_image.with_suffix(".txt").name
        
        try:
            # 复制图像
            shutil.copy2(str(src_image), str(dst_image))
            stats[split] += 1
            
            # 查找并复制标签
            src_label = src_image.with_suffix(".txt")
            if not src_label.exists():
                # 尝试其他可能的位置
                possible_paths = [
                    src_image.parent.parent / "labels" / src_image.with_suffix(".txt").name,
                    src_image.parent / "labels" / src_image.with_suffix(".txt").name,
                ]
                for path in possible_paths:
                    if path.exists():
                        src_label = path
                        break
            
            if src_label.exists():
                shutil.copy2(str(src_label), str(dst_label))
                
        except Exception as e:
            logger.error(f"复制文件失败 {src_image}: {e}")
            error_count += 1
            continue
        
        # 每100张打印一次进度
        if idx % 100 == 0:
            logger.info(f"处理进度: {idx}/{len(image_list)}, stats: {stats}")
    
    logger.info(f"复制完成: stats={stats}, 缺失={missing_count}, 错误={error_count}")
    
    # 创建YAML配置文件
    yaml_config = {
        "path": ".",
        "train": "train/images",
        "val": "val/images",
        "test": "test/images" if stats["test"] > 0 else None,
        "nc": len(source_dataset.class_names),
        "names": source_dataset.class_names
    }
    
    # 移除None值
    yaml_config = {k: v for k, v in yaml_config.items() if v is not None}
    
    try:
        import yaml
        yaml_path = target_path / "data.yaml"
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_config, f, allow_unicode=True, sort_keys=False)
        logger.info(f"创建YAML配置: {yaml_path}")
    except Exception as e:
        logger.error(f"保存YAML失败: {e}")
    
    logger.info(f"数据集划分完成: {stats}")
    return stats


@router.post("/{id}/convert", response_model=APIResponse[DatasetResponse])
async def convert_dataset_format(
    id: str,
    request: DatasetConvertRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DatasetResponse]:
    """
    转换数据集格式
    
    支持 YOLO/COCO/VOC 格式互转
    """
    check_admin_permission(current_user)
    target_format = request.target_format.upper()
    if target_format not in ALLOWED_DATASET_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的目标格式: {target_format}"
        )
    
    # 获取数据集
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    if dataset.format == target_format:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"数据集已经是 {target_format} 格式"
        )
    
    # 执行实际的格式转换
    try:
        from app.utils.dataset_parser import DatasetAnalyzer, DatasetConverter
        
        # 解析当前数据集
        logger.info(f"开始解析数据集: path={dataset.path}, format={dataset.format.lower()}")
        analyzer = DatasetAnalyzer(dataset.path, dataset.format.lower())
        
        # 先调用 analyze_labels() 来解析数据集，它会缓存 DatasetInfo 到 _dataset_info
        analysis_result = analyzer.analyze_labels()
        logger.info(f"analyze_labels 返回: {analysis_result}")
        
        # 获取内部缓存的 DatasetInfo 对象
        dataset_info = analyzer._dataset_info
        logger.info(f"_dataset_info: {dataset_info}")
        
        if not dataset_info:
            error_msg = analysis_result.get('error', '未知错误')
            logger.error(f"解析数据集失败: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无法解析数据集: {error_msg}"
            )
        
        if not dataset_info.images:
            logger.error(f"数据集中没有图像")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="数据集中没有图像"
            )
        
        # 更新类别名称（使用数据库中的修复后的名称）
        dataset_info.class_names = dataset.class_names
        
        # 转换数据集
        converter = DatasetConverter()
        
        # 生成输出路径
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(
            settings.upload_dir, 
            "datasets", 
            f"{dataset.name}_{dataset.format}_to_{target_format}_{timestamp}"
        )
        os.makedirs(output_dir, exist_ok=True)
        
        # 执行转换
        if target_format == "COCO":
            result_path = await converter.to_coco_async(dataset_info, output_dir)
        elif target_format == "VOC":
            result_path = await converter.to_voc_async(dataset_info, output_dir)
        elif target_format == "YOLO":
            result_path = await converter.to_yolo_async(dataset_info, output_dir)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的目标格式: {target_format}"
            )
        
        # 创建新的数据集记录
        new_dataset = Dataset(
            name=f"{dataset.name}_{dataset.format}_to_{target_format}",
            description=f"从 {dataset.name} ({dataset.format}) 转换为 {target_format} 格式",
            path=result_path,
            format=target_format,
            total_images=dataset.total_images,
            total_annotations=dataset.total_annotations,
            class_names=dataset.class_names,
            split_ratio=dataset.split_ratio,
            production_line_id=dataset.production_line_id,
            created_by=current_user.user_id
        )
        
        db.add(new_dataset)
        await db.flush()  # 获取新数据集的ID
        
        # 创建图像记录
        from app.models.dataset import DatasetImage as DatasetImageModel
        for img in dataset_info.images:
            # 根据目标格式使用不同的路径格式
            if target_format == "VOC":
                # VOC 格式: JPEGImages/{split}/{filename}
                relative_path = os.path.join("JPEGImages", img.split, img.filename)
            elif target_format == "COCO":
                # COCO 格式: images/{split}/{filename}
                relative_path = os.path.join("images", img.split, img.filename)
            else:
                # YOLO 格式: {split}/images/{filename}
                relative_path = os.path.join(img.split, "images", img.filename)
            
            # 使用文件名（不含扩展名）作为 name_id
            name_id = Path(img.filename).stem
            
            new_image = DatasetImageModel(
                name_id=name_id,
                dataset_id=new_dataset.id,
                filename=img.filename,
                filepath=relative_path,  # 存储相对路径
                split=img.split,
                width=img.width,
                height=img.height
            )
            db.add(new_image)
        
        # 为新数据集创建统计信息记录
        from app.models.dataset_statistics import DatasetStatistics
        
        # 从 dataset_info 统计各split的图像数量
        split_counts = {"train": 0, "val": 0, "test": 0}
        for img in dataset_info.images:
            split = img.split if img.split in split_counts else "train"
            split_counts[split] += 1
        
        stats = DatasetStatistics(
            dataset_id=new_dataset.id,
            total_images=len(dataset_info.images),
            total_annotations=sum(len(img.bboxes) for img in dataset_info.images),
            images_with_annotations=sum(1 for img in dataset_info.images if img.bboxes),
            images_without_annotations=sum(1 for img in dataset_info.images if not img.bboxes),
            avg_annotations_per_image=sum(len(img.bboxes) for img in dataset_info.images) / len(dataset_info.images) if dataset_info.images else 0,
            class_count=len(dataset.class_names),
            class_distribution=[{"class_name": name, "count": 0, "percentage": 0} for name in dataset.class_names],
            annotations_per_class={name: 0 for name in dataset.class_names},
            image_sizes=[],
            avg_image_width=0,
            avg_image_height=0,
            avg_bbox_width=0,
            avg_bbox_height=0,
            avg_bbox_aspect_ratio=1.0,
            small_bboxes=0,
            medium_bboxes=0,
            large_bboxes=0,
            split_distribution=split_counts,
            scan_status="completed",
            last_scan_time=datetime.now(timezone.utc),
            labels_hash=""
        )
        db.add(stats)
        await db.commit()
        await db.refresh(new_dataset)
        
        # 记录敏感操作日志
        logger.warning(
            f"用户 {current_user.user_id} (角色: {current_user.role}) 执行数据集格式转换: "
            f"source_id={id}, source_name={dataset.name}, "
            f"source_format={dataset.format}, target_format={target_format}, "
            f"new_id={new_dataset.id}, new_name={new_dataset.name}"
        )
        
        return APIResponse.success_response(
            data=DatasetResponse.model_validate(new_dataset),
            message=f"数据集格式已转换为 {target_format}，新数据集已创建"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"转换数据集格式失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"转换失败: {str(e)}"
        )


async def _sync_images_async(dataset_id: str, dataset_path: str, format_type: str, max_images: int = 1000):
    """
    异步后台同步图像（不阻塞主请求）
    """
    from app.db.session import async_session
    from app.models.dataset import Dataset
    
    try:
        async with async_session() as db:
            # 获取数据集
            result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
            dataset = result.scalar_one_or_none()
            if not dataset:
                logger.error(f"后台同步: 数据集 {dataset_id} 不存在")
                return
            
            logger.info(f"后台同步开始: 数据集 {dataset_id}")
            count = await _sync_images_from_filesystem(dataset, db, max_images)
            logger.info(f"后台同步完成: 数据集 {dataset_id}, 同步了 {count} 张图像")
    except Exception as e:
        logger.error(f"后台同步失败: 数据集 {dataset_id}, 错误: {e}")


async def _sync_images_from_filesystem(dataset: Dataset, db: AsyncSession, max_images: int = 1000) -> int:
    """
    从文件系统扫描图像并同步到数据库（限制数量以提高性能）
    
    Args:
        dataset: 数据集对象
        db: 数据库会话
        max_images: 最大同步图像数量，默认1000
        
    Returns:
        同步的图像数量
    """
    from app.utils.dataset_parser import DatasetAnalyzer
    
    try:
        # 使用 DatasetAnalyzer 解析数据集（限制数量以提高性能）
        analyzer = DatasetAnalyzer(dataset.path, dataset.format.lower())
        preview_images = analyzer.get_preview_images(max_images)
        
        if not preview_images:
            logger.warning(f"从文件系统未找到任何图像: {dataset.path}")
            return 0
        
        # 创建图像记录
        count = 0
        for img_info in preview_images:
            # 判断路径类型（相对或绝对）
            img_path = Path(img_info["filepath"])
            if img_path.is_absolute():
                filepath = str(img_path)
            else:
                # 使用相对路径
                filepath = img_info["filepath"]
            
            # 使用文件名（不含扩展名）作为 name_id，与预览保持一致
            name_id = Path(img_info["filename"]).stem
            
            dataset_image = DatasetImage(
                name_id=name_id,
                dataset_id=dataset.id,
                filename=img_info["filename"],
                filepath=filepath,
                split=img_info.get("split", "train"),
                width=img_info.get("width", 0),
                height=img_info.get("height", 0)
            )
            db.add(dataset_image)
            count += 1
            
            # 分批提交避免事务过大
            if count % 100 == 0:
                await db.flush()
        
        await db.commit()
        logger.info(f"成功同步 {count} 张图像到数据库")
        return count
        
    except Exception as e:
        logger.error(f"同步图像失败: {e}")
        await db.rollback()
        raise


@router.get("/{id}/images", response_model=APIResponse[PaginatedResponse[DatasetImageResponse]])
async def get_dataset_images(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
    split: Optional[str] = Query(None, description="划分筛选 (train/val/test)"),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[PaginatedResponse[DatasetImageResponse]]:
    """
    分页获取数据集图像列表
    
    支持按划分筛选。如果数据库中没有图像记录，会自动从文件系统扫描并创建记录。
    """
    # 验证数据集存在
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = dataset_result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 获取总数
    count_query = select(func.count()).select_from(DatasetImage).where(DatasetImage.dataset_id == id)
    if split:
        count_query = count_query.where(DatasetImage.split == split)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # 如果数据库中没有图像记录，异步触发文件系统扫描（不阻塞当前请求）
    if total == 0:
        logger.info(f"数据集 {id} 数据库中没有图像记录，将在后台同步...")
        # 使用 asyncio.create_task 异步执行，不阻塞当前请求
        import asyncio
        asyncio.create_task(_sync_images_async(dataset.id, dataset.path, dataset.format.lower()))
    
    # 构建查询
    query = select(DatasetImage).where(DatasetImage.dataset_id == id)
    if split:
        query = query.where(DatasetImage.split == split)
    
    # 获取分页数据
    result = await db.execute(
        query
        .offset(pagination.offset)
        .limit(pagination.page_size)
        .order_by(DatasetImage.created_at.desc())
    )
    images = result.scalars().all()
    
    # 手动构建响应，使用 name_id 作为 id
    image_responses = []
    for img in images:
        image_responses.append(DatasetImageResponse(
            id=img.name_id,  # 使用 name_id 作为 id 返回
            filename=img.filename,
            filepath=img.filepath,
            split=img.split,
            width=img.width,
            height=img.height,
            annotation_path=img.annotation_path,
            created_at=img.created_at
        ))
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=image_responses,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    )


@router.get("/{id}/images/{image_id}/thumbnail")
async def get_image_thumbnail(
    id: str,
    image_id: str,
    width: int = Query(256, ge=32, le=1024, description="缩略图宽度"),
    height: int = Query(256, ge=32, le=1024, description="缩略图高度"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Response:
    """
    获取图像缩略图
    
    支持指定缩略图尺寸，自动生成并缓存缩略图
    
    Args:
        id: 数据集ID
        image_id: 图像ID
        width: 缩略图宽度 (32-1024)
        height: 缩略图高度 (32-1024)
        current_user: 当前用户
        db: 数据库会话
    
    Returns:
        缩略图文件响应
    """
    import logging
    from PIL import Image as PILImage
    import io
    
    logger = logging.getLogger(__name__)
    
    # 验证数据集存在并检查权限
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = dataset_result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 获取图像
    image_result = await db.execute(
        select(DatasetImage).where(
            and_(DatasetImage.name_id == image_id, DatasetImage.dataset_id == id)
        )
    )
    image = image_result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图像不存在"
        )
    
    # 构建完整的图像路径（支持相对路径和绝对路径）
    image_path = Path(image.filepath)
    
    # 首先检查filepath是否已经是有效路径（相对于当前工作目录或绝对路径）
    if not image_path.exists():
        # 尝试相对于数据集路径
        alt_path = Path(dataset.path) / image_path
        if alt_path.exists():
            image_path = alt_path
    
    # 如果还是不存在，尝试其他可能的路径组合
    if not image_path.exists():
        possible_paths = [
            # YOLO 格式
            Path(dataset.path) / image.split / "images" / image.filename,
            Path(dataset.path) / "images" / image.split / image.filename,
            # VOC 格式
            Path(dataset.path) / "JPEGImages" / image.split / image.filename,
            # COCO 格式
            Path(dataset.path) / "images" / image.split / image.filename,
        ]
        found_path = None
        for p in possible_paths:
            if p.exists():
                found_path = p
                break
        
        if not found_path:
            logger.error(f"图像文件不存在: {image.filepath}, 尝试路径: {[str(p) for p in possible_paths]}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="图像文件不存在"
            )
        image_path = found_path
    
    try:
        # 生成缩略图
        with PILImage.open(image_path) as img:
            # 转换为RGB模式（处理RGBA等模式）
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # 生成缩略图
            img.thumbnail((width, height), PILImage.Resampling.LANCZOS)
            
            # 保存到内存
            buffer = io.BytesIO()
            img_format = 'JPEG'
            save_kwargs = {'quality': 85, 'optimize': True}
            
            # 如果是PNG格式且需要保留透明度
            if image_path.suffix.lower() == '.png':
                img_format = 'PNG'
                save_kwargs = {'optimize': True}
            
            img.save(buffer, format=img_format, **save_kwargs)
            buffer.seek(0)
            
            # 返回响应
            media_type = f"image/{img_format.lower()}"
            return Response(
                content=buffer.getvalue(),
                media_type=media_type
            )
            
    except Exception as e:
        logger.error(f"生成缩略图失败: {str(e)}")
        # 如果缩略图生成失败，返回原始文件
        return FileResponse(
            str(image_path),
            media_type="image/jpeg",
            filename=f"thumbnail_{image.filename}"
        )


@router.get("/{id}/images/{image_id}/annotated")
async def get_annotated_image(
    id: str,
    image_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Response:
    """
    获取带标注的图像
    
    返回渲染了标注框的图像
    """
    # 验证数据集存在并检查权限
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = dataset_result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 获取图像
    image_result = await db.execute(
        select(DatasetImage).where(
            and_(DatasetImage.name_id == image_id, DatasetImage.dataset_id == id)
        )
    )
    image = image_result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="图像不存在"
        )
    
    # 构建完整的图像路径（支持相对路径和绝对路径）
    image_path = Path(image.filepath)
    
    # 首先检查filepath是否已经是有效路径（相对于当前工作目录或绝对路径）
    if not image_path.exists():
        # 尝试相对于数据集路径
        alt_path = Path(dataset.path) / image_path
        if alt_path.exists():
            image_path = alt_path
    
    # 如果还是不存在，尝试其他可能的路径组合
    if not image_path.exists():
        possible_paths = [
            # YOLO 格式
            Path(dataset.path) / image.split / "images" / image.filename,
            Path(dataset.path) / "images" / image.split / image.filename,
            # VOC 格式
            Path(dataset.path) / "JPEGImages" / image.split / image.filename,
            # COCO 格式
            Path(dataset.path) / "images" / image.split / image.filename,
        ]
        found_path = None
        for p in possible_paths:
            if p.exists():
                found_path = p
                break
        
        if not found_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="图像文件不存在"
            )
        image_path = found_path
    
    # TODO: 实现标注渲染逻辑
    # 这里直接返回原图，后续需要实现标注框渲染
    
    return FileResponse(
        str(image_path),
        media_type="image/jpeg",
        filename=f"annotated_{image.filename}"
    )


@router.delete("/{id}", response_model=APIResponse)
async def delete_dataset(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse:
    """
    删除数据集
    
    同时删除数据库记录和存储的文件
    - 管理员：可以删除所有数据集
    - 普通用户：只能删除自己创建的数据集
    """
    # 获取数据集
    result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 获取数据集路径用于删除
    dataset_path = dataset.path
    dataset_name = dataset.name
    
    # 记录敏感操作日志
    logger.warning(
        f"用户 {current_user.user_id} (角色: {current_user.role}) 删除数据集: "
        f"id={id}, name={dataset_name}, path={dataset_path}"
    )
    
    # 删除数据库记录
    await db.delete(dataset)
    await db.commit()
    
    # 删除文件目录
    try:
        if os.path.exists(dataset_path):
            # 确定数据集根目录
            # 路径格式可能是:
            # 1. uploads/datasets/name_timestamp (划分的数据集)
            # 2. uploads/datasets/name_timestamp/extracted/subdir (上传的数据集)
            
            path_parts = Path(dataset_path).parts
            dataset_root = dataset_path
            
            # 如果路径包含 'extracted'，向上追溯到数据集根目录
            if "extracted" in path_parts:
                # 找到 'datasets' 目录后的部分，通常是 name_timestamp
                datasets_idx = -1
                for i, part in enumerate(path_parts):
                    if part == "datasets" and i + 1 < len(path_parts):
                        datasets_idx = i
                        break
                
                if datasets_idx >= 0:
                    # 构建到 name_timestamp 的完整路径
                    dataset_root = os.path.join(*path_parts[:datasets_idx + 2])
            
            # 安全检查：确保要删除的目录在 datasets 目录下
            if "datasets" in Path(dataset_root).parts:
                logger.info(f"删除数据集目录: {dataset_root}")
                shutil.rmtree(dataset_root)
            else:
                logger.error(f"拒绝删除不在datasets目录下的路径: {dataset_root}")
    except Exception as e:
        # 记录错误但不影响API响应
        logger.error(f"删除数据集文件失败: {e}")
    
    return APIResponse.success_response(message="数据集删除成功")



@router.get("/{id}/labels", response_model=APIResponse[LabelAnalysisResponse])
async def analyze_dataset_labels_api(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[LabelAnalysisResponse]:
    """
    分析数据集标签
    
    返回类别统计信息，包括：
    - 类别名称列表
    - 每个类别的标注数量
    - 包含每个类别的图像数量
    - YAML配置（如果存在）
    """
    # 获取数据集
    result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 分析标签
    from app.utils.dataset_parser import DatasetAnalyzer
    analyzer = DatasetAnalyzer(dataset.path, dataset.format.lower())
    analysis = analyzer.analyze_labels()
    
    return APIResponse.success_response(
        data=LabelAnalysisResponse(
            class_names=analysis.get("class_names", []),
            class_count=analysis.get("class_count", 0),
            annotations_per_class=analysis.get("annotations_per_class", {}),
            images_per_class=analysis.get("images_per_class", {}),
            total_annotations=analysis.get("total_annotations", 0),
            yaml_config=analysis.get("yaml_config"),
            has_yaml=analysis.get("yaml_config") is not None
        )
    )


@router.get("/{id}/preview", response_model=APIResponse[DatasetPreviewResponse])
async def get_dataset_preview_api(
    id: str,
    count: int = Query(20, ge=1, le=50, description="预览图片数量"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DatasetPreviewResponse]:
    """
    获取数据集预览图片
    
    返回前N张图片的信息，用于数据集卡片展示
    """
    # 获取数据集
    result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 获取预览图片
    from app.utils.dataset_parser import DatasetAnalyzer
    analyzer = DatasetAnalyzer(dataset.path, dataset.format.lower())
    preview_images = analyzer.get_preview_images(count)
    
    return APIResponse.success_response(
        data=DatasetPreviewResponse(
            dataset_id=dataset.id,
            total_images=dataset.total_images,
            preview_images=[
                PreviewImageInfo(
                    id=img["id"],
                    filename=img["filename"],
                    filepath=img["filepath"],
                    width=img["width"],
                    height=img["height"],
                    split=img["split"],
                    annotation_count=img["annotation_count"]
                )
                for img in preview_images
            ]
        )
    )


@router.put("/{id}/labels", response_model=APIResponse[UpdateLabelsResponse])
async def update_dataset_labels_api(
    id: str,
    request: UpdateLabelsRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[UpdateLabelsResponse]:
    """
    更新数据集标签（类别名称）
    
    支持手动填写类别名称，并可选保存到YAML文件
    """
    # 获取数据集
    result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 记录旧类别名称用于日志
    old_class_names = dataset.class_names.copy() if dataset.class_names else []
    
    # 更新类别名称
    from app.utils.dataset_parser import DatasetAnalyzer
    analyzer = DatasetAnalyzer(dataset.path, dataset.format.lower())
    
    yaml_saved = False
    if request.save_to_yaml:
        yaml_saved = analyzer.update_class_names(request.class_names)
    
    # 更新数据库中的类别名称
    dataset.class_names = request.class_names
    await db.commit()
    await db.refresh(dataset)
    
    # 记录敏感操作日志
    logger.info(
        f"用户 {current_user.user_id} (角色: {current_user.role}) 更新数据集标签: "
        f"dataset_id={id}, name={dataset.name}, "
        f"old_classes={old_class_names}, new_classes={request.class_names}, "
        f"yaml_saved={yaml_saved}"
    )
    
    return APIResponse.success_response(
        data=UpdateLabelsResponse(
            success=True,
            class_names=request.class_names,
            yaml_saved=yaml_saved
        ),
        message="标签更新成功"
    )


@router.post("/{id}/labels/yaml", response_model=APIResponse[UpdateLabelsResponse])
async def upload_yaml_config_api(
    id: str,
    yaml_content: str = Form(..., description="YAML文件内容"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[UpdateLabelsResponse]:
    """
    上传YAML配置文件
    
    用户可以通过上传YAML文件来配置类别名称
    """
    # 获取数据集
    result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 解析YAML内容
    try:
        import yaml
        config = yaml.safe_load(yaml_content)
        
        if not config or "names" not in config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="YAML文件必须包含 'names' 字段"
            )
        
        names = config["names"]
        if isinstance(names, dict):
            class_names = [names[i] for i in sorted(names.keys())]
        elif isinstance(names, list):
            class_names = names
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'names' 必须是列表或字典"
            )
        
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器未安装YAML解析库"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"YAML解析失败: {str(e)}"
        )
    
    # 保存YAML配置
    from app.utils.dataset_parser import DatasetAnalyzer
    analyzer = DatasetAnalyzer(dataset.path, dataset.format.lower())
    yaml_saved = analyzer.save_yaml_config(config)
    
    # 更新数据库中的类别名称
    dataset.class_names = class_names
    await db.commit()
    await db.refresh(dataset)
    
    return APIResponse.success_response(
        data=UpdateLabelsResponse(
            success=True,
            class_names=class_names,
            yaml_saved=yaml_saved
        ),
        message="YAML配置上传成功"
    )


@router.get("/{id}/card-info", response_model=APIResponse[DatasetCardInfoResponse])
async def get_dataset_card_info_api(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DatasetCardInfoResponse]:
    """
    获取数据集卡片信息（用于列表页展示）
    
    包含：
    - 基本信息（名称、描述、格式等）
    - 类别统计（优先从数据库统计表获取，如不存在则实时分析）
    - 预览图片（前20张）
    - 标签分布
    
    如果统计数据为空，会自动触发异步分析任务。
    """
    # 获取数据集（使用joinedload预加载statistics避免N+1问题）
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(Dataset)
        .options(joinedload(Dataset.statistics))
        .where(Dataset.id == id)
    )
    dataset = result.unique().scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 尝试获取统计数据
    annotations_per_class = {}
    class_count = len(dataset.class_names) if dataset.class_names else 0
    
    if dataset.statistics and dataset.statistics.scan_status == "completed":
        # 使用数据库中缓存的统计数据
        logger.debug(f"使用缓存的统计数据，数据集: {id}")
        annotations_per_class = dataset.statistics.annotations_per_class or {}
        class_count = dataset.statistics.class_count or class_count
    else:
        # 统计数据不存在或未完成后，尝试实时分析（但不阻塞响应）
        logger.info(f"数据集 {id} 统计信息不存在或未完成，将使用实时分析")
        try:
            from app.utils.dataset_parser import DatasetAnalyzer
            analyzer = DatasetAnalyzer(dataset.path, dataset.format.lower())
            label_analysis = analyzer.analyze_labels()
            annotations_per_class = label_analysis.get("annotations_per_class", {})
            class_count = label_analysis.get("class_count", class_count)
            
            # 异步触发统计更新（不等待完成）
            # 实际应用中可以使用后台任务如Celery
        except Exception as e:
            logger.warning(f"实时分析数据集 {id} 失败: {e}")
    
    # 获取预览图片（前20张）
    from app.utils.dataset_parser import DatasetAnalyzer
    analyzer = DatasetAnalyzer(dataset.path, dataset.format.lower())
    preview_images = analyzer.get_preview_images(20)
    
    # 将预览图片的 id 转换为 name_id（文件名，不含扩展名）
    # 这样前端可以直接用这个 id 请求缩略图
    from pathlib import Path
    preview_images_fixed = []
    for img in preview_images:
        # 使用文件名（不含扩展名）作为 id
        name_id = Path(img["filename"]).stem
        img_fixed = {**img, "id": name_id}
        preview_images_fixed.append(img_fixed)
    
    return APIResponse.success_response(
        data=DatasetCardInfoResponse(
            id=dataset.id,
            name=dataset.name,
            description=dataset.description,
            format=dataset.format,
            total_images=dataset.total_images,
            class_count=class_count,
            class_names=dataset.class_names or [],
            preview_images=[
                PreviewImageInfo(
                    id=img["id"],
                    filename=img["filename"],
                    filepath=img["filepath"],
                    width=img["width"],
                    height=img["height"],
                    split=img["split"],
                    annotation_count=img["annotation_count"]
                )
                for img in preview_images_fixed
            ],
            annotations_per_class=annotations_per_class,
            created_at=dataset.created_at
        )
    )


# ==================== 数据集统计分析 API ====================

@router.get("/{id}/statistics", response_model=APIResponse[DatasetStatisticsResponse])
async def get_dataset_statistics_api(
    id: str,
    force_refresh: bool = Query(False, description="强制重新分析"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DatasetStatisticsResponse]:
    """
    获取数据集统计信息
    
    如果统计信息不存在或已过期，自动进行分析。
    统计信息包括：
    - 图像和标注数量统计
    - 类别分布
    - 图像尺寸分布
    - 标注框大小分布
    - 数据集划分分布
    
    Args:
        id: 数据集ID
        force_refresh: 是否强制重新分析
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        数据集统计信息
    """
    # 检查数据集访问权限
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    check_dataset_access(dataset, current_user)
    
    try:
        # 获取或创建统计信息
        service = DatasetStatisticsService(db)
        stats = await service.get_or_create_statistics(id, force_refresh=force_refresh)
        
        # 构建响应数据
        response_data = DatasetStatisticsResponse(
            dataset_id=id,
            total_images=stats.total_images,
            total_annotations=stats.total_annotations,
            avg_annotations_per_image=round(stats.avg_annotations_per_image, 2),
            images_with_annotations=stats.images_with_annotations,
            images_without_annotations=stats.images_without_annotations,
            class_count=stats.class_count,
            class_distribution=[
                item for item in stats.class_distribution
            ],
            size_distribution=[
                item for item in stats.image_sizes
            ],
            bbox_distribution={
                "avg_width": round(stats.avg_bbox_width, 2),
                "avg_height": round(stats.avg_bbox_height, 2),
                "avg_aspect_ratio": round(stats.avg_bbox_aspect_ratio, 2),
                "small_boxes": stats.small_bboxes,
                "medium_boxes": stats.medium_bboxes,
                "large_boxes": stats.large_bboxes
            },
            split_distribution=stats.split_distribution,
            scan_status=stats.scan_status,
            last_scan_time=stats.last_scan_time
        )
        
        return APIResponse.success_response(
            data=response_data,
            message="获取统计信息成功" if stats.scan_status == "completed" else "统计信息计算中"
        )
        
    except DatasetStatisticsError as e:
        logger.error(f"获取数据集统计信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"统计失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"获取数据集统计信息时发生错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计信息失败，请稍后重试"
        )


@router.post("/{id}/statistics/refresh", response_model=APIResponse[DatasetStatisticsResponse])
async def refresh_dataset_statistics_api(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DatasetStatisticsResponse]:
    """
    刷新数据集统计信息
    
    强制重新扫描labels文件并计算统计数据。
    
    Args:
        id: 数据集ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        更新后的统计信息
    """
    # 检查管理员权限
    check_admin_permission(current_user)
    
    # 检查数据集是否存在
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    try:
        # 强制刷新统计信息
        service = DatasetStatisticsService(db)
        stats = await service.analyze_and_save(id)
        
        response_data = DatasetStatisticsResponse(
            dataset_id=id,
            total_images=stats.total_images,
            total_annotations=stats.total_annotations,
            avg_annotations_per_image=round(stats.avg_annotations_per_image, 2),
            images_with_annotations=stats.images_with_annotations,
            images_without_annotations=stats.images_without_annotations,
            class_count=stats.class_count,
            class_distribution=[
                item for item in stats.class_distribution
            ],
            size_distribution=[
                item for item in stats.image_sizes
            ],
            bbox_distribution={
                "avg_width": round(stats.avg_bbox_width, 2),
                "avg_height": round(stats.avg_bbox_height, 2),
                "avg_aspect_ratio": round(stats.avg_bbox_aspect_ratio, 2),
                "small_boxes": stats.small_bboxes,
                "medium_boxes": stats.medium_bboxes,
                "large_boxes": stats.large_bboxes
            },
            split_distribution=stats.split_distribution,
            scan_status=stats.scan_status,
            last_scan_time=stats.last_scan_time
        )
        
        return APIResponse.success_response(
            data=response_data,
            message="统计信息已刷新"
        )
        
    except DatasetStatisticsError as e:
        logger.error(f"刷新数据集统计信息失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刷新失败: {str(e)}"
        )
    except Exception as e:
        logger.error(f"刷新数据集统计信息时发生错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刷新统计信息失败"
        )


@router.get("/{id}/chart-data", response_model=APIResponse[DatasetChartDataResponse])
async def get_dataset_chart_data_api(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse[DatasetChartDataResponse]:
    """
    获取数据集图表展示数据
    
    返回适合前端图表库（如Recharts）使用的数据格式。
    
    Args:
        id: 数据集ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        图表数据
    """
    # 检查数据集访问权限
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    check_dataset_access(dataset, current_user)
    
    try:
        service = DatasetStatisticsService(db)
        chart_data = await service.get_chart_data(id)
        
        if not chart_data:
            # 如果没有数据，触发分析
            logger.info(f"数据集 {id} 没有图表数据，触发分析...")
            stats = await service.get_or_create_statistics(id)
            chart_data = stats.to_chart_data()
        
        logger.debug(f"返回图表数据: {chart_data}")
        
        return APIResponse.success_response(
            data=DatasetChartDataResponse(**chart_data)
        )
        
    except Exception as e:
        logger.error(f"获取图表数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取图表数据失败"
        )


@router.delete("/{id}/statistics", response_model=APIResponse)
async def delete_dataset_statistics_api(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> APIResponse:
    """
    删除数据集统计信息
    
    仅管理员可操作，下次获取时会自动重新计算。
    
    Args:
        id: 数据集ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        操作结果
    """
    check_admin_permission(current_user)
    
    service = DatasetStatisticsService(db)
    deleted = await service.delete_statistics(id)
    
    if deleted:
        return APIResponse.success_response(message="统计信息已删除")
    else:
        return APIResponse.success_response(message="统计信息不存在")


# ==================== 数据集导出 API ====================

@router.get("/{id}/export")
async def export_dataset(
    id: str,
    format: str = Query("original", description="导出格式: original/yolo/coco/voc"),
    splits: Optional[str] = Query(None, description="导出的划分，逗号分隔如: train,val,test"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    导出数据集为ZIP文件
    
    支持导出为不同格式，可选择要包含的数据划分。
    
    Args:
        id: 数据集ID
        format: 导出格式，original表示保持原格式
        splits: 要导出的划分，默认全部
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        ZIP文件下载
    """
    # 获取数据集
    dataset_result = await db.execute(
        select(Dataset).where(Dataset.id == id)
    )
    dataset = dataset_result.scalar_one_or_none()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="数据集不存在"
        )
    
    # 检查访问权限
    check_dataset_access(dataset, current_user)
    
    # 解析要导出的划分
    split_list = ["train", "val", "test"]
    if splits:
        split_list = [s.strip() for s in splits.split(",")]
    
    # 确定导出格式
    target_format = format.upper()
    if target_format == "ORIGINAL":
        target_format = dataset.format
    
    if target_format not in ALLOWED_DATASET_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的导出格式: {format}"
        )
    
    try:
        # 创建临时导出目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = os.path.join(settings.upload_dir, "exports", f"{dataset.name}_export_{timestamp}")
        os.makedirs(export_dir, exist_ok=True)
        
        # 如果需要格式转换
        if target_format != dataset.format:
            logger.info(f"导出时转换格式: {dataset.format} -> {target_format}")
            
            # 解析当前数据集
            from app.utils.dataset_parser import DatasetAnalyzer, DatasetConverter
            analyzer = DatasetAnalyzer(dataset.path, dataset.format.lower())
            dataset_info = analyzer._dataset_info
            
            if not dataset_info:
                analysis_result = analyzer.analyze_labels()
                dataset_info = analyzer._dataset_info
            
            if not dataset_info:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="无法解析数据集"
                )
            
            # 更新类别名称
            dataset_info.class_names = dataset.class_names
            
            # 转换格式
            converter = DatasetConverter()
            
            if target_format == "COCO":
                source_path = await converter.to_coco_async(dataset_info, export_dir)
            elif target_format == "VOC":
                source_path = await converter.to_voc_async(dataset_info, export_dir)
            elif target_format == "YOLO":
                source_path = await converter.to_yolo_async(dataset_info, export_dir)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的目标格式: {target_format}"
                )
        else:
            # 保持原格式，直接复制
            source_path = dataset.path
        
        # 创建ZIP文件
        zip_filename = f"{dataset.name}_{target_format.lower()}_export_{timestamp}.zip"
        zip_path = os.path.join(settings.upload_dir, "exports", zip_filename)
        
        # 打包数据集
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_path):
                for file in files:
                    # 检查是否是指定的划分
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, source_path)
                    
                    # 根据划分过滤
                    include_file = False
                    for split in split_list:
                        if split in relative_path.lower():
                            include_file = True
                            break
                    
                    # 标注文件和配置文件始终包含
                    if file.endswith(('.json', '.xml', '.yaml', 'labels.txt')):
                        include_file = True
                    
                    if include_file:
                        zipf.write(file_path, relative_path)
        
        # 清理临时目录（如果不是原始格式）
        if target_format != dataset.format and os.path.exists(export_dir):
            shutil.rmtree(export_dir)
        
        # 记录敏感操作日志
        logger.info(
            f"用户 {current_user.user_id} (角色: {current_user.role}) 导出数据集: "
            f"dataset_id={id}, name={dataset.name}, "
            f"format={target_format}, splits={split_list}, "
            f"zip_file={zip_filename}"
        )
        
        # 返回ZIP文件
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=zip_filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出数据集失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出失败: {str(e)}"
        )


@router.get("/{id}/export/status")
async def get_export_status(
    id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取导出任务状态
    
    Args:
        id: 数据集ID
        current_user: 当前用户
        db: 数据库会话
        
    Returns:
        导出任务状态
    """
    # TODO: 实现导出任务状态跟踪
    return APIResponse.success_response(
        data={"status": "pending", "progress": 0},
        message="导出功能已实现，暂不支持异步状态跟踪"
    )
