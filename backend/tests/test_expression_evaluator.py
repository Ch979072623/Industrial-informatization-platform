"""
表达式求值器单元测试

覆盖：
- 基本算术运算
- 下标访问
- 内置函数调用
- 变量上下文
- 安全拒绝（恶意输入必须被拒）
"""
import pytest
import math

from app.ml.modules.expression_evaluator import (
    evaluate_expression,
    resolve_params,
    ExpressionSecurityError,
    ExpressionSyntaxError,
)


class TestBasicArithmetic:
    """基本算术运算测试"""

    def test_addition(self):
        assert evaluate_expression("2 + 3", {}) == 5

    def test_subtraction(self):
        assert evaluate_expression("10 - 4", {}) == 6

    def test_multiplication(self):
        assert evaluate_expression("3 * 7", {}) == 21

    def test_division(self):
        assert evaluate_expression("10 / 4", {}) == 2.5

    def test_floor_division(self):
        assert evaluate_expression("10 // 4", {}) == 2

    def test_modulo(self):
        assert evaluate_expression("10 % 3", {}) == 1

    def test_power(self):
        assert evaluate_expression("2 ** 3", {}) == 8

    def test_unary_minus(self):
        assert evaluate_expression("-5", {}) == -5

    def test_unary_plus(self):
        assert evaluate_expression("+5", {}) == 5

    def test_complex_expression(self):
        ctx = {"in_channels": 64, "n_splits": 3}
        result = evaluate_expression("in_channels // n_splits", ctx)
        assert result == 21


class TestSubscriptAccess:
    """下标访问测试"""

    def test_list_index(self):
        ctx = {"kernel_sizes": [3, 5, 7]}
        assert evaluate_expression("kernel_sizes[0]", ctx) == 3
        assert evaluate_expression("kernel_sizes[1]", ctx) == 5
        assert evaluate_expression("kernel_sizes[2]", ctx) == 7

    def test_nested_list_index(self):
        ctx = {"items": [[1, 2], [3, 4]]}
        assert evaluate_expression("items[0][1]", ctx) == 2

    def test_dict_access(self):
        ctx = {"config": {"a": 10, "b": 20}}
        assert evaluate_expression("config['a']", ctx) == 10


class TestBuiltinFunctions:
    """内置函数测试"""

    def test_int(self):
        assert evaluate_expression("int(3.7)", {}) == 3

    def test_float(self):
        assert evaluate_expression("float(5)", {}) == 5.0

    def test_abs(self):
        assert evaluate_expression("abs(-10)", {}) == 10

    def test_min_max(self):
        assert evaluate_expression("min(1, 2, 3)", {}) == 1
        assert evaluate_expression("max(1, 2, 3)", {}) == 3

    def test_len(self):
        assert evaluate_expression("len([1, 2, 3])", {}) == 3

    def test_sum(self):
        assert evaluate_expression("sum([1, 2, 3])", {}) == 6

    def test_round(self):
        assert evaluate_expression("round(3.7)", {}) == 4


class TestResolveParams:
    """参数解析测试"""

    def test_literal_value(self):
        spec = {"dim": 1}
        parent = {}
        assert resolve_params(spec, parent) == {"dim": 1}

    def test_expression_binding(self):
        spec = {"kernel_size": "${kernel_sizes[0]}", "padding": "${kernel_sizes[0] // 2}"}
        parent = {"kernel_sizes": [3, 5, 7]}
        result = resolve_params(spec, parent)
        assert result == {"kernel_size": 3, "padding": 1}

    def test_mixed_literal_and_expression(self):
        spec = {"in_channels": "${in_channels}", "out_channels": 64, "kernel_size": 1}
        parent = {"in_channels": 128}
        result = resolve_params(spec, parent)
        assert result == {"in_channels": 128, "out_channels": 64, "kernel_size": 1}

    def test_schema_default_none_injected(self):
        """params_schema 中默认值为 None 的参数必须注入 context"""
        spec = {"padding": "${p if p is not None else k // 2}"}
        parent = {"k": 5, "s": 1}  # 没传 p
        schema = [
            {"name": "c1", "type": "int", "default": 64},
            {"name": "c2", "type": "int", "default": 128},
            {"name": "k", "type": "int", "default": 3},
            {"name": "s", "type": "int", "default": 1},
            {"name": "p", "type": "int", "default": None},
        ]
        result = resolve_params(spec, parent, schema)
        assert result == {"padding": 2}  # k // 2 = 5 // 2 = 2

    def test_schema_default_zero_overrides_none(self):
        """p=0 应覆盖默认值 None，is not None 为 True"""
        spec = {"padding": "${p if p is not None else k // 2}"}
        parent = {"k": 5, "p": 0}
        schema = [
            {"name": "k", "type": "int", "default": 3},
            {"name": "p", "type": "int", "default": None},
        ]
        result = resolve_params(spec, parent, schema)
        assert result == {"padding": 0}

    def test_schema_default_explicit_overrides(self):
        """显式传入值覆盖 schema 默认值"""
        spec = {"stride": "${s if s is not None else 1}"}
        parent = {"s": 2}
        schema = [
            {"name": "s", "type": "int", "default": None},
        ]
        result = resolve_params(spec, parent, schema)
        assert result == {"stride": 2}


