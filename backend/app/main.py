"""
FastAPI 应用主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import logging

from app.core.config import settings
from app.core.events import lifespan
from app.api.v1 import api_router

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
def create_application() -> FastAPI:
    """
    创建 FastAPI 应用实例
    
    Returns:
        FastAPI: 配置好的 FastAPI 应用
    """
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="工业缺陷检测平台 API",
        debug=settings.debug,
        lifespan=lifespan
    )
    
    # 配置 CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册 API 路由
    application.include_router(api_router, prefix="/api")
    
    return application


# 创建应用实例
app = create_application()


@app.get("/")
async def root():
    """根路径 - API 信息"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "environment": settings.environment
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "version": settings.app_version
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
