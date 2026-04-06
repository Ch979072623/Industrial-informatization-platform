"""
SQLAlchemy 基础模块
定义所有模型的基类和公共字段
"""
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr


class Base(DeclarativeBase):
    """
    SQLAlchemy 声明式基类
    
    所有模型类都应继承此类
    """
    
    # 自动生成表名（小写类名）
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
    
    # 禁用默认的继承映射
    type_annotation_map = {
        datetime: DateTime(timezone=True)
    }


class BaseModel(Base):
    """
    基础模型类
    
    包含所有表共有的字段：
    - id: UUID 主键
    - created_at: 创建时间
    - updated_at: 更新时间
    """
    
    __abstract__ = True  # 抽象基类，不创建实际表
    
    # UUID 主键
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        index=True
    )
    
    # 创建时间（UTC）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # 更新时间（UTC）
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    def to_dict(self) -> dict[str, Any]:
        """
        将模型转换为字典
        
        Returns:
            包含模型数据的字典
        """
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def __repr__(self) -> str:
        """模型的字符串表示"""
        return f"<{self.__class__.__name__}(id={self.id})>"

