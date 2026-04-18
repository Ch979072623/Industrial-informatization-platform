"""
机器学习模块定义

提供分层复合模块的数据结构、表达式求值和注册表功能。
"""
from app.ml.modules.base import (
    ParamSchemaItem,
    ProxyPort,
    SubNode,
    SubEdge,
    CompositeModuleSpec,
)
from app.ml.modules.expression_evaluator import (
    evaluate_expression,
    resolve_params,
    ExpressionSecurityError,
    ExpressionSyntaxError,
)
__all__ = [
    "ParamSchemaItem",
    "ProxyPort",
    "SubNode",
    "SubEdge",
    "CompositeModuleSpec",
    "evaluate_expression",
    "resolve_params",
    "ExpressionSecurityError",
    "ExpressionSyntaxError",
]
