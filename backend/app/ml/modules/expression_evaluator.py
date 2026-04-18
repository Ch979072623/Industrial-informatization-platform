"""
表达式求值器

支持 schema 中 ${表达式} 的求值，基于 AST 白名单实现。
严禁使用 eval/exec。

支持的运算：
- 基本算术: +, -, *, /, //, %, **
- 一元运算: +, -
- 下标访问: list[index], dict[key]
- 内置函数: int, float, abs, min, max, len, sum, round
- 变量引用: 来自传入的上下文 dict

安全策略：
- 仅允许白名单内的 AST 节点类型
- 拒绝 __import__, eval, exec, compile, getattr, setattr, open 等危险调用
- 拒绝 NameConstant/Constant 中的非数字/字符串/布尔/None 值
"""
import ast
import operator
from typing import Any, Dict, Callable, List, Optional


class ExpressionSecurityError(Exception):
    """表达式包含不安全 AST 节点"""
    pass


class ExpressionSyntaxError(Exception):
    """表达式语法错误"""
    pass


# 允许的二元操作符
_BINARY_OPS: Dict[type, Callable] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# 允许的比较操作符
_COMPARE_OPS: Dict[type, Callable] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: lambda a, b: not operator.is_(a, b),
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

# 允许的内置函数白名单
_BUILTIN_WHITELIST: Dict[str, Callable] = {
    "int": int,
    "float": float,
    "abs": abs,
    "min": min,
    "max": max,
    "len": len,
    "sum": sum,
    "round": round,
}

# 允许的一元操作符
_UNARY_OPS: Dict[type, Callable] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# 允许的所有 AST 节点类型
_ALLOWED_NODES: set = {
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Num,  # Python < 3.8 compatibility
    ast.Name,
    ast.Subscript,
    ast.Index,  # Python < 3.9 compatibility
    ast.Load,
    ast.Call,
    ast.keyword,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Compare,
    ast.BoolOp,
    ast.And,
    ast.Or,
    # 二元操作符
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    # 一元操作符
    ast.UAdd,
    ast.USub,
    # 比较操作符
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    # 成员测试
    ast.In,
    ast.NotIn,
    # 身份测试
    ast.Is,
    ast.IsNot,
    # 三元表达式
    ast.IfExp,
}

# 禁止的 name/id
_FORBIDDEN_NAMES: set = {
    "__import__", "eval", "exec", "compile", "getattr", "setattr", "delattr",
    "open", "input", "raw_input", "breakpoint", "help", "license",
    "__builtins__", "__class__", "__base__", "__subclasses__", "__mro__",
    "__globals__", "__closure__", "__code__", "__defaults__", "__dict__",
    "os", "sys", "subprocess", "shutil", "socket", "requests", "urllib",
}


def _validate_node(node: ast.AST) -> None:
    """递归验证 AST 节点是否在白名单内"""
    if type(node) not in _ALLOWED_NODES:
        raise ExpressionSecurityError(
            f"不支持的 AST 节点类型: {type(node).__name__}"
        )

    # 拒绝危险名称
    if isinstance(node, ast.Name):
        if node.id in _FORBIDDEN_NAMES:
            raise ExpressionSecurityError(
                f"禁止使用的名称: {node.id}"
            )

    # 拒绝危险函数调用
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id not in _BUILTIN_WHITELIST:
                raise ExpressionSecurityError(
                    f"禁止调用的函数: {node.func.id}"
                )
        elif isinstance(node.func, ast.Attribute):
            raise ExpressionSecurityError(
                "禁止方法调用（属性访问）"
            )

    # 递归验证子节点
    for child in ast.iter_child_nodes(node):
        _validate_node(child)


