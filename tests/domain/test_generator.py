"""generator 模块单元测试。

覆盖各运算类别的范围约束、减法负数开关、除法整除性、混合
运算结构与求值正确性、去重、种子可复现性以及参数边界。
"""

import pytest

from calcstar.config import OperationCategory
from calcstar.domain.generator import generate_questions
from calcstar.domain.models import PracticeConfig

_ALL_CATEGORIES = list(OperationCategory)


def make_config(category, range_n=20, count=100, **kwargs) -> PracticeConfig:
    """构造练习配置（不限时）。"""
    return PracticeConfig(
        category=category, range_n=range_n, count=count, duration_minutes=None, **kwargs
    )


# ---- 测试专用的独立求值器（调度场算法 + 逆波兰求值） ----

_PRECEDENCE = {"+": 1, "-": 1, "×": 2, "÷": 2}


def evaluate_expression(expression: str) -> tuple[int, list[int]]:
    """按先乘除后加减（支持一层括号）求值表达式文本。

    返回 (最终结果, 按求值顺序排列的中间结果)；遇到除数为零或
    除法不整除时抛出 ValueError，供测试断言整除性。
    """
    body = expression.removesuffix("=").strip()
    tokens = body.replace("(", " ( ").replace(")", " ) ").split()
    output: list = []
    stack: list[str] = []
    for token in tokens:
        if token == "(":
            stack.append(token)
        elif token == ")":
            while stack and stack[-1] != "(":
                output.append(stack.pop())
            stack.pop()
        elif token in _PRECEDENCE:
            while (
                stack
                and stack[-1] != "("
                and _PRECEDENCE[stack[-1]] >= _PRECEDENCE[token]
            ):
                output.append(stack.pop())
            stack.append(token)
        else:
            output.append(int(token))
    while stack:
        output.append(stack.pop())

    values: list[int] = []
    intermediates: list[int] = []
    for token in output:
        if isinstance(token, int):
            values.append(token)
            continue
        rhs = values.pop()
        lhs = values.pop()
        if token == "+":
            result = lhs + rhs
        elif token == "-":
            result = lhs - rhs
        elif token == "×":
            result = lhs * rhs
        else:
            if rhs == 0 or lhs % rhs != 0:
                raise ValueError(f"除法不整除或除数为零：{expression}")
            result = lhs // rhs
        intermediates.append(result)
        values.append(result)
    assert len(values) == 1, expression
    return values[0], intermediates


def assert_in_bounds(value: int, range_n: int, allow_negative: bool = False) -> None:
    """断言数值落在有效范围内。"""
    if allow_negative:
        assert -range_n <= value <= range_n
    else:
        assert 0 <= value <= range_n


# ---- 简单类别的范围约束 ----


def test_add_operands_and_result_within_range():
    questions = generate_questions(
        make_config(OperationCategory.ADD, range_n=20, count=100, seed=42)
    )
    assert len(questions) == 100
    for question in questions:
        assert question.operators == ("+",)
        assert len(question.operands) == 2
        assert all(0 <= value <= 20 for value in question.operands)
        assert question.answer == sum(question.operands)
        assert 0 <= question.answer <= 20
        a, b = question.operands
        assert question.expression == f"{a} + {b} ="


def test_sub_result_non_negative_by_default():
    questions = generate_questions(
        make_config(OperationCategory.SUB, range_n=20, count=100, seed=42)
    )
    assert len(questions) == 100
    for question in questions:
        a, b = question.operands
        assert question.operators == ("-",)
        assert all(0 <= value <= 20 for value in question.operands)
        assert question.answer == a - b
        assert 0 <= question.answer <= 20


def test_sub_allow_negative():
    questions = generate_questions(
        make_config(
            OperationCategory.SUB, range_n=20, count=100, seed=42, allow_negative=True
        )
    )
    assert len(questions) == 100
    for question in questions:
        a, b = question.operands
        assert question.answer == a - b
        assert -20 <= question.answer <= 20
    # 负数开关打开后应出现负数结果
    assert any(question.answer < 0 for question in questions)


def test_div_integrality_and_nonzero_divisor():
    questions = generate_questions(
        make_config(OperationCategory.DIV, range_n=50, count=100, seed=42)
    )
    assert len(questions) == 100
    for question in questions:
        dividend, divisor = question.operands
        assert question.operators == ("÷",)
        assert divisor >= 1
        assert 0 <= dividend <= 50
        assert dividend % divisor == 0
        assert question.answer == dividend // divisor
        assert 1 <= question.answer <= 50


def test_mul_product_within_range():
    questions = generate_questions(
        make_config(OperationCategory.MUL, range_n=20, count=100, seed=42)
    )
    assert len(questions) == 100
    for question in questions:
        a, b = question.operands
        assert question.operators == ("×",)
        assert all(0 <= value <= 20 for value in question.operands)
        assert question.answer == a * b
        assert 0 <= question.answer <= 20


def test_add_sub_category_contains_both_kinds():
    questions = generate_questions(
        make_config(OperationCategory.ADD_SUB, range_n=20, count=100, seed=42)
    )
    operators = {question.operators[0] for question in questions}
    assert operators == {"+", "-"}


def test_mul_div_category_contains_both_kinds():
    questions = generate_questions(
        make_config(OperationCategory.MUL_DIV, range_n=20, count=100, seed=42)
    )
    operators = {question.operators[0] for question in questions}
    assert operators == {"×", "÷"}


# ---- 混合运算 ----


