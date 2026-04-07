"""
数据增强相关 Schema
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ==================== 增强操作 Schema ====================

class AugmentationOperationBase(BaseModel):
    """增强操作基础 Schema"""
    operation_type: str = Field(..., description="操作类型标识")
    name: str = Field(..., description="操作显示名称")
    description: Optional[str] = Field(default=None, description="操作描述")
    probability: float = Field(default=1.0, ge=0.0, le=1.0, description="应用概率 (0-1)")
    enabled: bool = Field(default=True, description="是否启用")
    order: int = Field(default=0, ge=0, description="执行顺序")


class HorizontalFlipOperation(AugmentationOperationBase):
    """水平翻转操作"""
    operation_type: Literal["horizontal_flip"] = "horizontal_flip"
    name: Literal["水平翻转"] = "水平翻转"


class VerticalFlipOperation(AugmentationOperationBase):
    """垂直翻转操作"""
    operation_type: Literal["vertical_flip"] = "vertical_flip"
    name: Literal["垂直翻转"] = "垂直翻转"


class RandomRotateOperation(AugmentationOperationBase):
    """随机旋转操作"""
    operation_type: Literal["random_rotate"] = "random_rotate"
    name: Literal["随机旋转"] = "随机旋转"
    angle_range: List[float] = Field(
        default=[-180.0, 180.0],
        description="旋转角度范围 [-180, 180]"
    )
    
    @field_validator('angle_range')
    @classmethod
    def validate_angle_range(cls, v):
        if len(v) != 2:
            raise ValueError('angle_range 必须包含两个值')
        if v[0] < -180 or v[1] > 180:
            raise ValueError('角度范围必须在 -180 到 180 之间')
        if v[0] > v[1]:
            raise ValueError('角度范围第一个值必须小于等于第二个值')
        return v


class RandomCropOperation(AugmentationOperationBase):
    """随机裁剪操作"""
    operation_type: Literal["random_crop"] = "random_crop"
    name: Literal["随机裁剪"] = "随机裁剪"
    crop_ratio: float = Field(default=0.8, ge=0.5, le=1.0, description="裁剪比例 (0.5-1.0)")


class ScaleOperation(AugmentationOperationBase):
    """缩放操作"""
    operation_type: Literal["scale"] = "scale"
    name: Literal["缩放"] = "缩放"
    scale_range: List[float] = Field(
        default=[0.8, 1.2],
        description="缩放范围 [0.5, 2.0]"
    )
    
    @field_validator('scale_range')
    @classmethod
    def validate_scale_range(cls, v):
        if len(v) != 2:
            raise ValueError('scale_range 必须包含两个值')
        if v[0] < 0.5 or v[1] > 2.0:
            raise ValueError('缩放范围必须在 0.5 到 2.0 之间')
        if v[0] > v[1]:
            raise ValueError('缩放范围第一个值必须小于等于第二个值')
        return v


class AffineTransformOperation(AugmentationOperationBase):
    """仿射变换操作"""
    operation_type: Literal["affine_transform"] = "affine_transform"
    name: Literal["仿射变换"] = "仿射变换"
    angle: float = Field(default=0.0, ge=-180.0, le=180.0, description="旋转角度")
    translate_x: float = Field(default=0.0, ge=-1.0, le=1.0, description="X方向平移比例")
    translate_y: float = Field(default=0.0, ge=-1.0, le=1.0, description="Y方向平移比例")
    scale: float = Field(default=1.0, ge=0.5, le=2.0, description="缩放比例")
    shear: float = Field(default=0.0, ge=-45.0, le=45.0, description="剪切角度")


class BrightnessAdjustmentOperation(AugmentationOperationBase):
    """亮度调整操作"""
    operation_type: Literal["brightness"] = "brightness"
    name: Literal["亮度调整"] = "亮度调整"
    brightness_range: List[float] = Field(
        default=[-30, 30],
        description="亮度调整范围 [-100, 100]"
    )
    
    @field_validator('brightness_range')
    @classmethod
    def validate_brightness_range(cls, v):
        if len(v) != 2:
            raise ValueError('brightness_range 必须包含两个值')
        if v[0] < -100 or v[1] > 100:
            raise ValueError('亮度范围必须在 -100 到 100 之间')
        if v[0] > v[1]:
            raise ValueError('亮度范围第一个值必须小于等于第二个值')
        return v


class ContrastAdjustmentOperation(AugmentationOperationBase):
    """对比度调整操作"""
    operation_type: Literal["contrast"] = "contrast"
    name: Literal["对比度调整"] = "对比度调整"
    contrast_range: List[float] = Field(
        default=[0.8, 1.2],
        description="对比度调整范围 [0.5, 2.0]"
    )
    
    @field_validator('contrast_range')
    @classmethod
    def validate_contrast_range(cls, v):
        if len(v) != 2:
            raise ValueError('contrast_range 必须包含两个值')
        if v[0] < 0.5 or v[1] > 2.0:
            raise ValueError('对比度范围必须在 0.5 到 2.0 之间')
        if v[0] > v[1]:
            raise ValueError('对比度范围第一个值必须小于等于第二个值')
        return v


class SaturationAdjustmentOperation(AugmentationOperationBase):
    """饱和度调整操作"""
    operation_type: Literal["saturation"] = "saturation"
    name: Literal["饱和度调整"] = "饱和度调整"
    saturation_range: List[float] = Field(
        default=[0.8, 1.2],
        description="饱和度调整范围 [0.5, 2.0]"
    )
    
    @field_validator('saturation_range')
    @classmethod
    def validate_saturation_range(cls, v):
        if len(v) != 2:
            raise ValueError('saturation_range 必须包含两个值')
        if v[0] < 0.5 or v[1] > 2.0:
            raise ValueError('饱和度范围必须在 0.5 到 2.0 之间')
        if v[0] > v[1]:
            raise ValueError('饱和度范围第一个值必须小于等于第二个值')
        return v


class HueJitterOperation(AugmentationOperationBase):
    """色调抖动操作"""
    operation_type: Literal["hue_jitter"] = "hue_jitter"
    name: Literal["色调抖动"] = "色调抖动"
    hue_range: List[int] = Field(
        default=[-10, 10],
        description="色调调整范围 [-30, 30]"
    )
    
    @field_validator('hue_range')
    @classmethod
    def validate_hue_range(cls, v):
        if len(v) != 2:
            raise ValueError('hue_range 必须包含两个值')
        if v[0] < -30 or v[1] > 30:
            raise ValueError('色调范围必须在 -30 到 30 之间')
        if v[0] > v[1]:
            raise ValueError('色调范围第一个值必须小于等于第二个值')
        return v


class HistogramEqualizationOperation(AugmentationOperationBase):
    """直方图均衡化操作"""
    operation_type: Literal["histogram_equalization"] = "histogram_equalization"
    name: Literal["直方图均衡化"] = "直方图均衡化"


class CLAHEOperation(AugmentationOperationBase):
    """CLAHE操作"""
    operation_type: Literal["clahe"] = "clahe"
    name: Literal["CLAHE自适应均衡"] = "CLAHE自适应均衡"
    clip_limit: float = Field(default=2.0, ge=1.0, le=10.0, description="对比度限制")
    tile_grid_size: int = Field(default=8, ge=4, le=16, description="网格大小")


class GaussianNoiseOperation(AugmentationOperationBase):
    """高斯噪声操作"""
    operation_type: Literal["gaussian_noise"] = "gaussian_noise"
    name: Literal["高斯噪声"] = "高斯噪声"
    std_range: List[float] = Field(
        default=[5.0, 15.0],
        description="标准差范围 [0, 50]"
    )
    
    @field_validator('std_range')
    @classmethod
    def validate_std_range(cls, v):
        if len(v) != 2:
            raise ValueError('std_range 必须包含两个值')
        if v[0] < 0 or v[1] > 50:
            raise ValueError('标准差范围必须在 0 到 50 之间')
        if v[0] > v[1]:
            raise ValueError('标准差范围第一个值必须小于等于第二个值')
        return v


class SaltPepperNoiseOperation(AugmentationOperationBase):
    """椒盐噪声操作"""
    operation_type: Literal["salt_pepper_noise"] = "salt_pepper_noise"
    name: Literal["椒盐噪声"] = "椒盐噪声"
    noise_ratio: float = Field(default=0.01, ge=0.0, le=0.1, description="噪声比例 (0-0.1)")


class GaussianBlurOperation(AugmentationOperationBase):
    """高斯模糊操作"""
    operation_type: Literal["gaussian_blur"] = "gaussian_blur"
    name: Literal["高斯模糊"] = "高斯模糊"
    kernel_size: int = Field(default=5, ge=3, le=15, description="核大小 (3-15，奇数)")
    sigma: float = Field(default=1.0, ge=0.1, le=5.0, description="标准差")
    
    @field_validator('kernel_size')
    @classmethod
    def validate_kernel_size(cls, v):
        if v % 2 == 0:
            raise ValueError('kernel_size 必须是奇数')
        return v


class MotionBlurOperation(AugmentationOperationBase):
    """运动模糊操作"""
    operation_type: Literal["motion_blur"] = "motion_blur"
    name: Literal["运动模糊"] = "运动模糊"
    kernel_size: int = Field(default=5, ge=3, le=15, description="核大小 (3-15，奇数)")
    angle: float = Field(default=0.0, ge=0.0, le=360.0, description="运动角度 (0-360)")
    
    @field_validator('kernel_size')
    @classmethod
    def validate_kernel_size(cls, v):
        if v % 2 == 0:
            raise ValueError('kernel_size 必须是奇数')
        return v


class MosaicOperation(AugmentationOperationBase):
    """Mosaic操作（4图拼接）"""
    operation_type: Literal["mosaic"] = "mosaic"
    name: Literal["Mosaic拼接"] = "Mosaic拼接"
    grid_size: int = Field(default=2, ge=2, le=4, description="网格大小 (2-4)")


class MixUpOperation(AugmentationOperationBase):
    """MixUp操作"""
    operation_type: Literal["mixup"] = "mixup"
    name: Literal["MixUp混合"] = "MixUp混合"
    alpha: float = Field(default=0.4, ge=0.1, le=1.0, description="Beta分布参数")


class CutOutOperation(AugmentationOperationBase):
    """CutOut操作"""
    operation_type: Literal["cutout"] = "cutout"
    name: Literal["CutOut擦除"] = "CutOut擦除"
    erase_ratio: float = Field(default=0.2, ge=0.1, le=0.5, description="擦除区域比例 (0.1-0.5)")
    max_erase_count: int = Field(default=1, ge=1, le=5, description="最大擦除块数 (1-5)")


class CutMixOperation(AugmentationOperationBase):
    """CutMix操作"""
    operation_type: Literal["cutmix"] = "cutmix"
    name: Literal["CutMix混合"] = "CutMix混合"
    alpha: float = Field(default=1.0, ge=0.1, le=2.0, description="Beta分布参数")


class CustomScriptOperation(AugmentationOperationBase):
    """自定义脚本操作"""
    operation_type: Literal["custom_script"] = "custom_script"
    name: Literal["自定义脚本"] = "自定义脚本"
    script_id: str = Field(..., description="脚本ID")


# 联合类型，用于流水线配置
AugmentationOperation = (
    HorizontalFlipOperation | VerticalFlipOperation | RandomRotateOperation |
    RandomCropOperation | ScaleOperation | AffineTransformOperation |
    BrightnessAdjustmentOperation | ContrastAdjustmentOperation |
    SaturationAdjustmentOperation | HueJitterOperation |
    HistogramEqualizationOperation | CLAHEOperation |
    GaussianNoiseOperation | SaltPepperNoiseOperation |
    GaussianBlurOperation | MotionBlurOperation |
    MosaicOperation | MixUpOperation | CutOutOperation | CutMixOperation |
    CustomScriptOperation
)


# ==================== 模板 Schema ====================

class AugmentationTemplateBase(BaseModel):
    """增强模板基础 Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: Optional[str] = Field(default=None, description="模板描述")
    pipeline_config: List[Dict[str, Any]] = Field(default_factory=list, description="流水线配置")


