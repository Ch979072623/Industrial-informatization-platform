"""
用户模型
"""
from typing import TYPE_CHECKING, Optional, List
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel

if TYPE_CHECKING:
    from app.models.production_line import ProductionLine
    from app.models.augmentation import AugmentationTemplate, AugmentationJob, CustomAugmentationScript
    from app.models.generation import GenerationTemplate, GenerationJob


class User(BaseModel):
    """
    用户表
    
    存储平台用户信息，支持管理员和普通用户角色
    """
    
    # 用户名（唯一）
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="用户名"
    )
    
    # 邮箱（唯一）
    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="邮箱地址"
    )
    
    # 密码哈希
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码哈希"
    )
    
    # 用户角色
    role: Mapped[str] = mapped_column(
        String(20),
        default="user",
        nullable=False,
        comment="角色: admin/user"
    )
    
    # 是否激活
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="是否激活"
    )
    
    # 所属产线（外键）
    production_line_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("productionline.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属产线ID"
    )
    
    # 关系
    production_line: Mapped[Optional["ProductionLine"]] = relationship(
        "ProductionLine",
        foreign_keys=[production_line_id],
        back_populates="users",
        remote_side="ProductionLine.id"
    )
    
    # 增强模块关系
    augmentation_templates: Mapped[List["AugmentationTemplate"]] = relationship(
        "AugmentationTemplate",
        back_populates="creator",
        cascade="all, delete-orphan"
    )
    augmentation_jobs: Mapped[List["AugmentationJob"]] = relationship(
        "AugmentationJob",
        back_populates="creator",
        cascade="all, delete-orphan"
    )
    custom_scripts: Mapped[List["CustomAugmentationScript"]] = relationship(
        "CustomAugmentationScript",
        back_populates="creator",
        cascade="all, delete-orphan"
    )
    
    # 数据生成模块关系
    generation_templates: Mapped[List["GenerationTemplate"]] = relationship(
        "GenerationTemplate",
        back_populates="creator",
        cascade="all, delete-orphan"
    )
    generation_jobs: Mapped[List["GenerationJob"]] = relationship(
        "GenerationJob",
        back_populates="creator",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
