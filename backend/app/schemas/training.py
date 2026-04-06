"""
训练任务相关 Schema
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TrainingMetrics(BaseModel):
    """训练指标 Schema"""
    loss: Optional[float] = Field(default=None, description="损失")
    val_loss: Optional[float] = Field(default=None, description="验证损失")
    mAP: Optional[float] = Field(default=None, description="平均精度")
    precision: Optional[float] = Field(default=None, description="精确率")
    recall: Optional[float] = Field(default=None, description="召回率")
    epoch: Optional[int] = Field(default=None, description="当前轮次")


class TrainingJobBase(BaseModel):
    """训练任务基础 Schema"""
    model_config_id: str = Field(description="模型配置ID")
    dataset_id: str = Field(description="数据集ID")
    hyperparams: Dict[str, Any] = Field(
        default_factory=lambda: {
            "epochs": 100,
            "batch_size": 16,
            "learning_rate": 0.001,
            "device": "cuda"
        },
        description="超参数"
    )


class TrainingJobCreate(TrainingJobBase):
    """训练任务创建 Schema"""
    production_line_id: str = Field(description="所属产线ID")


class TrainingJobResponse(TrainingJobBase):
    """训练任务响应 Schema"""
    id: str = Field(description="任务ID")
    status: str = Field(description="状态")
    progress: float = Field(description="进度 0-100")
    metrics: Optional[Dict[str, Any]] = Field(default=None, description="训练指标")
    best_weights_path: Optional[str] = Field(default=None, description="最佳权重路径")
    log_path: Optional[str] = Field(default=None, description="日志路径")
    celery_task_id: Optional[str] = Field(default=None, description="Celery任务ID")
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    completed_at: Optional[datetime] = Field(default=None, description="完成时间")
    production_line_id: str = Field(description="所属产线ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    
    class Config:
        from_attributes = True


class TrainedModelResponse(BaseModel):
    """训练模型响应 Schema"""
    id: str = Field(description="模型ID")
    training_job_id: str = Field(description="训练任务ID")
    name: str = Field(description="模型名称")
    weights_path: str = Field(description="权重路径")
    architecture_config: Dict[str, Any] = Field(description="架构配置")
    metrics_summary: Dict[str, Any] = Field(description="指标摘要")
    params_count: Optional[int] = Field(default=None, description="参数量")
    flops: Optional[int] = Field(default=None, description="FLOPs")
    is_pruned: bool = Field(description="是否剪枝")
    is_distilled: bool = Field(description="是否蒸馏")
    parent_model_id: Optional[str] = Field(default=None, description="父模型ID")
    production_line_id: str = Field(description="所属产线ID")
    created_at: datetime = Field(description="创建时间")
    
    class Config:
        from_attributes = True
