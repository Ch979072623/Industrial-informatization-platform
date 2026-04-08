"""
数据生成相关 Schema
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ==================== 生成器 Schema ====================

class GeneratorInfo(BaseModel):
    """生成器信息 Schema"""
    name: str = Field(..., description="生成器名称")
    description: str = Field(..., description="生成器描述")
    version: str = Field(default="1.0.0", description="版本")
    is_builtin: bool = Field(default=True, description="是否为内置生成器")
    config_schema: Dict[str, Any] = Field(default_factory=dict, description="配置参数 JSON Schema")
    supported_formats: List[str] = Field(default_factory=list, description="支持的标注格式")
    default_config: Dict[str, Any] = Field(default_factory=dict, description="默认配置")


class GeneratorListResponse(BaseModel):
    """生成器列表响应"""
    generators: List[GeneratorInfo] = Field(..., description="生成器列表")


# ==================== 配置验证 Schema ====================

class ValidateConfigRequest(BaseModel):
    """验证配置请求 Schema"""
    generator_name: str = Field(..., description="生成器名称")
    config: Dict[str, Any] = Field(..., description="配置参数")


class ValidateConfigResponse(BaseModel):
    """验证配置响应 Schema"""
    is_valid: bool = Field(..., description="是否有效")
    errors: Optional[List[Dict[str, str]]] = Field(default=None, description="错误列表")
    
    
class ConfigError(BaseModel):
    """配置错误 Schema"""
    field: str = Field(..., description="字段名")
    message: str = Field(..., description="错误信息")


# ==================== 生成预览 Schema ====================

class GenerationPreviewRequest(BaseModel):
    """生成预览请求 Schema"""
    generator_name: str = Field(..., description="生成器名称")
    config: Dict[str, Any] = Field(..., description="完整配置")
    seed: Optional[int] = Field(default=None, description="随机种子")
    base_image_id: Optional[str] = Field(default=None, description="指定基底图像ID")


class PreviewAnnotation(BaseModel):
    """预览标注 Schema"""
    boxes: List[List[float]] = Field(default_factory=list, description="边界框 [[x1, y1, x2, y2], ...]")
    labels: List[int] = Field(default_factory=list, description="类别ID列表")
    scores: List[float] = Field(default_factory=list, description="置信度列表")


class GenerationMetadata(BaseModel):
    """生成元数据 Schema"""
    num_defects: int = Field(default=0, description="缺陷数量")
    color_match_mode: Optional[str] = Field(default=None, description="颜色匹配模式")
    placement_strategy: Optional[str] = Field(default=None, description="放置策略")
    fusion_quality_scores: Optional[List[float]] = Field(default=None, description="融合质量分数列表")
    average_quality: float = Field(default=0, description="平均质量分数")
    api_type: Optional[str] = Field(default=None, description="API类型")
    api_call_time: Optional[float] = Field(default=None, description="API调用时间")


class GenerationPreviewResponse(BaseModel):
    """生成预览响应 Schema"""
    original_image: str = Field(..., description="原始图像 base64")
    generated_image: str = Field(..., description="生成图像 base64")
    annotations: PreviewAnnotation = Field(default_factory=PreviewAnnotation, description="标注信息")
    metadata: GenerationMetadata = Field(default_factory=GenerationMetadata, description="元数据")
    generation_time: float = Field(..., description="生成耗时（秒）")


# ==================== 生成任务 Schema ====================

class GenerationTemplateBase(BaseModel):
    """生成模板基础 Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: Optional[str] = Field(default=None, description="模板描述")
    generator_name: str = Field(..., description="生成器名称")
    config: Dict[str, Any] = Field(default_factory=dict, description="生成配置")


class GenerationTemplateCreate(GenerationTemplateBase):
    """创建生成模板请求 Schema"""
    pass