class AugmentationTemplateCreate(AugmentationTemplateBase):
    """创建增强模板请求 Schema"""
    pass


class AugmentationTemplateUpdate(BaseModel):
    """更新增强模板请求 Schema"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None)
    pipeline_config: Optional[List[Dict[str, Any]]] = Field(default=None)


class AugmentationTemplateResponse(AugmentationTemplateBase):
    """增强模板响应 Schema"""
    id: str = Field(description="模板ID")
    is_preset: bool = Field(default=False, description="是否为系统预设")
    created_by: str = Field(description="创建者ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 增强任务 Schema ====================

class AugmentationJobBase(BaseModel):
    """增强任务基础 Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="任务名称")
    source_dataset_id: str = Field(..., description="源数据集ID")
    pipeline_config: List[Dict[str, Any]] = Field(default_factory=list, description="流水线配置")
    augmentation_factor: int = Field(default=2, ge=1, le=10, description="增强倍数 (1-10)")


class AugmentationJobCreate(AugmentationJobBase):
    """创建增强任务请求 Schema"""
    new_dataset_name: Optional[str] = Field(default=None, description="新数据集名称（可选）")
    target_split: Optional[str] = Field(default="train", description="目标划分 (train/val/test/all)")
    include_original: bool = Field(default=True, description="是否包含原始图像")


