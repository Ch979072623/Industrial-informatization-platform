"""
数据集相关 Schema
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# 导入统计数据Schema以便统一导出
from app.schemas.dataset_statistics import (
    ClassDistributionItem,
    ImageSizeDistributionItem,
    BBoxDistributionItem,
    DatasetStatisticsResponse,
    DatasetStatisticsCreate,
    DatasetChartDataResponse,
    SplitDistributionItem,
    DatasetChartSummary,
    DatasetChartBboxDistribution,
)


class DatasetBase(BaseModel):
    """数据集基础 Schema"""
    name: str = Field(min_length=1, max_length=100, description="数据集名称")
    description: Optional[str] = Field(default=None, description="数据集描述")
    format: str = Field(pattern="^(YOLO|COCO|VOC)$", description="数据格式")
    class_names: List[str] = Field(default_factory=list, description="类别名称列表")
    split_ratio: Dict[str, float] = Field(
        default_factory=lambda: {"train": 0.7, "val": 0.2, "test": 0.1},
        description="数据集划分比例"
    )


class DatasetCreate(DatasetBase):
    """数据集创建 Schema"""
    production_line_id: Optional[str] = Field(default=None, description="所属产线ID")


class DatasetUpdate(BaseModel):
    """数据集更新 Schema"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None)
    class_names: Optional[List[str]] = Field(default=None)
    split_ratio: Optional[Dict[str, float]] = Field(default=None)


class DatasetImageResponse(BaseModel):
    """数据集图像响应 Schema"""
    id: str = Field(description="图像ID")
    filename: str = Field(description="文件名")
    filepath: str = Field(description="文件路径")
    split: str = Field(description="数据划分")
    width: Optional[int] = Field(description="图像宽度")
    height: Optional[int] = Field(description="图像高度")
    annotation_path: Optional[str] = Field(description="标注路径")
    created_at: datetime = Field(description="创建时间")
    
    model_config = ConfigDict(from_attributes=True)


class DatasetResponse(DatasetBase):
    """数据集响应 Schema"""
    id: str = Field(description="数据集ID")
    path: str = Field(description="存储路径")
    total_images: int = Field(description="图像总数")
    production_line_id: Optional[str] = Field(default=None, description="所属产线ID")
    created_by: str = Field(description="创建者ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class DatasetDetailResponse(DatasetResponse):
    """数据集详情响应 Schema"""
    images: List[DatasetImageResponse] = Field(default_factory=list, description="图像列表")


# ==================== 新增Schema定义 ====================

class DatasetUploadRequest(BaseModel):
    """数据集上传请求 Schema"""
    name: str = Field(
        min_length=1, 
        max_length=100, 
        description="数据集名称"
    )
    description: Optional[str] = Field(
        default=None, 
        description="数据集描述"
    )
    format: str = Field(
        pattern="^(YOLO|COCO|VOC)$", 
        description="数据格式: YOLO/COCO/VOC"
    )
    class_names: Optional[List[str]] = Field(
        default=None, 
        description="类别名称列表，如从标注文件中自动提取可省略"
    )
    split_ratio: Dict[str, float] = Field(
        default_factory=lambda: {"train": 0.7, "val": 0.2, "test": 0.1},
        description="数据集划分比例，各比例之和应等于1.0"
    )
    production_line_id: Optional[str] = Field(default=None, description="所属产线ID")
    overwrite: bool = Field(
        default=False, 
        description="是否覆盖已存在的同名数据集"
    )


class ClassDistribution(BaseModel):
    """类别分布 Schema"""
    class_name: str = Field(description="类别名称")
    count: int = Field(ge=0, description="该类别的标注数量")
    percentage: float = Field(
        ge=0, 
        le=100, 
        description="该类别占总标注的百分比"
    )


class ImageSizeDistribution(BaseModel):
    """图像尺寸分布 Schema"""
    width: int = Field(gt=0, description="图像宽度")
    height: int = Field(gt=0, description="图像高度")
    count: int = Field(ge=0, description="该尺寸图像数量")


class BoundingBoxDistribution(BaseModel):
    """标注框分布 Schema"""
    avg_width: float = Field(ge=0, description="平均框宽度")
    avg_height: float = Field(ge=0, description="平均框高度")
    avg_aspect_ratio: float = Field(gt=0, description="平均宽高比")
    small_boxes: int = Field(ge=0, description="小目标数量（< 32x32）")
    medium_boxes: int = Field(ge=0, description="中目标数量（32x32 ~ 96x96）")
    large_boxes: int = Field(ge=0, description="大目标数量（> 96x96）")


class DatasetStatisticsResponse(BaseModel):
    """数据集统计响应 Schema"""
    dataset_id: str = Field(description="数据集ID")
    total_images: int = Field(ge=0, description="图像总数")
    total_annotations: int = Field(ge=0, description="标注框总数")
    avg_annotations_per_image: float = Field(ge=0, description="平均每图标注数")
    images_with_annotations: int = Field(ge=0, description="有标注的图像数量")
    images_without_annotations: int = Field(ge=0, description="无标注的图像数量")
    class_distribution: List[ClassDistribution] = Field(
        default_factory=list, 
        description="类别分布统计"
    )
    size_distribution: List[ImageSizeDistribution] = Field(
        default_factory=list, 
        description="图像尺寸分布"
    )
    bbox_distribution: BoundingBoxDistribution = Field(
        description="标注框分布统计"
    )
    split_distribution: Dict[str, int] = Field(
        default_factory=dict, 
        description="训练/验证/测试集分布"
    )


class DatasetSplitRequest(BaseModel):
    """数据集划分请求 Schema"""
    split_ratio: Dict[str, float] = Field(
        description="划分比例，如 {'train': 0.7, 'val': 0.2, 'test': 0.1}"
    )
    random_seed: Optional[int] = Field(
        default=42, 
        ge=0, 
        description="随机种子，保证可复现"
    )
    stratify: bool = Field(
        default=True, 
        description="是否按类别分层抽样"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "split_ratio": {"train": 0.7, "val": 0.2, "test": 0.1},
            "random_seed": 42,
            "stratify": True
        }
    })


