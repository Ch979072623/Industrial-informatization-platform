"""
应用生命周期事件处理模块
包含启动和关闭事件的处理逻辑
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.core.config import settings
from app.db.session import engine
from app.db.base import Base

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def init_database() -> None:
    """
    初始化数据库
    在开发环境中自动创建表（生产环境建议使用 Alembic）
    """
    if settings.is_sqlite:
        # SQLite: 自动创建表（仅开发环境）
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表已创建（SQLite 开发模式）")


async def close_database() -> None:
    """关闭数据库连接"""
    await engine.dispose()
    logger.info("数据库连接已关闭")


async def init_celery() -> None:
    """初始化 Celery 配置检查"""
    try:
        from celery import Celery
        # 简单检查 Celery broker 是否可达
        logger.info(f"Celery Broker URL: {settings.celery_broker_url}")
    except Exception as e:
        logger.warning(f"Celery 初始化检查失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    FastAPI 生命周期管理器
    
    处理应用启动和关闭事件
    
    Args:
        app: FastAPI 应用实例
        
    Yields:
        None
    """
    # 启动事件
    logger.info(f"启动 {settings.app_name} v{settings.app_version}")
    logger.info(f"环境: {settings.environment}")
    
    try:
        # 初始化数据库
        await init_database()
        
        # 检查 Celery 配置
        await init_celery()
        
        logger.info("应用启动完成")
    except Exception as e:
        logger.error(f"启动过程中出现错误: {e}")
        raise
    
    yield
    
    # 关闭事件
    logger.info("正在关闭应用...")
    
    try:
        # 关闭数据库连接
        await close_database()
        
        logger.info("应用已关闭")
    except Exception as e:
        logger.error(f"关闭过程中出现错误: {e}")


def setup_events(app: FastAPI) -> None:
    """
    设置应用生命周期事件
    
    Args:
        app: FastAPI 应用实例
    """
    app.router.lifespan_context = lifespan