class GenerationTemplateUpdate(BaseModel):
    """更新生成模板请求 Schema"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None)
    config: Optional[Dict[str, Any]] = Field(default=None)


class GenerationTemplateResponse(GenerationTemplateBase):
    """生成模板响应 Schema"""
    id: str = Field(..., description="模板ID")
    is_preset: bool = Field(default=False, description="是否为系统预设")
    created_by: str = Field(..., description="创建者ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 执行任务 Schema ====================

class GenerationJobBase(BaseModel):
    """生成任务基础 Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    generator_name: str = Field(..., description="生成器名称")
    config: Dict[str, Any] = Field(..., description="生成配置")
    count: int = Field(default=100, ge=1, le=10000, description="生成数量")
    annotation_format: str = Field(default="yolo", pattern="^(yolo|coco|voc)$", description="标注格式")


class GenerationJobCreate(GenerationJobBase):
    """创建生成任务请求 Schema"""
    output_dataset_name: Optional[str] = Field(default=None, description="输出数据集名称")


class GenerationJobUpdate(BaseModel):
    """更新生成任务请求 Schema"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    status: Optional[str] = Field(default=None, pattern="^(pending|running|paused|completed|failed|cancelled)$")


class GenerationJobResponse(GenerationJobBase):
    """生成任务响应 Schema"""
    id: str = Field(..., description="任务ID")
    status: str = Field(default="pending", description="任务状态")
    progress: float = Field(default=0.0, description="进度百分比")
    processed_count: int = Field(default=0, description="已处理数量")
    total_count: int = Field(default=0, description="总数量")
    success_count: int = Field(default=0, description="成功数量")
    failed_count: int = Field(default=0, description="失败数量")
    output_dataset_id: Optional[str] = Field(default=None, description="输出数据集ID")
    celery_task_id: Optional[str] = Field(default=None, description="Celery任务ID")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    execution_logs: List[Dict[str, Any]] = Field(default_factory=list, description="执行日志")
    quality_report: Optional[Dict[str, Any]] = Field(default=None, description="质量报告")
    timing_stats: Optional[Dict[str, Any]] = Field(default=None, description="时间统计")
    created_by: str = Field(..., description="创建者ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class GenerationJobListQuery(BaseModel):
    """生成任务列表查询 Schema"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    status: Optional[str] = Field(default=None, pattern="^(pending|running|paused|completed|failed|cancelled)$")
    generator_name: Optional[str] = Field(default=None, description="生成器名称")


class ExecuteGenerationRequest(BaseModel):
    """执行生成请求 Schema"""
    generator_name: str = Field(..., description="生成器名称")
    config: Dict[str, Any] = Field(..., description="完整配置")
    count: int = Field(default=100, ge=1, le=10000, description="生成数量")
    output_dataset_name: str = Field(..., min_length=1, max_length=100, description="输出数据集名称")
    annotation_format: str = Field(default="yolo", pattern="^(yolo|coco|voc)$", description="标注格式")


class ExecuteGenerationResponse(BaseModel):
    """执行生成响应 Schema"""
    task_id: str = Field(..., description="任务ID")
    estimated_time: float = Field(..., description="预计执行时间（秒）")
    estimated_disk_usage: float = Field(..., description="预计占用空间（MB）")


# ==================== 任务控制 Schema ====================

class JobControlRequest(BaseModel):
    """任务控制请求 Schema"""
    action: str = Field(..., pattern="^(pause|resume|cancel)$", description="控制动作")


class JobControlResponse(BaseModel):
    """任务控制响应 Schema"""
    success: bool = Field(..., description="是否成功")
    new_status: str = Field(..., description="新状态")
    message: str = Field(..., description="消息")


# ==================== 任务进度 Schema ====================

class GenerationErrorDetail(BaseModel):
    """生成错误详情 Schema"""
    image_index: int = Field(..., description="图像索引")
    image_name: Optional[str] = Field(default=None, description="图像名称")
    error: str = Field(..., description="错误信息")