class DatasetConvertRequest(BaseModel):
    """数据集格式转换请求 Schema"""
    target_format: str = Field(
        pattern="^(YOLO|COCO|VOC)$", 
        description="目标格式: YOLO/COCO/VOC"
    )
    output_path: Optional[str] = Field(
        default=None, 
        description="输出路径，默认使用原路径"
    )
    preserve_original: bool = Field(
        default=True, 
        description="是否保留原始格式数据"
    )
    copy_images: bool = Field(
        default=True, 
        description="是否复制图像文件"
    )


class DatasetImageListResponse(BaseModel):
    """图片列表响应 Schema"""
    total: int = Field(ge=0, description="总图像数量")
    page: int = Field(ge=1, description="当前页码")
    page_size: int = Field(ge=1, le=1000, description="每页数量")
    images: List[DatasetImageResponse] = Field(
        default_factory=list, 
        description="图像列表"
    )


class PreviewImageInfo(BaseModel):
    """预览图像信息 Schema"""
    image_id: str = Field(description="图像ID")
    filename: str = Field(description="文件名")
    filepath: str = Field(description="文件路径")
    width: int = Field(gt=0, description="图像宽度")
    height: int = Field(gt=0, description="图像高度")
    annotation_count: int = Field(ge=0, description="标注数量")


class DatasetPreviewResponse(BaseModel):
    """数据集预览响应 Schema"""
    dataset_id: str = Field(description="数据集ID")
    dataset_name: str = Field(description="数据集名称")
    total_images: int = Field(ge=0, description="图像总数")
    sample_images: List[PreviewImageInfo] = Field(
        default_factory=list, 
        description="样本图像列表（预览用）"
    )
    class_names: List[str] = Field(
        default_factory=list, 
        description="类别名称列表"
    )
    format: str = Field(description="数据格式")


