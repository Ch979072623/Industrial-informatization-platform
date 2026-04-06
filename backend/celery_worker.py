"""
Celery Worker 入口
"""
from celery import Celery
from app.core.config import settings

# 创建 Celery 应用实例
celery_app = Celery(
    "defect_detection",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.training_task",
        "app.tasks.augmentation_task",
        "app.tasks.generation_task",
        "app.tasks.testing_task",
        "app.tasks.pruning_task",
        "app.tasks.distillation_task",
        "app.tasks.dataset_task",
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    # 接受的内容类型
    accept_content=["json"],
    # 结果序列化
    result_serializer="json",
    # 时区设置
    timezone="Asia/Shanghai",
    # 启用 UTC
    enable_utc=True,
    # 任务结果过期时间（秒）
    result_expires=3600,
    # 任务跟踪
    task_track_started=True,
    # 任务发送事件
    task_send_sent_event=True,
    # Worker 发送事件
    worker_send_task_events=True,
)


if __name__ == "__main__":
    celery_app.start()
