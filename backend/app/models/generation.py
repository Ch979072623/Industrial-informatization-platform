"""
数据生成模型

存储数据生成任务和生成器配置
"""
from typing import TYPE_CHECKING, Optional, Dict, Any, List
from sqlalchemy import String, Text, ForeignKey, Integer, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.dataset import Dataset
    from app.models.user import User


class GenerationTemplate(BaseModel):
    """
    生成模板表
    
    存储用户保存的生成策略配置模板
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
    
    # 生成器名称
    generator_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="生成器名称"
    )
    
    # 生成配置 (JSON)
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="生成配置参数"
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
    creator: Mapped["User"] = relationship("User", back_populates="generation_templates")


class GenerationJob(BaseModel):
    """
    生成任务表
    
    存储数据生成任务的执行状态和结果
    """
    
    # 任务名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="任务名称"
    )
    
    # 生成器名称
    generator_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="生成器名称"
    )
    
    # 生成配置 (JSON)
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="生成配置参数"
    )
    
    # 生成数量
    count: Mapped[int] = mapped_column(
        Integer,
        default=100,
        nullable=False,
        comment="生成数量"
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
    
    # 成功生成的图像数量
    success_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="成功生成数量"
    )
    
    # 失败的图像数量
    failed_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="失败数量"
    )
    
    # 输出数据集ID
    output_dataset_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("dataset.id", ondelete="SET NULL"),
        nullable=True,
        comment="输出数据集ID"
    )
    
    # Celery 任务ID
    celery_task_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Celery任务ID"
    )
    
    # 输出标注格式
    annotation_format: Mapped[str] = mapped_column(
        String(10),
        default="yolo",
        nullable=False,
        comment="标注格式: yolo/coco/voc"
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
    
    # 质量报告 (JSON)
    quality_report: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="质量报告数据"
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
    output_dataset: Mapped[Optional["Dataset"]] = relationship("Dataset")
    creator: Mapped["User"] = relationship("User", back_populates="generation_jobs")


class DefectLibraryCache(BaseModel):
    """
    缺陷库缓存表
    
    缓存从数据集中提取的缺陷区域，避免重复提取
    """
    
    # 源数据集ID
    source_dataset_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("dataset.id", ondelete="CASCADE"),
        nullable=False,
        comment="源数据集ID"
    )
    
    # 颜色匹配模式
    color_mode: Mapped[str] = mapped_column(
        String(20),
        default="standard",
        nullable=False,
        comment="颜色匹配模式"
    )
    
    # 缓存键
    cache_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="缓存键: dataset_id:color_mode"
    )
    
    # 缓存数据路径
    cache_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="缓存数据存储路径"
    )
    
    # 缺陷数量
    defect_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="缺陷数量"
    )
    
    # 缓存大小（MB）
    cache_size_mb: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="缓存大小（MB）"
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


class GenerationPreview(BaseModel):
    """
    生成预览缓存表
    
    存储生成预览结果，避免重复计算
    """
    
    # 生成器名称
    generator_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="生成器名称"
    )
    
    # 配置哈希（用于缓存键）
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
    
    # 原始基底图像路径（用于对比）
    base_image_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="原始基底图像路径"
    )
    
    # 预览标注数据 (JSON)
    preview_annotations: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="预览标注数据"
    )
    
    # 生成元数据 (JSON)
    generation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="生成元数据"
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
