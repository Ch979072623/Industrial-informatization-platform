"""
模块定义模型

存储神经网络可视化构建器的模块定义，包括：
1. 原子模块（对应 PyTorch 原生层）
2. 复合模块（由子节点通过内部子图组合而成）
3. 用户自定义复合模块
"""
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, ForeignKey, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import BaseModel


class ModuleDefinition(BaseModel):
    """
    模块定义表

    以 type 为业务主键（唯一标识一种模块，如 "Conv2d" / "PMSFA"）。
    schema_json 存储完整元数据：原子模块只有 params_schema + ports；
    复合模块额外包含 proxy_inputs/outputs、sub_nodes、sub_edges。
    """

    # 模块类型标识符（如 Conv2d, PMSFA），业务主键
    type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        comment="模块类型标识符"
    )

    # 模块分类
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="模块分类: atomic/backbone/neck/head/attention/custom"
    )

    # 是否为复合模块
    is_composite: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="是否为复合模块"
    )

    # 显示名称（中文）
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="显示名称"
    )

    # 完整 schema（核心数据契约）
    schema_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="完整模块 schema"
    )

    # 来源
    source: Mapped[str] = mapped_column(
        String(20),
        default="builtin",
        nullable=False,
        comment="来源: builtin/custom"
    )

    # 版本号（用于检测 schema 变化）
    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="版本号"
    )

    # 创建者（自定义模块时有值）
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建者ID"
    )

    # 所属产线
    production_line_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("productionline.id", ondelete="SET NULL"),
        nullable=True,
        comment="所属产线ID"
    )

    def __repr__(self) -> str:
        return f"<ModuleDefinition(type={self.type}, category={self.category}, is_composite={self.is_composite})>"

    def to_dict(self) -> Dict[str, Any]:
        """将模型转换为字典"""
        return {
            "id": self.id,
            "type": self.type,
            "category": self.category,
            "is_composite": self.is_composite,
            "display_name": self.display_name,
            "schema_json": self.schema_json,
            "source": self.source,
            "version": self.version,
            "created_by": self.created_by,
            "production_line_id": self.production_line_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
