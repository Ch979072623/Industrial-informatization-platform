"""
通用 Schema
"""
from typing import TypeVar, Generic, Optional, List, Dict, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    
    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: List[T] = Field(description="数据列表")
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    pages: int = Field(description="总页数")
    
    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        page_size: int
    ) -> "PaginatedResponse[T]":
        """创建分页响应"""
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages
        )


class APIResponse(BaseModel, Generic[T]):
    """通用 API 响应"""
    success: bool = Field(default=True, description="是否成功")
    message: Optional[str] = Field(default=None, description="消息")
    data: Optional[T] = Field(default=None, description="数据")
    
    @classmethod
    def success_response(
        cls,
        data: Optional[T] = None,
        message: str = "操作成功"
    ) -> "APIResponse[T]":
        """创建成功响应"""
        return cls(success=True, message=message, data=data)
    
    @classmethod
    def error_response(
        cls,
        message: str = "操作失败",
        data: Optional[T] = None
    ) -> "APIResponse[T]":
        """创建失败响应"""
        return cls(success=False, message=message, data=data)


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = Field(default=False)
    error_code: str = Field(description="错误代码")
    message: str = Field(description="错误消息")
    details: Optional[Dict[str, Any]] = Field(default=None, description="错误详情")