class AugmentationJobUpdate(BaseModel):
    """更新增强任务请求 Schema"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    status: Optional[str] = Field(default=None, pattern="^(pending|running|paused|completed|failed|cancelled)$")


class AugmentationJobResponse(AugmentationJobBase):
    """增强任务响应 Schema"""
    id: str = Field(description="任务ID")
    target_dataset_id: Optional[str] = Field(default=None, description="目标数据集ID")
    status: str = Field(default="pending", description="任务状态")
    progress: float = Field(default=0.0, description="进度百分比")
    processed_count: int = Field(default=0, description="已处理数量")
    total_count: int = Field(default=0, description="总数量")
    generated_count: int = Field(default=0, description="生成数量")
    celery_task_id: Optional[str] = Field(default=None, description="Celery任务ID")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    execution_logs: List[Dict[str, Any]] = Field(default_factory=list, description="执行日志")
    timing_stats: Optional[Dict[str, Any]] = Field(default=None, description="时间统计")
    created_by: str = Field(description="创建者ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class AugmentationJobListQuery(BaseModel):
    """增强任务列表查询 Schema"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    status: Optional[str] = Field(default=None, pattern="^(pending|running|paused|completed|failed|cancelled)$")
    source_dataset_id: Optional[str] = Field(default=None, description="源数据集ID")


