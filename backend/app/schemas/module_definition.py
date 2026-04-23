"""
ModuleDefinition 相关 Schema

为 GET /api/v1/models/modules 提供类型安全的响应结构。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModuleDefinitionListItem(BaseModel):
    """模块列表项（轻量版，不含 sub_nodes/sub_edges）"""

    id: str = Field(..., description="模块ID")
    type: str = Field(..., description="模块类型标识符")
    display_name: str = Field(..., description="显示名称（中文）")
    category: str = Field(..., description="分类: atomic/backbone/neck/head/attention/custom")
    is_composite: bool = Field(..., description="是否为复合模块")
    source: str = Field(default="builtin", description="来源: builtin/custom")
    version: int = Field(default=1, description="版本号")
    params_schema: List[Dict[str, Any]] = Field(default_factory=list, description="参数声明列表")
    proxy_inputs: List[Dict[str, Any]] = Field(default_factory=list, description="代理输入端口")
    proxy_outputs: List[Dict[str, Any]] = Field(default_factory=list, description="代理输出端口")
    input_ports_dynamic: Optional[bool] = Field(default=None, description="输入端口数是否动态")


class ModuleDefinitionDetail(BaseModel):
    """模块详情（完整 schema_json，含内部子图；同时扁平化常用字段到顶层）"""

    id: str = Field(..., description="模块ID")
    type: str = Field(..., description="模块类型标识符")
    display_name: str = Field(..., description="显示名称（中文）")
    category: str = Field(..., description="分类")
    is_composite: bool = Field(..., description="是否为复合模块")
    source: str = Field(default="builtin", description="来源")
    version: int = Field(default=1, description="版本号")
    params_schema: List[Dict[str, Any]] = Field(default_factory=list, description="参数声明列表")
    proxy_inputs: List[Dict[str, Any]] = Field(default_factory=list, description="代理输入端口")
    proxy_outputs: List[Dict[str, Any]] = Field(default_factory=list, description="代理输出端口")
    input_ports_dynamic: Optional[bool] = Field(default=None, description="输入端口数是否动态")
    schema_json: Dict[str, Any] = Field(..., description="完整模块 schema")
    created_at: Optional[str] = Field(default=None, description="创建时间 ISO 字符串")
    updated_at: Optional[str] = Field(default=None, description="更新时间 ISO 字符串")


class ModuleDefinitionResponse(ModuleDefinitionDetail):
    """创建/更新模块后的响应（与 ModuleDefinitionDetail 同构）"""
    pass
