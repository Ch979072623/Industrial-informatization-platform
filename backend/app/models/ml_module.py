"""
机器学习模块模型

存储神经网络可视化构建器的模块定义，包括内置模块和用户自定义模块
"""
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Text, ForeignKey, Boolean, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import BaseModel


class ModelBuilderConfig(BaseModel):
    """
    模型构建器配置表
    
    存储可视化构建器生成的模型架构配置
    """
    
    # 配置名称
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="配置名称"
    )
    
    # 配置描述
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="配置描述"
    )
    
    # 架构配置（React Flow 的 nodes 和 edges）
    architecture_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="模型架构 JSON 配置 {nodes, edges, metadata}"
    )
    
    # 生成的代码快照
    code_snapshot: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="生成的 PyTorch 代码快照"
    )
    
    # 输入形状配置
    input_shape: Mapped[Optional[List[int]]] = mapped_column(
        JSON,
        nullable=True,
        comment="输入形状 [C, H, W]"
    )
    
    # 类别数量
    num_classes: Mapped[Optional[int]] = mapped_column(
        default=None,
        nullable=True,
        comment="类别数量"
    )
    
    # 基础模型（如果有）
    base_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="基础模型名称"
    )
    
    # 所属产线
    production_line_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("productionline.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属产线ID"
    )
    
    # 创建者
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        comment="创建者ID"
    )
    
    # 是否公开（其他用户可见）
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否公开"
    )
    
    # 版本号
    version: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
        comment="版本号"
    )
    
    # 关联的训练任务
    training_jobs: Mapped[List["TrainingJob"]] = relationship(
        "TrainingJob", back_populates="model_builder_config", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<ModelBuilderConfig(id={self.id}, name={self.name}, version={self.version})>"
