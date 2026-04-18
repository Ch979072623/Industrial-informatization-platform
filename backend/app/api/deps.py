"""
API 依赖注入模块
提供 FastAPI 依赖函数
"""
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.core.security import (
    security_bearer,
    verify_token,
    TokenData,
    require_roles
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话依赖
    
    Yields:
        AsyncSession: 异步数据库会话
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer)
) -> TokenData:
    """
    获取当前认证用户
    
    Args:
        credentials: HTTP Bearer 凭据
        
    Returns:
        TokenData: 令牌数据
        
    Raises:
        HTTPException: 认证失败时抛出
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = verify_token(credentials.credentials)
    
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data


# 角色权限依赖
def require_admin():
    """要求管理员权限"""
    return Depends(require_roles(["admin"]))


def require_user():
    """要求用户权限（普通用户或管理员）"""
    return Depends(require_roles(["user", "admin"]))


def require_production_line_access():
    """
    产线访问权限检查
    
    检查用户是否有权限访问指定产线的数据
    """
    async def checker(
        current_user: TokenData = Depends(get_current_user)
    ) -> TokenData:
        # 管理员可以访问所有产线
        if current_user.role == "admin":
            return current_user
        
        # 普通用户只能访问所属产线
        # 具体产线ID检查在路由中处理
        return current_user
    
    return Depends(checker)
