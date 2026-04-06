"""
检测记录相关 Schema
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DefectInfo(BaseModel):
    """缺陷信息 Schema"""
    class_id: int = Field(description="类别ID")
    class_name: str = Field(description="类别名称")
    confidence: float = Field(description="置信度")
    bbox: List[float] = Field(description="边界框 [x, y, width, height]")


class DetectionRecordCreate(BaseModel):
    """检测记录创建 Schema"""
    image_path: str = Field(description="图像路径")
    model_id: str = Field(description="模型ID")
    confidence_threshold: float = Field(default=0.5, ge=0, le=1, description="置信度阈值")
    production_line_id: str = Field(description="所属产线ID")


class DetectionRecordResponse(BaseModel):
    """检测记录响应 Schema"""
    id: str = Field(description="记录ID")
    image_path: str = Field(description="原始图像路径")
    result_image_path: Optional[str] = Field(default=None, description="结果图像路径")
    model_id: str = Field(description="模型ID")
    defects: List[DefectInfo] = Field(default_factory=list, description="缺陷列表")
    verdict: str = Field(description="检测结果 PASS/NG")
    confidence_threshold: float = Field(description="置信度阈值")
    latency_ms: float = Field(description="推理延迟(ms)")
    production_line_id: str = Field(description="所属产线ID")
    created_by: str = Field(description="创建者ID")
    created_at: datetime = Field(description="创建时间")
    
    class Config:
        from_attributes = True


class DefectStatsResponse(BaseModel):
    """缺陷统计响应 Schema"""
    id: str = Field(description="统计ID")
    date: str = Field(description="统计日期")
    total_count: int = Field(description="总检测数")
    pass_count: int = Field(description="合格数")
    ng_count: int = Field(description="不合格数")
    avg_latency: float = Field(description="平均延迟(ms)")
    defect_distribution: Dict[str, int] = Field(description="缺陷分布")
    production_line_id: str = Field(description="所属产线ID")
    created_at: datetime = Field(description="创建时间")
    
    class Config:
        from_attributes = True


class DetectionStatsQuery(BaseModel):
    """检测统计查询 Schema"""
    start_date: Optional[str] = Field(default=None, description="开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(default=None, description="结束日期 (YYYY-MM-DD)")
    production_line_id: Optional[str] = Field(default=None, description="产线ID")
