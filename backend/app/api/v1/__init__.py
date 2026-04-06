"""
API V1 路由模块
"""
from fastapi import APIRouter

from app.api.v1 import auth, users

api_router = APIRouter(prefix="/v1")

# 注册路由
api_router.include_router(auth.router)
api_router.include_router(users.router)

# 预留的其他路由（后续实现）
# from app.api.v1 import datasets, models, training, detection, analytics
# api_router.include_router(datasets.router, prefix="/datasets")
# api_router.include_router(models.router, prefix="/models")
# api_router.include_router(training.router, prefix="/training")
# api_router.include_router(detection.router, prefix="/detection")
# api_router.include_router(analytics.router, prefix="/analytics")