# ==================== 预览 Schema ====================

class AugmentationPreviewRequest(BaseModel):
    """增强预览请求 Schema"""
    source_dataset_id: str = Field(..., description="源数据集ID")
    image_id: Optional[str] = Field(default=None, description="指定图像ID（可选）")
    pipeline_config: List[Dict[str, Any]] = Field(default_factory=list, description="流水线配置")
    # 新增：上传的图片数据（base64编码）
    uploaded_image: Optional[str] = Field(default=None, description="上传的图片（base64编码，可选）")


class PreviewBBoxInfo(BaseModel):
    """预览标注框信息"""
    id: str = Field(description="标注框ID")
    x1: float = Field(description="左上角X坐标（归一化0-1）")
    y1: float = Field(description="左上角Y坐标（归一化0-1）")
    x2: float = Field(description="右下角X坐标（归一化0-1）")
    y2: float = Field(description="右下角Y坐标（归一化0-1）")
    class_id: int = Field(description="类别ID")
    class_name: Optional[str] = Field(default=None, description="类别名称")


class PreviewImageInfo(BaseModel):
    """预览图像信息"""
    url: str = Field(description="图像URL")
    width: int = Field(default=0, description="图像宽度")
    height: int = Field(default=0, description="图像高度")
    bbox_count: int = Field(default=0, description="标注框数量")
    bboxes: List[PreviewBBoxInfo] = Field(default_factory=list, description="标注框列表")


