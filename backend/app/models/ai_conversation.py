"""
AI对话模型
"""
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import BaseModel


class AIConversation(BaseModel):
    """
    AI对话表
    
    存储用户与AI助手的对话记录
    """
    
    # 会话ID（用于关联同一对话）
    session_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        comment="会话ID"
    )
    
    # 角色 (user/assistant)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="角色: user/assistant"
    )
    
    # 对话内容
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="对话内容"
    )
    
    # 工具调用 (JSON)
    tool_calls: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        comment="工具调用信息"
    )
    
    # 所属产线
    production_line_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("productionline.id", ondelete="CASCADE"),
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
    
    def __repr__(self) -> str:
        return f"<AIConversation(id={self.id}, session_id={self.session_id}, role={self.role})>"
