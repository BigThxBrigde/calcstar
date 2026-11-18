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
    body = expression.strip()
    if body.endswith("( )"):
        body = body[:-3].rstrip()
    body = body.removesuffix("=").strip()
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
        assert question.expression == f"{a} + {b} = ( )"


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
        assert question.paren_pos is None
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
    with_paren = [q for q in questions if q.paren_pos is not None]
    # 约半数含一层括号，但不允许全部带括号
    assert 0 < len(with_paren) < 50
    for question in questions:
        value, intermediates = evaluate_expression(question.expression)
        assert value == question.answer
        for item in (*intermediates, value):
            assert_in_bounds(item, 20)
        if question.paren_pos is not None:
            body = question.expression.removesuffix(" ( )")
            assert body.count("(") == body.count(")") == 1


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
            assert question.expression.endswith(" = ( )")
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
    assert set(expressions) == {"1 ÷ 1 = ( )", "2 ÷ 1 = ( )", "2 ÷ 2 = ( )"}
    # 加法范围 1 的全部组合为 0+0、0+1、1+0
    questions = generate_questions(make_config(OperationCategory.ADD, range_n=1, count=10, seed=4))
    assert {question.expression for question in questions} == {
        "0 + 0 = ( )", "0 + 1 = ( )", "1 + 0 = ( )"
    }
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


# ---- 三目链式算式（operand_count=3） ----


@pytest.mark.parametrize(
    "category", _ALL_CATEGORIES, ids=[category.value for category in _ALL_CATEGORIES]
)
def test_three_operand_structure(category):
    """三目模式：每题三个操作数、两个运算符，且批量产出充足。"""
    questions = generate_questions(
        make_config(category, range_n=30, count=40, seed=21, operand_count=3)
    )
    assert len(questions) == 40, category
    expressions = [question.expression for question in questions]
    assert len(set(expressions)) == 40, category
    for question in questions:
        assert len(question.operands) == 3, question.expression
        assert len(question.operators) == 2, question.expression
        assert question.blank_index is None


@pytest.mark.parametrize(
    "category", _ALL_CATEGORIES, ids=[category.value for category in _ALL_CATEGORIES]
)
def test_three_operand_bounds_and_consistency(category):
    """三目模式：操作数与结果落在范围内，求值与答案一致。"""
    range_n = 30
    questions = generate_questions(
        make_config(category, range_n=range_n, count=40, seed=23, operand_count=3)
    )
    for question in questions:
        for operand in question.operands:
            assert 0 <= operand <= range_n, (category, question.expression)
        assert 0 <= question.answer <= range_n, (category, question.expression)
        value, _ = evaluate_expression(question.expression)
        assert value == question.answer, (category, question.expression)


def test_three_operand_div_is_integral():
    """三目除法链逐级整除，商即答案。"""
    questions = generate_questions(
        make_config(OperationCategory.DIV, range_n=50, count=40, seed=29, operand_count=3)
    )
    for question in questions:
        dividend, divisor_b, divisor_c = question.operands
        assert question.operators == ("÷", "÷")
        assert dividend % divisor_b == 0
        assert (dividend // divisor_b) % divisor_c == 0
        assert question.answer == dividend // divisor_b // divisor_c


def test_three_operand_sub_allow_negative():
    """三目减法链允许负数时，中间与最终结果均不越界。"""
    questions = generate_questions(
        make_config(
            OperationCategory.SUB, range_n=20, count=40, seed=31,
            operand_count=3, allow_negative=True,
        )
    )
    assert any(question.answer < 0 for question in questions)
    for question in questions:
        a, b, c = question.operands
        assert question.operators == ("-", "-")
        first = a - b
        assert -20 <= first <= 20
        assert -20 <= question.answer <= 20


def test_mixed_three_operands_has_two_operators():
    """四则混合在 operand_count=3 时固定为两个运算符。"""
    questions = generate_questions(
        make_config(OperationCategory.MIXED, range_n=30, count=40, seed=37, operand_count=3)
    )
    for question in questions:
        assert len(question.operators) == 2, question.expression
        assert len(question.operands) == 3, question.expression
        assert any(op in "+-" for op in question.operators)
        assert any(op in "×÷" for op in question.operators)


def test_operand_count_random_mixes_two_and_three():
    """operand_count=-1 时每题随机两目或三目，两种均会出现。"""
    questions = generate_questions(
        make_config(OperationCategory.ADD_SUB, range_n=30, count=80, seed=41,
                    operand_count=-1)
    )
    sizes = {len(question.operands) for question in questions}
    assert sizes == {2, 3}
    for question in questions:
        assert len(question.operators) == len(question.operands) - 1
        value, _ = evaluate_expression(question.expression)
        assert value == question.answer, question.expression


# ---- 填空位置（blank_position） ----


def test_blank_position_last_keeps_result_form():
    """固定末尾（默认）：所有题形如 a op b = ( )，末尾空也用括号占位。"""
    for category in (OperationCategory.ADD, OperationCategory.MIXED):
        questions = generate_questions(
            make_config(category, range_n=20, count=30, seed=43)
        )
        for question in questions:
            assert question.blank_index is None
            assert question.expression.count("( )") == 1
            assert question.expression.endswith(" = ( )")


def _assert_hidden_operand_question(question, range_n: int) -> None:
    """校验一道隐藏操作数的填空题：还原后求值应等于等号后的结果。"""
    assert question.blank_index is not None
    assert 0 <= question.blank_index < len(question.operands)
    assert "( )" in question.expression
    hidden = question.operands[question.blank_index]
    assert 0 <= hidden <= range_n
    # 等号右侧给出原结果；把空白替换回真实操作数后应可求值且一致
    left, _, right = question.expression.rpartition(" = ")
    filled = left.replace("( )", str(hidden))
    value, _ = evaluate_expression(filled + " =")
    assert value == int(right), question.expression


def test_blank_position_any_hides_operands_and_results():
    """位置不定模式：既有求结果题也有藏操作数题，且藏数题答案正确。"""
    questions = generate_questions(
        make_config(OperationCategory.ADD_SUB, range_n=20, count=100, seed=47,
                    blank_position="any")
    )
    hidden_count = 0
    for question in questions:
        if question.blank_index is None:
            assert question.expression.endswith(" = ( )")
            assert question.expression.count("( )") == 1
        else:
            hidden_count += 1
            _assert_hidden_operand_question(question, 20)
    # 100 题中两种形式都应出现（约各半）
    assert 0 < hidden_count < 100


def test_blank_position_any_mixed_avoids_blank_adjacent_to_paren():
    """混合 + 括号 + 位置不定：空白不得紧贴括号，还原后求值一致。"""
    questions = generate_questions(
        make_config(
            OperationCategory.MIXED, range_n=20, count=60, seed=53,
            blank_position="any", include_parentheses=True,
        )
    )
    hidden_with_paren = 0
    for question in questions:
        if question.blank_index is None:
            continue
        if question.paren_pos is not None:
            hidden_with_paren += 1
            idx = question.expression.index("( )")
            # 空白前一个字符不应是 "("，其后一个字符不应是 ")"
            assert idx == 0 or question.expression[idx - 1] != "("
            end = idx + 3
            assert end >= len(question.expression) or question.expression[end] != ")"
        _assert_hidden_operand_question(question, 20)
    assert hidden_with_paren > 0


def test_blank_position_any_reproducible():
    """位置不定模式同样受种子控制，结果可复现。"""
    config = make_config(OperationCategory.ADD, range_n=20, count=30, seed=59,
                         blank_position="any")
    assert generate_questions(config) == generate_questions(config)