class GenerationJobProgressResponse(BaseModel):
    """生成任务进度响应 Schema"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态")
    progress: float = Field(..., description="进度百分比")
    processed_count: int = Field(..., description="已处理数量")
    total_count: int = Field(..., description="总数量")
    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    current_image: Optional[str] = Field(default=None, description="当前处理图像")
    estimated_remaining_time: Optional[int] = Field(default=None, description="预计剩余时间（秒）")
    errors: List[GenerationErrorDetail] = Field(default_factory=list, description="错误列表")


# ==================== 质量报告 Schema ====================

class QualityReportImageDetail(BaseModel):
    """质量报告图像详情 Schema"""
    filename: str = Field(..., description="文件名")
    defect_count: int = Field(..., description="缺陷数量")
    quality_score: float = Field(..., description="质量分数")
    generation_time: float = Field(..., description="生成耗时（秒）")


class QualityReportResponse(BaseModel):
    """质量报告响应 Schema"""
    task_id: str = Field(..., description="任务ID")
    total_images: int = Field(..., description="总图像数")
    success_count: int = Field(..., description="成功数量")
    failed_count: int = Field(..., description="失败数量")
    average_quality_score: float = Field(..., description="平均质量分数")
    image_details: List[QualityReportImageDetail] = Field(..., description="图像详情列表")
    failed_images: List[GenerationErrorDetail] = Field(..., description="失败图像列表")
    quality_distribution: Dict[str, int] = Field(..., description="质量分布")
    class_distribution: Dict[str, int] = Field(..., description="类别分布")


# ==================== 合并结果 Schema ====================

class MergeGenerationRequest(BaseModel):
    """合并生成结果请求 Schema"""
    task_id: str = Field(..., description="任务ID")
    merge_mode: str = Field(..., pattern="^(create_new|append|replace)$", description="合并模式")
    target_dataset_id: Optional[str] = Field(default=None, description="目标数据集ID（非 create_new 时必填）")
    new_dataset_name: Optional[str] = Field(default=None, description="新数据集名称（create_new 时必填）")
    class_mapping: Optional[Dict[str, int]] = Field(default=None, description="类别映射")


class MergeGenerationResponse(BaseModel):
    """合并生成结果响应 Schema"""
    merge_task_id: str = Field(..., description="合并任务ID")
    target_dataset_id: str = Field(..., description="目标数据集ID")
    merged_count: int = Field(..., description="合并数量")


# ==================== 缓存管理 Schema ====================

class DefectCacheInfo(BaseModel):
    """缺陷缓存信息 Schema"""
    cache_key: str = Field(..., description="缓存键")
    source_dataset_id: str = Field(..., description="源数据集ID")
    color_mode: str = Field(..., description="颜色匹配模式")
    defect_count: int = Field(..., description="缺陷数量")
    cache_size_mb: float = Field(..., description="缓存大小（MB）")
    expires_at: Optional[str] = Field(default=None, description="过期时间")
    created_at: str = Field(..., description="创建时间")


class DefectCacheListResponse(BaseModel):
    """缺陷缓存列表响应 Schema"""
    caches: List[DefectCacheInfo] = Field(..., description="缓存列表")
    total_size_mb: float = Field(..., description="总缓存大小（MB）")


class RefreshCacheRequest(BaseModel):
    """刷新缓存请求 Schema"""
    dataset_id: str = Field(..., description="数据集ID")
    color_mode: str = Field(default="standard", description="颜色匹配模式")


# ==================== 热力图 Schema ====================

class HeatmapGenerateRequest(BaseModel):
    """生成热力图请求 Schema"""
    type: str = Field(..., pattern="^(gaussian|edge|center)$", description="热力图类型")
    width: int = Field(..., ge=64, le=4096, description="宽度")
    height: int = Field(..., ge=64, le=4096, description="高度")
    params: Optional[Dict[str, Any]] = Field(default=None, description="额外参数")


class HeatmapGenerateResponse(BaseModel):
    """生成热力图响应 Schema"""
    heatmap_image: str = Field(..., description="热力图 base64")
    type: str = Field(..., description="类型")
