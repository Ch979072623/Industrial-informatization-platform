"""
数据集统计相关 Schema

提供数据集统计信息的Pydantic模型定义。
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ClassDistributionItem(BaseModel):
    """类别分布项 Schema"""
    class_name: str = Field(description="类别名称")
    count: int = Field(ge=0, description="该类别标注数量")
    percentage: float = Field(ge=0, le=100, description="占比百分比")


class ImageSizeDistributionItem(BaseModel):
    """图像尺寸分布项 Schema"""
    width: int = Field(gt=0, description="图像宽度")
    height: int = Field(gt=0, description="图像高度")
    count: int = Field(ge=0, description="该尺寸图像数量")


class BBoxDistributionItem(BaseModel):
    """标注框分布 Schema"""
    avg_width: float = Field(ge=0, description="平均框宽度")
    avg_height: float = Field(ge=0, description="平均框高度")
    avg_aspect_ratio: float = Field(gt=0, description="平均宽高比")
    small_boxes: int = Field(ge=0, description="小目标数量（< 32x32）")
    medium_boxes: int = Field(ge=0, description="中目标数量（32x32 ~ 96x96）")
    large_boxes: int = Field(ge=0, description="大目标数量（> 96x96）")


class SplitDistributionItem(BaseModel):
    """数据集划分分布项 Schema"""
    name: str = Field(description="划分名称")
    value: int = Field(ge=0, description="图像数量")
    fill: str = Field(description="图表颜色")


class DatasetStatisticsBase(BaseModel):
    """数据集统计基础 Schema"""
    total_images: int = Field(ge=0, description="图像总数")
    total_annotations: int = Field(ge=0, description="标注框总数")
    avg_annotations_per_image: float = Field(ge=0, description="平均每图标注数")
    images_with_annotations: int = Field(ge=0, description="有标注的图像数量")
    images_without_annotations: int = Field(ge=0, description="无标注的图像数量")
    class_count: int = Field(ge=0, description="类别数量")


class DatasetStatisticsCreate(DatasetStatisticsBase):
    """创建数据集统计请求 Schema"""
    class_distribution: List[ClassDistributionItem] = Field(
        default_factory=list, 
        description="类别分布统计"
    )
    size_distribution: List[ImageSizeDistributionItem] = Field(
        default_factory=list,
        description="图像尺寸分布"
    )
    bbox_distribution: BBoxDistributionItem = Field(
        description="标注框分布统计"
    )
    split_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="训练/验证/测试集分布"
    )


class DatasetStatisticsResponse(DatasetStatisticsBase):
    """数据集统计响应 Schema"""
    dataset_id: str = Field(description="数据集ID")
    class_distribution: List[ClassDistributionItem] = Field(
        default_factory=list,
        description="类别分布统计"
    )
    size_distribution: List[ImageSizeDistributionItem] = Field(
        default_factory=list,
        description="图像尺寸分布"
    )
    bbox_distribution: BBoxDistributionItem = Field(
        description="标注框分布统计"
    )
    split_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="训练/验证/测试集分布"
    )
    scan_status: str = Field(
        default="pending",
        description="扫描状态: pending/running/completed/failed"
    )
    last_scan_time: Optional[datetime] = Field(
        default=None,
        description="上次扫描时间"
    )
    
    model_config = ConfigDict(from_attributes=True)


class DatasetChartSummary(BaseModel):
    """图表数据汇总 Schema"""
    total_images: int = Field(ge=0, description="图像总数")
    total_annotations: int = Field(ge=0, description="标注总数")
    avg_annotations_per_image: float = Field(ge=0, description="平均每图标注数")
    class_count: int = Field(ge=0, description="类别数量")
    images_with_annotations: int = Field(ge=0, description="有标注图像数")
    images_without_annotations: int = Field(ge=0, description="无标注图像数")


class DatasetChartBboxDistribution(BaseModel):
    """图表标注框分布 Schema"""
    avg_width: float = Field(ge=0, description="平均宽度")
    avg_height: float = Field(ge=0, description="平均高度")
    avg_aspect_ratio: float = Field(gt=0, description="平均宽高比")
    small: int = Field(ge=0, description="小目标数量")
    medium: int = Field(ge=0, description="中目标数量")
    large: int = Field(ge=0, description="大目标数量")


class DatasetChartDataResponse(BaseModel):
    """数据集图表数据响应 Schema
    
    为前端图表库（如Recharts）优化的数据格式
    """
    class_distribution: List[ClassDistributionItem] = Field(
        default_factory=list,
        description="类别分布数据（用于柱状图）"
    )
    image_sizes: List[ImageSizeDistributionItem] = Field(
        default_factory=list,
        description="图像尺寸数据（用于散点图）"
    )
    split_distribution: List[SplitDistributionItem] = Field(
        default_factory=list,
        description="划分分布数据（用于饼图）"
    )
    bbox_distribution: DatasetChartBboxDistribution = Field(
        description="标注框分布数据"
    )
    summary: DatasetChartSummary = Field(
        description="汇总统计数据"
    )
    
    model_config = ConfigDict(from_attributes=True)


class DatasetStatisticsUpdateRequest(BaseModel):
    """更新统计信息请求 Schema（内部使用）"""
    force_refresh: bool = Field(
        default=False,
        description="是否强制重新计算"
    )


class StatisticsStatusResponse(BaseModel):
    """统计状态响应 Schema"""
    dataset_id: str = Field(description="数据集ID")
    status: str = Field(description="扫描状态")
    last_scan_time: Optional[datetime] = Field(description="上次扫描时间")
    error_message: Optional[str] = Field(description="错误信息")
