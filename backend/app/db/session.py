"""
数据库会话管理模块
提供异步数据库引擎和会话工厂
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
    AsyncEngine
)

from app.core.config import settings

# 创建异步数据库引擎
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,  # 调试模式下输出 SQL
    future=True,
    pool_pre_ping=True,  # 连接前 ping，自动处理断开的连接
    pool_recycle=3600,   # 连接回收时间（秒）
)

# 创建异步会话工厂
# expire_on_commit=False 保持对象在 commit 后仍可访问
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖函数
    
    用于 FastAPI 依赖注入，确保会话正确关闭
    
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


async def get_db_session() -> AsyncSession:
    """
    直接获取数据库会话（非生成器方式）
    
    用于需要直接控制会话的场景（如 Celery 任务）
    
    Returns:
        AsyncSession: 异步数据库会话
    """
    return AsyncSessionLocal()


class DatabaseSessionManager:
    """
    数据库会话管理器
    
    提供上下文管理器方式使用数据库会话
    """
    
    def __init__(self):
        self.session: AsyncSession | None = None
    
    async def __aenter__(self) -> AsyncSession:
        self.session = AsyncSessionLocal()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type:
                await self.session.rollback()
            else:
                await self.session.commit()
            await self.session.close()
        return False
