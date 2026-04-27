"""
数据增强模型

存储数据增强任务和模板配置
"""
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from sqlalchemy import String, Text, ForeignKey, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.dataset import Dataset
    from app.models.user import User


class AugmentationTemplate(BaseModel):
    """
    增强模板表
    
    存储用户保存的增强策略配置模板
    """
    
    # 模板名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="模板名称"
    )
    
    # 模板描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="模板描述"
    )
    
    # 增强流水线配置 (JSON)
    pipeline_config: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="增强流水线配置，存储操作列表和参数"
    )
    
    # 是否系统预设模板
    is_preset: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否为系统预设模板"
    )
    
    # 创建者
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者ID"
    )
    
    # 关系
    creator: Mapped["User"] = relationship("User", back_populates="augmentation_templates")


class AugmentationJob(BaseModel):
    """
    增强任务表
    
    存储数据增强任务的执行状态和结果
    """
    
    # 任务名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="任务名称"
    )
    
    # 源数据集ID
    source_dataset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("dataset.id", ondelete="CASCADE"),
        nullable=False,
        comment="源数据集ID"
    )
    
    # 目标数据集ID（可选，增强后创建的新数据集）
    target_dataset_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("dataset.id", ondelete="SET NULL"),
        nullable=True,
        comment="目标数据集ID"
    )
    
    # 增强配置 (JSON)
    pipeline_config: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="增强流水线配置"
    )
    
    # 增强倍数
    augmentation_factor: Mapped[int] = mapped_column(
        Integer,
        default=2,
        nullable=False,
        comment="增强倍数（每张原始图像生成多少张增强图像）"
    )
    
    # 任务状态
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="任务状态: pending/running/paused/completed/failed/cancelled"
    )
    
    # 任务进度（0-100）
    progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="任务进度百分比"
    )
    
    # 已处理的图像数量
    processed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="已处理图像数量"
    )
    
    # 总图像数量
    total_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="总图像数量"
    )
    
    # 生成的图像数量
    generated_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="生成的增强图像数量"
    )
    
    # Celery 任务ID
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Celery任务ID"
    )
    
    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息"
    )
    
    # 执行日志 (JSON)
    execution_logs: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
        comment="执行日志"
    )
    
    # 执行时间统计 (JSON)
    timing_stats: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="执行时间统计"
    )
    
    # 创建者
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者ID"
    )
    
    # 关系
    source_dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        foreign_keys=[source_dataset_id],
        back_populates="augmentation_jobs"
    )
    target_dataset: Mapped[Optional["Dataset"]] = relationship(
        "Dataset",
        foreign_keys=[target_dataset_id]
    )
    creator: Mapped["User"] = relationship("User", back_populates="augmentation_jobs")


class CustomAugmentationScript(BaseModel):
    """
    自定义增强脚本表
    
    存储用户上传的自定义 Python 增强脚本
    """
    
    # 脚本名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="脚本名称"
    )
    
    # 脚本描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="脚本描述"
    )
    
    # 脚本文件路径
    script_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="脚本文件存储路径"
    )
    
    # 脚本内容哈希（用于缓存验证）
    script_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="脚本内容SHA256哈希"
    )
    
    # 文件大小（字节）
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="文件大小（字节）"
    )
    
    # 是否通过语法验证
    is_valid: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="是否通过语法验证"
    )
    
    # 验证错误信息
    validation_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="验证错误信息"
    )
    
    # 脚本接口类型
    interface_type: Mapped[str] = mapped_column(
        String(20),
        default="standard",
        nullable=False,
        comment="脚本接口类型: standard/numpy"
    )
    
    # 创建者
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者ID"
    )
    
    # 关系
    creator: Mapped["User"] = relationship("User", back_populates="custom_scripts")


class AugmentationPreview(BaseModel):
    """
    增强预览缓存表
    
    存储增强预览结果，避免重复计算
    """
    
    # 源图像ID
    source_image_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("datasetimage.id", ondelete="CASCADE"),
        nullable=False,
        comment="源图像ID"
    )
    
    # 增强配置哈希（用于缓存键）
    config_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="配置哈希值"
    )
    
    # 预览图像路径
    preview_image_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="预览图像存储路径"
    )
    
    # 预览标注数据 (JSON)
    preview_annotations: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="预览标注数据"
    )
    
    # 过期时间
    expires_at: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
        comment="缓存过期时间（ISO格式）"
    )
    
    # 创建者
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者ID"
    )
