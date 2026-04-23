"""
机器学习模块相关 Schema
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ==================== 端口定义 Schema ====================

class PortDefinition(BaseModel):
    """端口定义 Schema"""
    name: str = Field(..., description="端口名称")
    type: str = Field(default="tensor", description="端口数据类型")
    shape: Optional[str] = Field(default="auto", description="张量形状")
    description: Optional[str] = Field(default=None, description="端口描述")


# ==================== 模块分类 Schema ====================

class ModuleCategory(BaseModel):
    """模块分类 Schema"""
    key: str = Field(..., description="分类键")
    label: str = Field(..., description="分类显示名称")
    icon: str = Field(..., description="分类图标")
    description: Optional[str] = Field(default=None, description="分类描述")


# ==================== MLModule Schema ====================

class MLModuleBase(BaseModel):
    """MLModule 基础 Schema"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(..., min_length=1, max_length=100, description="模块名称")
    display_name: str = Field(..., min_length=1, max_length=200, description="显示名称")
    category: Literal["basic", "backbone", "neck", "head", "custom"] = Field(
        ..., description="模块分类"
    )
    type: Literal["layer", "block", "network"] = Field(
        ..., description="模块类型"
    )
    description: Optional[str] = Field(default=None, description="模块描述")
    parameters_schema: Dict[str, Any] = Field(
        default_factory=dict, description="参数配置 JSON Schema"
    )
    default_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="默认参数值"
    )
    code_template: Optional[str] = Field(default=None, description="PyTorch 代码模板")
    input_ports: List[PortDefinition] = Field(
        default_factory=list, description="输入端口定义"
    )
    output_ports: List[PortDefinition] = Field(
        default_factory=list, description="输出端口定义"
    )
    icon: Optional[str] = Field(default="box", description="图标名称")
    sort_order: int = Field(default=0, description="排序权重")
    is_active: bool = Field(default=True, description="是否启用")


class MLModuleCreate(MLModuleBase):
    """创建 MLModule 请求 Schema"""
    pass


class MLModuleUpdate(BaseModel):
    """更新 MLModule 请求 Schema"""
    model_config = ConfigDict(from_attributes=True)
    
    display_name: Optional[str] = Field(default=None, max_length=200, description="显示名称")
    description: Optional[str] = Field(default=None, description="模块描述")
    parameters_schema: Optional[Dict[str, Any]] = Field(default=None, description="参数配置 JSON Schema")
    default_parameters: Optional[Dict[str, Any]] = Field(default=None, description="默认参数值")
    code_template: Optional[str] = Field(default=None, description="PyTorch 代码模板")
    input_ports: Optional[List[PortDefinition]] = Field(default=None, description="输入端口定义")
    output_ports: Optional[List[PortDefinition]] = Field(default=None, description="输出端口定义")
    icon: Optional[str] = Field(default=None, description="图标名称")
    sort_order: Optional[int] = Field(default=None, description="排序权重")
    is_active: Optional[bool] = Field(default=None, description="是否启用")