def evaluate_expression(expression: str, context: Dict[str, Any]) -> Any:
    """
    安全地求值表达式字符串

    Args:
        expression: 表达式字符串，如 "in_channels // n_splits"
        context: 变量上下文，如 {"in_channels": 64, "n_splits": 3}

    Returns:
        求值结果

    Raises:
        ExpressionSecurityError: 包含不安全 AST 节点
        ExpressionSyntaxError: 语法错误
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ExpressionSyntaxError(f"语法错误: {e}") from e

    # 安全验证
    _validate_node(tree)

    # 求值
    return _eval_node(tree.body, context)


def _eval_node(node: ast.AST, context: Dict[str, Any]) -> Any:
    """递归求值 AST 节点"""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Num):  # Python < 3.8
        return node.n

    if isinstance(node, ast.Name):
        if node.id in context:
            return context[node.id]
        if node.id in _BUILTIN_WHITELIST:
            return _BUILTIN_WHITELIST[node.id]
        raise ExpressionSecurityError(f"未定义的变量: {node.id}")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, context)
        right = _eval_node(node.right, context)
        op_type = type(node.op)
        if op_type not in _BINARY_OPS:
            raise ExpressionSecurityError(f"不支持的操作符: {op_type.__name__}")
        return _BINARY_OPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, context)
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ExpressionSecurityError(f"不支持的一元操作符: {op_type.__name__}")
        return _UNARY_OPS[op_type](operand)

    if isinstance(node, ast.Subscript):
        value = _eval_node(node.value, context)
        slice_node = node.slice
        # Python 3.9+ ast.Subscript.slice is directly the inner node
        if isinstance(slice_node, ast.Index):
            slice_node = slice_node.value
        index = _eval_node(slice_node, context)
        return value[index]

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id not in _BUILTIN_WHITELIST:
                raise ExpressionSecurityError(f"禁止调用的函数: {node.func.id}")
            func = _BUILTIN_WHITELIST[node.func.id]
            args = [_eval_node(arg, context) for arg in node.args]
            kwargs = {kw.arg: _eval_node(kw.value, context) for kw in node.keywords}
            return func(*args, **kwargs)
        raise ExpressionSecurityError("只允许白名单内的函数调用")

    if isinstance(node, ast.List):
        return [_eval_node(e, context) for e in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(e, context) for e in node.elts)

    if isinstance(node, ast.Dict):
        keys = [_eval_node(k, context) for k in node.keys]
        values = [_eval_node(v, context) for v in node.values]
        return dict(zip(keys, values))

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, context)
            op_type = type(op)
            if op_type not in _COMPARE_OPS:
                raise ExpressionSecurityError(f"不支持的比较操作符: {op_type.__name__}")
            if not _COMPARE_OPS[op_type](left, right):
                result = False
                break
            left = right
        return result

    if isinstance(node, ast.BoolOp):
        # Python 的 and/or 是短路求值，返回最后一个求值的操作数，不是 True/False
        if isinstance(node.op, ast.Or):
            for v in node.values:
                val = _eval_node(v, context)
                if val:
                    return val
            return val  # 所有值都 falsy，返回最后一个
        if isinstance(node.op, ast.And):
            for v in node.values:
                val = _eval_node(v, context)
                if not val:
                    return val
            return val  # 所有值都 truthy，返回最后一个
        raise ExpressionSecurityError("不支持的布尔操作符")

    if isinstance(node, ast.IfExp):
        test = _eval_node(node.test, context)
        if test:
            return _eval_node(node.body, context)
        else:
            return _eval_node(node.orelse, context)

    raise ExpressionSecurityError(f"未处理的 AST 节点: {type(node).__name__}")


def resolve_params(
    params_spec: Dict[str, Any],
    parent_params: Dict[str, Any],
    params_schema: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    解析参数映射

    将子节点的 params 中 ${表达式} 替换为实际值，字面量直接保留。
    如果提供了 params_schema，会先把 schema 中声明的默认值（包括 None）
    注入 context，再用 parent_params 覆盖，确保表达式能访问到所有声明参数。

    Args:
        params_spec: 子节点参数规格，如 {"kernel_size": "${kernel_sizes[0]}", "padding": 1}
        parent_params: 父节点对外参数取值，如 {"kernel_sizes": [3, 5, 7]}
        params_schema: 参数声明列表，如 [{"name": "p", "default": None}, ...]

    Returns:
        解析后的参数字典
    """
    context: Dict[str, Any] = {}
    if params_schema is not None:
        for param_spec in params_schema:
            context[param_spec["name"]] = param_spec.get("default")
    context.update(parent_params)

    resolved: Dict[str, Any] = {}
    for key, value in params_spec.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            expr = value[2:-1].strip()
            resolved[key] = evaluate_expression(expr, context)
        else:
            resolved[key] = value
    return resolved