def test_mixed_structure_and_evaluation_without_parentheses():
    questions = generate_questions(
        make_config(OperationCategory.MIXED, range_n=20, count=50, seed=7)
    )
    assert len(questions) == 50
    for question in questions:
        assert 2 <= len(question.operators) <= 3
        assert "(" not in question.expression
        # 四则混合：加减与乘除至少各含一个
        assert any(op in "+-" for op in question.operators)
        assert any(op in "×÷" for op in question.operators)
        value, intermediates = evaluate_expression(question.expression)
        assert value == question.answer
        # 所有中间结果与最终结果均落在 [0, N]
        for item in (*intermediates, value):
            assert_in_bounds(item, 20)


def test_mixed_with_parentheses():
    questions = generate_questions(
        make_config(
            OperationCategory.MIXED, range_n=20, count=50, seed=7,
            include_parentheses=True,
        )
    )
    assert len(questions) == 50
    with_paren = [q for q in questions if "(" in q.expression]
    # 约半数含一层括号，但不允许全部带括号
    assert 0 < len(with_paren) < 50
    for question in questions:
        value, intermediates = evaluate_expression(question.expression)
        assert value == question.answer
        for item in (*intermediates, value):
            assert_in_bounds(item, 20)
        if "(" in question.expression:
            assert question.expression.count("(") == question.expression.count(")") == 1


def test_mixed_allow_negative_bounds():
    questions = generate_questions(
        make_config(
            OperationCategory.MIXED, range_n=30, count=50, seed=5, allow_negative=True
        )
    )
    for question in questions:
        value, intermediates = evaluate_expression(question.expression)
        assert value == question.answer
        for item in (*intermediates, value):
            assert_in_bounds(item, 30, allow_negative=True)
    assert any(question.answer < 0 for question in questions)


# ---- 去重、可复现性与批量语义 ----


def test_questions_are_unique():
    for category in (OperationCategory.ADD, OperationCategory.MIXED):
        questions = generate_questions(
            make_config(category, range_n=20, count=50, seed=3)
        )
        expressions = [question.expression for question in questions]
        assert len(expressions) == 50
        assert len(set(expressions)) == 50


def test_same_seed_reproduces_same_questions():
    config = make_config(OperationCategory.ADD_SUB, range_n=20, count=30, seed=7)
    assert generate_questions(config) == generate_questions(config)
    config_mixed = make_config(
        OperationCategory.MIXED, range_n=20, count=30, seed=7,
        include_parentheses=True,
    )
    assert generate_questions(config_mixed) == generate_questions(config_mixed)


def test_different_seed_changes_questions():
    first = generate_questions(make_config(OperationCategory.ADD, count=30, seed=1))
    second = generate_questions(make_config(OperationCategory.ADD, count=30, seed=2))
    assert first != second


def test_all_seven_categories_generate_full_count():
    for category in _ALL_CATEGORIES:
        questions = generate_questions(
            make_config(category, range_n=20, count=30, seed=11)
        )
        assert len(questions) == 30, category
        expressions = [question.expression for question in questions]
        assert len(set(expressions)) == 30, category
        for question in questions:
            assert question.expression.endswith(" =")
            evaluate_expression(question.expression)


# ---- 参数边界与候选空间耗尽 ----


def test_count_one():
    for category in _ALL_CATEGORIES:
        questions = generate_questions(make_config(category, count=1, seed=2))
        assert len(questions) == 1, category


def test_range_one_boundary():
    for category in _ALL_CATEGORIES:
        questions = generate_questions(
            make_config(category, range_n=1, count=10, seed=2)
        )
        expressions = [question.expression for question in questions]
        assert len(set(expressions)) == len(expressions), category
        for question in questions:
            assert all(-1 <= value <= 1 for value in (*question.operands, question.answer))
            if category is OperationCategory.MIXED:
                value, intermediates = evaluate_expression(question.expression)
                assert value == question.answer
                for item in (*intermediates, value):
                    assert_in_bounds(item, 1)


def test_exhausted_space_returns_all_available():
    # 除法范围 2 的全部合法组合只有 1÷1、2÷1、2÷2 三种
    questions = generate_questions(make_config(OperationCategory.DIV, range_n=2, count=50, seed=4))
    expressions = [question.expression for question in questions]
    assert len(expressions) == 3
    assert len(set(expressions)) == 3
    assert set(expressions) == {"1 ÷ 1 =", "2 ÷ 1 =", "2 ÷ 2 ="}
    # 加法范围 1 的全部组合为 0+0、0+1、1+0
    questions = generate_questions(make_config(OperationCategory.ADD, range_n=1, count=10, seed=4))
    assert {question.expression for question in questions} == {"0 + 0 =", "0 + 1 =", "1 + 0 ="}
    # 除法范围 20 的合法空间共 sum(20 // q) 种，count=100 时应全部返回且不重复
    questions = generate_questions(make_config(OperationCategory.DIV, range_n=20, count=100, seed=4))
    expected_space = sum(20 // quotient for quotient in range(1, 21))
    expressions = [question.expression for question in questions]
    assert len(expressions) == expected_space
    assert len(set(expressions)) == expected_space


def test_range_boundary_values_respected_for_all_categories():
    range_n = 30
    for category in _ALL_CATEGORIES:
        questions = generate_questions(
            make_config(category, range_n=range_n, count=60, seed=13)
        )
        for question in questions:
            for operand in question.operands:
                assert 0 <= operand <= range_n, (category, question.expression)


@pytest.mark.parametrize(
    "category", _ALL_CATEGORIES, ids=[category.value for category in _ALL_CATEGORIES]
)
def test_expression_format_and_answer_consistency(category):
    questions = generate_questions(
        make_config(category, range_n=25, count=40, seed=17)
    )
    for question in questions:
        value, _ = evaluate_expression(question.expression)
        assert value == question.answer, question.expression