class MLModuleResponse(MLModuleBase):
    """MLModule 响应 Schema"""
    id: str = Field(..., description="模块ID")
    is_builtin: bool = Field(..., description="是否内置模块")
    is_custom: bool = Field(..., description="是否用户自定义模块")
    created_by: Optional[str] = Field(default=None, description="创建者ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class MLModuleListItem(BaseModel):
    """MLModule 列表项 Schema（简化版）"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="模块ID")
    name: str = Field(..., description="模块名称")
    display_name: str = Field(..., description="显示名称")
    category: str = Field(..., description="模块分类")
    type: str = Field(..., description="模块类型")
    description: Optional[str] = Field(default=None, description="模块描述")
    icon: Optional[str] = Field(default=None, description="图标名称")
    is_builtin: bool = Field(..., description="是否内置模块")
    is_custom: bool = Field(..., description="是否用户自定义模块")


class MLModuleCategoryResponse(BaseModel):
    """按分类组织的模块列表响应"""
    categories: Dict[str, List[MLModuleListItem]] = Field(
        ..., description="按分类组织的模块列表"
    )
    total: int = Field(..., description="总模块数")


class MLModuleQuery(BaseModel):
    """模块查询参数 Schema"""
    category: Optional[str] = Field(default=None, description="按分类筛选")
    search: Optional[str] = Field(default=None, description="搜索关键词")
    include_inactive: bool = Field(default=False, description="是否包含未启用模块")


# ==================== 自定义模块创建 Schema ====================

class CustomModuleCreate(BaseModel):
    """创建自定义模块请求 Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="模块名称")
    display_name: str = Field(..., min_length=1, max_length=200, description="显示名称")
    category: Literal["custom"] = Field(default="custom", description="模块分类")
    description: Optional[str] = Field(default=None, description="模块描述")
    parameters_schema: Dict[str, Any] = Field(
        default_factory=dict, description="参数配置 JSON Schema"
    )
    default_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="默认参数值"
    )
    code_template: str = Field(..., min_length=1, description="PyTorch 代码模板")
    input_ports: List[PortDefinition] = Field(
        default_factory=lambda: [PortDefinition(name="input", type="tensor")],
        description="输入端口定义"
    )
    output_ports: List[PortDefinition] = Field(
        default_factory=lambda: [PortDefinition(name="output", type="tensor")],
        description="输出端口定义"
    )
    icon: Optional[str] = Field(default="puzzle", description="图标名称")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证模块名称（必须是有效的 Python 标识符）"""
        if not v.isidentifier():
            raise ValueError('模块名称必须是有效的 Python 标识符（字母、数字、下划线，且不能以数字开头）')
        if v[0].isdigit():
            raise ValueError('模块名称不能以数字开头')
        return v


# ==================== ModuleDefinition 创建 Schema ====================

class ModuleDefinitionCreate(BaseModel):
    """用户从 Module 画布提交的新模块定义"""
    
    # 基本标识
    type: str = Field(..., min_length=1, max_length=64, description="模块 type（Python class 名），如 PMSFA")
    display_name: str = Field(..., min_length=1, max_length=128, description="中文显示名，如 并行多尺度特征聚合")
    category: str = Field(..., description="模块分类：atomic/backbone/neck/head/attention/custom")
    description: Optional[str] = Field(default=None, max_length=500)
    
    # 画布数据
    nodes: List[ModelNode]
    edges: List[ModelEdge]
    
    # 可选的参数 schema（若用户在画布上声明了对外参数）
    params_schema: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证模块 type（需以大写字母开头的 Python 标识符）"""
        if not v.isidentifier():
            raise ValueError('模块 type 必须是有效的 Python 标识符')
        if not v[0].isupper():
            raise ValueError('模块 type 需以大写字母开头')
        return v


# ==================== ModelBuilderConfig Schema ====================

class ModelNode(BaseModel):
    """模型节点 Schema"""
    id: str = Field(..., description="节点ID")
    type: str = Field(default="module", description="节点类型")
    position: Dict[str, float] = Field(..., description="节点位置 {x, y}")
    data: Dict[str, Any] = Field(..., description="节点数据")
    
    @field_validator('position')
    @classmethod
    def validate_position(cls, v: Dict[str, float]) -> Dict[str, float]:
        if 'x' not in v or 'y' not in v:
            raise ValueError('position 必须包含 x 和 y 坐标')
        return v


class ModelEdge(BaseModel):
    """模型边（连线）Schema"""
    id: str = Field(..., description="边ID")
    source: str = Field(..., description="源节点ID")
    sourceHandle: Optional[str] = Field(default=None, description="源端口ID")
    target: str = Field(..., description="目标节点ID")
    targetHandle: Optional[str] = Field(default=None, description="目标端口ID")
    type: Optional[str] = Field(default="default", description="边类型")


class ModelMetadata(BaseModel):
    """模型元数据 Schema"""
    input_shape: Optional[List[int]] = Field(
        default=None, description="输入形状 [C, H, W]"
    )
    num_classes: Optional[int] = Field(default=None, description="类别数量")
    description: Optional[str] = Field(default=None, description="模型描述")