class TestSecurity:
    """安全性测试——恶意输入必须被拒"""

    def test_reject_import(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("__import__('os').system('ls')", {})

    def test_reject_eval(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("eval('1+1')", {})

    def test_reject_exec(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("exec('print(1)')", {})

    def test_reject_compile(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("compile('1', '', 'eval')", {})

    def test_reject_getattr(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("getattr(__builtins__, 'eval')", {})

    def test_reject_open(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("open('/etc/passwd')", {})

    def test_reject_attribute_access(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("os.system('ls')", {})

    def test_reject_breakpoint(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("breakpoint()", {})

    def test_reject_forbidden_name_in_context(self):
        # 即使上下文中有 __import__，名称本身被禁止
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("__import__", {"__import__": 1})

    def test_reject_lambda(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("(lambda: 1)()", {})

    def test_reject_class_def(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("object.__subclasses__()", {})

    def test_reject_list_comprehension(self):
        # ListComp 不在白名单中
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("[x for x in [1,2,3]]", {})

    def test_reject_call_unknown_function(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("print('hello')", {})

    def test_reject_undefined_variable(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("unknown_var + 1", {})

    def test_syntax_error(self):
        with pytest.raises(ExpressionSyntaxError):
            evaluate_expression("1 + * 2", {})

    def test_f_string_rejected(self):
        # Python 3.12+ f-string AST 可能不同，直接拒绝包含 f-string 的表达式
        # 实际上 ast.parse 会把 f-string 解析为 JoinedStr，不在白名单中
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("f'{x}'", {"x": 1})


class TestTernaryExpression:
    """三元表达式测试"""

    def test_ternary_positive(self):
        assert evaluate_expression("10 if True else 20", {}) == 10

    def test_ternary_negative(self):
        assert evaluate_expression("10 if False else 20", {}) == 20

    def test_ternary_with_condition(self):
        ctx = {"x": 5}
        assert evaluate_expression("100 if x > 0 else 200", ctx) == 100
        ctx = {"x": -3}
        assert evaluate_expression("100 if x > 0 else 200", ctx) == 200

    def test_ternary_nested(self):
        ctx = {"x": -1, "y": 2}
        assert evaluate_expression("'a' if x > 0 else ('b' if y > 0 else 'c')", ctx) == 'b'
        ctx = {"x": -1, "y": -2}
        assert evaluate_expression("'a' if x > 0 else ('b' if y > 0 else 'c')", ctx) == 'c'

    def test_ternary_none_check(self):
        ctx = {"p": None, "k": 5}
        assert evaluate_expression("p if p is not None else k // 2", ctx) == 2
        ctx = {"p": 3, "k": 5}
        assert evaluate_expression("p if p is not None else k // 2", ctx) == 3

    def test_ternary_none_semantics(self):
        """专门验证 is not None 与 falsy 值（如 0）的区分"""
        for x, y, expected in [(None, 10, 10), (0, 10, 0), (5, 10, 5)]:
            result = evaluate_expression("x if x is not None else y", {"x": x, "y": y})
            assert result == expected, f"x={x!r}, expected={expected}, got={result}"
            # 对比：or 写法会误判 0
            result_or = evaluate_expression("x or y", {"x": x, "y": y})
            if x == 0:
                assert result_or == y  # or 会误判 0 为 falsy
            else:
                assert result_or == expected


class TestComparisonOperators:
    """比较运算符测试"""

    def test_eq(self):
        assert evaluate_expression("1 == 1", {}) is True
        assert evaluate_expression("1 == 2", {}) is False

    def test_neq(self):
        assert evaluate_expression("1 != 2", {}) is True
        assert evaluate_expression("1 != 1", {}) is False

    def test_lt(self):
        assert evaluate_expression("1 < 2", {}) is True
        assert evaluate_expression("2 < 1", {}) is False

    def test_gt(self):
        assert evaluate_expression("2 > 1", {}) is True
        assert evaluate_expression("1 > 2", {}) is False

    def test_lte(self):
        assert evaluate_expression("1 <= 1", {}) is True
        assert evaluate_expression("2 <= 1", {}) is False

    def test_gte(self):
        assert evaluate_expression("1 >= 1", {}) is True
        assert evaluate_expression("1 >= 2", {}) is False


class TestBooleanLogic:
    """布尔运算测试"""

    def test_and_short_circuit(self):
        assert evaluate_expression("True and True", {}) is True
        assert evaluate_expression("True and False", {}) is False
        assert evaluate_expression("False and True", {}) is False

    def test_or_short_circuit(self):
        assert evaluate_expression("True or False", {}) is True
        assert evaluate_expression("False or True", {}) is True
        assert evaluate_expression("False or False", {}) is False

    def test_combined_bool_and_comparison(self):
        ctx = {"x": 5, "y": 10}
        assert evaluate_expression("x > 0 and y > x", ctx) is True
        assert evaluate_expression("x > 0 and y < x", ctx) is False


class TestDefenseCases:
    """防御性安全测试（必须全部抛 ExpressionSecurityError）"""

    def test_attribute_access(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("a.b", {"a": 1})

    def test_subclass_exploit(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("().__class__.__bases__[0].__subclasses__()", {})

    def test_assignment(self):
        # 赋值在 eval mode 下直接语法错误，属于预期安全行为
        with pytest.raises(ExpressionSyntaxError):
            evaluate_expression("a = 1", {})

    def test_lambda(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("lambda x: x", {})

    def test_exec(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("exec('print(1)')", {})

    def test_eval(self):
        with pytest.raises(ExpressionSecurityError):
            evaluate_expression("eval('1+1')", {})