class AugmentationPreviewResponse(BaseModel):
    """增强预览响应 Schema"""
    original: PreviewImageInfo = Field(description="原图信息")
    augmented: PreviewImageInfo = Field(description="增强图信息")
    applied_operations: List[str] = Field(default_factory=list, description="应用的操作列表")
    processing_time_ms: int = Field(default=0, description="处理时间（毫秒）")


# ==================== 自定义脚本 Schema ====================

class CustomScriptUploadRequest(BaseModel):
    """上传自定义脚本请求 Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="脚本名称")
    description: Optional[str] = Field(default=None, description="脚本描述")


class CustomScriptResponse(BaseModel):
    """自定义脚本响应 Schema"""
    id: str = Field(description="脚本ID")
    name: str = Field(description="脚本名称")
    description: Optional[str] = Field(default=None, description="脚本描述")
    file_size: int = Field(description="文件大小（字节）")
    is_valid: bool = Field(description="是否通过验证")
    validation_error: Optional[str] = Field(default=None, description="验证错误信息")
    interface_type: str = Field(description="接口类型")
    created_by: str = Field(description="创建者ID")
    created_at: datetime = Field(description="创建时间")
    
    model_config = ConfigDict(from_attributes=True)


# ==================== 操作定义 Schema ====================

class AugmentationOperationDefinition(BaseModel):
    """增强操作定义（用于前端获取可用操作列表）"""
    operation_type: str = Field(description="操作类型标识")
    name: str = Field(description="操作显示名称")
    description: str = Field(description="操作描述")
    category: str = Field(description="分类: geometric/color/noise_blur/advanced/custom")
    icon: Optional[str] = Field(default=None, description="图标标识")
    parameters: List[Dict[str, Any]] = Field(default_factory=list, description="参数定义列表")
    supports_bbox: bool = Field(default=True, description="是否支持标注框")


class AvailableOperationsResponse(BaseModel):
    """可用操作列表响应 Schema"""
    operations: List[AugmentationOperationDefinition] = Field(description="操作列表")
    categories: List[Dict[str, str]] = Field(description="分类列表")


# ==================== 任务控制 Schema ====================

class JobControlRequest(BaseModel):
    """任务控制请求 Schema"""
    action: str = Field(..., pattern="^(pause|resume|cancel)$", description="控制动作")


class JobControlResponse(BaseModel):
    """任务控制响应 Schema"""
    success: bool = Field(description="是否成功")
    new_status: str = Field(description="新状态")
    message: str = Field(description="消息")


# ==================== 执行进度 Schema ====================

class JobProgressResponse(BaseModel):
    """任务进度响应 Schema"""
    job_id: str = Field(description="任务ID")
    status: str = Field(description="状态")
    progress: float = Field(description="进度百分比")
    processed_count: int = Field(description="已处理数量")
    total_count: int = Field(description="总数量")
    generated_count: int = Field(description="生成数量")
    current_operation: Optional[str] = Field(default=None, description="当前操作")
    estimated_time_remaining: Optional[int] = Field(default=None, description="预计剩余时间（秒）")