class ModelArchitecture(BaseModel):
    """模型架构 Schema"""
    nodes: List[ModelNode] = Field(default_factory=list, description="节点列表")
    edges: List[ModelEdge] = Field(default_factory=list, description="边列表")
    metadata: ModelMetadata = Field(
        default_factory=ModelMetadata, description="模型元数据"
    )
    viewport: Optional[Dict[str, Any]] = Field(
        default=None, description="画布视口信息 {x, y, zoom}"
    )


class ModelBuilderConfigBase(BaseModel):
    """模型构建器配置基础 Schema"""
    model_config = ConfigDict(from_attributes=True)
    
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    description: Optional[str] = Field(default=None, description="配置描述")
    architecture_json: ModelArchitecture = Field(..., description="模型架构配置")
    input_shape: Optional[List[int]] = Field(default=None, description="输入形状 [C, H, W]")
    num_classes: Optional[int] = Field(default=None, ge=1, description="类别数量")
    base_model: Optional[str] = Field(default=None, description="基础模型名称")
    is_public: bool = Field(default=False, description="是否公开")


class ModelBuilderConfigCreate(ModelBuilderConfigBase):
    """创建模型配置请求 Schema"""
    pass


class ModelBuilderConfigUpdate(BaseModel):
    """更新模型配置请求 Schema"""
    model_config = ConfigDict(from_attributes=True)
    
    name: Optional[str] = Field(default=None, max_length=100, description="配置名称")
    description: Optional[str] = Field(default=None, description="配置描述")
    architecture_json: Optional[ModelArchitecture] = Field(default=None, description="模型架构配置")
    input_shape: Optional[List[int]] = Field(default=None, description="输入形状 [C, H, W]")
    num_classes: Optional[int] = Field(default=None, ge=1, description="类别数量")
    base_model: Optional[str] = Field(default=None, description="基础模型名称")
    is_public: Optional[bool] = Field(default=None, description="是否公开")
    code_snapshot: Optional[str] = Field(default=None, description="生成的代码快照")


class ModelBuilderConfigResponse(ModelBuilderConfigBase):
    """模型配置响应 Schema"""
    id: str = Field(..., description="配置ID")
    code_snapshot: Optional[str] = Field(default=None, description="生成的代码快照")
    production_line_id: Optional[str] = Field(default=None, description="所属产线ID")
    created_by: str = Field(..., description="创建者ID")
    version: int = Field(..., description="版本号")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class ModelBuilderConfigListItem(BaseModel):
    """模型配置列表项 Schema（简化版）"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str = Field(..., description="配置ID")
    name: str = Field(..., description="配置名称")
    description: Optional[str] = Field(default=None, description="配置描述")
    base_model: Optional[str] = Field(default=None, description="基础模型名称")
    num_classes: Optional[int] = Field(default=None, description="类别数量")
    is_public: bool = Field(..., description="是否公开")
    version: int = Field(..., description="版本号")
    created_at: datetime = Field(..., description="创建时间")


class ModelBuilderConfigQuery(BaseModel):
    """模型配置查询参数 Schema"""
    search: Optional[str] = Field(default=None, description="搜索关键词")
    include_public: bool = Field(default=True, description="是否包含公开配置")


# ==================== 验证响应 Schema ====================

class ConnectionValidationResult(BaseModel):
    """连线验证结果 Schema"""
    valid: bool = Field(..., description="是否有效")
    reason: Optional[str] = Field(default=None, description="无效原因（如果无效）")


class ModelValidationRequest(BaseModel):
    """模型验证请求 Schema"""
    nodes: List[ModelNode] = Field(..., description="节点列表")
    edges: List[ModelEdge] = Field(..., description="边列表")


class ModelValidationResponse(BaseModel):
    """模型验证响应 Schema"""
    valid: bool = Field(..., description="是否有效")
    errors: List[str] = Field(default_factory=list, description="错误信息列表")
    warnings: List[str] = Field(default_factory=list, description="警告信息列表")