class DatasetListQuery(BaseModel):
    """数据集列表查询参数 Schema"""
    # 搜索参数
    keyword: Optional[str] = Field(
        default=None, 
        min_length=1, 
        max_length=100, 
        description="搜索关键词（匹配名称和描述）"
    )
    
    # 筛选参数
    format: Optional[str] = Field(
        default=None, 
        pattern="^(YOLO|COCO|VOC)$", 
        description="数据格式筛选"
    )
    production_line_id: Optional[str] = Field(
        default=None, 
        description="所属产线ID筛选"
    )
    created_by: Optional[str] = Field(
        default=None, 
        description="创建者ID筛选"
    )
    min_images: Optional[int] = Field(
        default=None, 
        ge=0, 
        description="最小图像数量"
    )
    max_images: Optional[int] = Field(
        default=None, 
        ge=0, 
        description="最大图像数量"
    )
    
    # 时间筛选
    created_after: Optional[datetime] = Field(
        default=None, 
        description="创建时间起始"
    )
    created_before: Optional[datetime] = Field(
        default=None, 
        description="创建时间截止"
    )
    
    # 排序参数
    sort_by: str = Field(
        default="created_at", 
        pattern="^(name|created_at|updated_at|total_images)$", 
        description="排序字段"
    )
    sort_order: str = Field(
        default="desc", 
        pattern="^(asc|desc)$", 
        description="排序方向: asc/desc"
    )
    
    # 分页参数
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "keyword": "缺陷",
            "format": "YOLO",
            "min_images": 100,
            "sort_by": "created_at",
            "sort_order": "desc",
            "page": 1,
            "page_size": 20
        }
    })



# ==================== 标签分析和预览 Schema ====================

class LabelAnalysisResponse(BaseModel):
    """标签分析响应 Schema"""
    class_names: List[str] = Field(default_factory=list, description="类别名称列表")
    class_count: int = Field(ge=0, description="类别数量")
    annotations_per_class: Dict[str, int] = Field(
        default_factory=dict, 
        description="每个类别的标注数量"
    )
    images_per_class: Dict[str, int] = Field(
        default_factory=dict, 
        description="包含每个类别的图像数量"
    )
    total_annotations: int = Field(ge=0, description="总标注数量")
    yaml_config: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="YAML配置内容"
    )
    has_yaml: bool = Field(default=False, description="是否存在YAML文件")


class PreviewImageInfo(BaseModel):
    """预览图像信息 Schema"""
    id: str = Field(description="图像ID")
    filename: str = Field(description="文件名")
    filepath: str = Field(description="文件路径")
    width: int = Field(gt=0, description="图像宽度")
    height: int = Field(gt=0, description="图像高度")
    split: str = Field(description="数据划分")
    annotation_count: int = Field(ge=0, description="标注数量")


class DatasetPreviewResponse(BaseModel):
    """数据集预览响应 Schema"""
    dataset_id: str = Field(description="数据集ID")
    total_images: int = Field(ge=0, description="图像总数")
    preview_images: List[PreviewImageInfo] = Field(
        default_factory=list, 
        description="预览图像列表"
    )


class UpdateLabelsRequest(BaseModel):
    """更新标签请求 Schema"""
    class_names: List[str] = Field(
        min_length=1,
        description="类别名称列表"
    )
    save_to_yaml: bool = Field(
        default=True, 
        description="是否保存到YAML文件"
    )


class UpdateLabelsResponse(BaseModel):
    """更新标签响应 Schema"""
    success: bool = Field(description="是否成功")
    class_names: List[str] = Field(description="更新后的类别名称")
    yaml_saved: bool = Field(description="YAML文件是否已保存")


class YamlUploadRequest(BaseModel):
    """上传YAML文件请求 Schema"""
    content: str = Field(description="YAML文件内容")


class DatasetCardInfoResponse(BaseModel):
    """数据集卡片信息响应 Schema（用于列表页展示）"""
    id: str = Field(description="数据集ID")
    name: str = Field(description="数据集名称")
    description: Optional[str] = Field(description="数据集描述")
    format: str = Field(description="数据格式")
    total_images: int = Field(ge=0, description="图像总数")
    class_count: int = Field(ge=0, description="类别数量")
    class_names: List[str] = Field(default_factory=list, description="类别名称列表")
    preview_images: List[PreviewImageInfo] = Field(
        default_factory=list, 
        description="前20张预览图像"
    )
    annotations_per_class: Dict[str, int] = Field(
        default_factory=dict, 
        description="每个类别的标注数量"
    )
    created_at: datetime = Field(description="创建时间")
