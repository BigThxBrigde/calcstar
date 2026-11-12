"""口算题目生成器（domain 层）。

根据 :class:`PracticeConfig` 生成各类别的口算题目：

- 内部使用独立播种的 :class:`random.Random`，同一种子生成结果
  完全可复现；
- 严格满足各范畴的范围约束（操作数、结果均落在 ``[0, N]``，
  除法整除、乘法积不超界等），并尽量避免 ``a+0``、``a-0``、
  ``a-a``、``0×a``、``a÷1`` 这类过于简单的题目（空间不足时自动
  放宽）；
- 混合运算含 2–3 个运算符，严格遵循先乘除后加减，每个除法
  步骤整除，所有中间结果与最终结果均落在有效范围内；
- 纯逻辑实现，不做任何 IO。
"""

from __future__ import annotations

import random

from calcstar.config import OperationCategory
from calcstar.domain.models import PracticeConfig, Question

#: 加法显示符号
_OP_ADD = "+"
#: 减法显示符号
_OP_SUB = "-"
#: 乘法显示符号
_OP_MUL = "×"
#: 除法显示符号
_OP_DIV = "÷"

#: 低优先级运算符（加减）
_LOW_PRECEDENCE = (_OP_ADD, _OP_SUB)
#: 高优先级运算符（乘除）
_HIGH_PRECEDENCE = (_OP_MUL, _OP_DIV)

#: 同一放宽级别内单题生成的最大尝试次数
_MAX_ATTEMPTS = 100
#: 混合运算单题的最大采样尝试次数（含整除性等拒绝重试）
_MIXED_ATTEMPTS = 300


def _make_question(
    operands: tuple[int, ...], operators: tuple[str, ...], answer: int
) -> Question:
    """按统一格式把操作数与运算符组装成 :class:`Question`。"""
    parts = [str(operands[0])]
    for operator, operand in zip(operators, operands[1:]):
        parts.append(operator)
        parts.append(str(operand))
    return Question(
        expression=" ".join(parts) + " =",
        answer=answer,
        operands=operands,
        operators=operators,
    )


# ---- 四则基本类别的单题生成（直接构造，不依赖拒绝采样） ----


def _generate_add(rng: random.Random, config: PracticeConfig, level: int) -> Question | None:
    """生成一道加法题：操作数与结果均落在 ``[0, N]``。

    level 0 额外避免 ``a+0`` / ``0+a``；level 1 放开该限制。
    """
    n = config.range_n
    if level == 0:
        if n < 2:
            return None
        a = rng.randint(1, n - 1)
        b = rng.randint(1, n - a)
    else:
        a = rng.randint(0, n)
        b = rng.randint(0, n - a)
    return _make_question((a, b), (_OP_ADD,), a + b)


def _generate_sub(rng: random.Random, config: PracticeConfig, level: int) -> Question | None:
    """生成一道减法题：操作数与结果（或结果的绝对值）均落在 ``[0, N]``。

    level 0 额外避免 ``a-0`` / ``a-a``；level 1 放开该限制。
    ``allow_negative=True`` 时结果可为负。
    """
    n = config.range_n
    if config.allow_negative:
        if level == 0:
            for _ in range(_MAX_ATTEMPTS):
                b = rng.randint(1, n)
                a = rng.randint(0, n)
                if a != b:
                    break
            else:
                return None
        else:
            a = rng.randint(0, n)
            b = rng.randint(0, n)
    elif level == 0:
        if n < 2:
            return None
        a = rng.randint(2, n)
        b = rng.randint(1, a - 1)
    else:
        a = rng.randint(0, n)
        b = rng.randint(0, a)
    return _make_question((a, b), (_OP_SUB,), a - b)


def _generate_mul(rng: random.Random, config: PracticeConfig, level: int) -> Question | None:
    """生成一道乘法题：因数落在 ``[0, N]`` 且积不超过 ``N``。

    level 0 额外避免 0 因子；level 1 放开该限制。
    """
    n = config.range_n
    if level == 0:
        a = rng.randint(1, n)
        b = rng.randint(1, n // a)
    else:
        a = rng.randint(0, n)
        if a == 0:
            b = rng.randint(0, n)
        else:
            b = rng.randint(0, n // a)
    return _make_question((a, b), (_OP_MUL,), a * b)


def _generate_div(rng: random.Random, config: PracticeConfig, level: int) -> Question | None:
    """生成一道除法题：商落在 ``[1, N]``、除数落在 ``[1, N]`` 且整除。

    通过 ``被除数 = 商 × 除数`` 直接构造保证整除，且被除数不超过
    ``N``。level 0 额外避免 ``a÷1``；level 1 放开该限制。
    """
    n = config.range_n
    if level == 0:
        if n < 2:
            return None
        quotient = rng.randint(1, n // 2)
        divisor = rng.randint(2, n // quotient)
    else:
        quotient = rng.randint(1, n)
        divisor = rng.randint(1, n // quotient)
    dividend = quotient * divisor
    return _make_question((dividend, divisor), (_OP_DIV,), quotient)


# ---- 复合类别的单题生成（每题随机落入其中一种基本类别） ----


def _generate_add_sub(rng: random.Random, config: PracticeConfig, level: int) -> Question | None:
    """生成一道加减法题：加法与减法各约 50%。"""
    if rng.random() < 0.5:
        return _generate_add(rng, config, level)
    return _generate_sub(rng, config, level)


def _generate_mul_div(rng: random.Random, config: PracticeConfig, level: int) -> Question | None:
    """生成一道乘除法题：乘法与除法各约 50%。"""
    if rng.random() < 0.5:
        return _generate_mul(rng, config, level)
    return _generate_div(rng, config, level)


# ---- 混合运算（mixed）：随机构造 + 重试采样 + 小型求值器校验 ----


class _InvalidExpression(Exception):
    """候选混合表达式不满足约束（除数为零、除法不整除等）。"""


def _in_bounds(value: int, n: int, allow_negative: bool) -> bool:
    """判断数值是否落在有效范围内。

    默认要求 ``0 <= value <= N``；``allow_negative=True`` 时允许为负，
    但绝对值不超过 ``N``。
    """
    if allow_negative:
        return -n <= value <= n
    return 0 <= value <= n


def _random_mixed_operators(rng: random.Random, count: int) -> list[str]:
    """随机生成 ``count`` 个运算符，保证加减与乘除至少各含一个。

    体现"四则混合"的题意：避免出现纯加减（如 ``a+b+c``）或
    纯乘除（如 ``a×b÷c``）的题目。
    """
    while True:
        operators = [rng.choice((*_LOW_PRECEDENCE, *_HIGH_PRECEDENCE)) for _ in range(count)]
        if any(op in _HIGH_PRECEDENCE for op in operators) and any(
            op in _LOW_PRECEDENCE for op in operators
        ):
            return operators


def _build_tokens(
    operands: list[int], operators: list[str], paren_pos: int | None
) -> list[int | str]:
    """把操作数与运算符展平成 token 序列，可选在某处包一层括号。

    ``paren_pos`` 为运算符下标，表示以其相邻两个操作数为一组
    加括号，如 ``(a+b)×c``、``a×(b-c)``。
    """
    tokens: list[int | str] = [operands[0]]
    for operator, operand in zip(operators, operands[1:]):
        tokens.append(operator)
        tokens.append(operand)
    if paren_pos is not None:
        start = 2 * paren_pos
        tokens.insert(start, "(")
        tokens.insert(start + 4, ")")
    return tokens


def _format_tokens(tokens: list[int | str]) -> str:
    """把 token 序列格式化为显示文本，括号内侧不加空格。"""
    text = ""
    for token in tokens:
        piece = str(token)
        if not text:
            text = piece
        elif piece == ")" or text.endswith("("):
            text += piece
        else:
            text += " " + piece
    return text + " ="


def _parse_factor(
    tokens: list[int | str], pos: int, intermediates: list[int]
) -> tuple[int, int]:
    """解析因子：数字或括号子表达式。返回 (值, 下一个位置)。"""
    token = tokens[pos]
    if token == "(":
        value, pos = _parse_expr(tokens, pos + 1, intermediates)
        if pos >= len(tokens) or tokens[pos] != ")":
            raise _InvalidExpression
        return value, pos + 1
    if not isinstance(token, int):
        raise _InvalidExpression
    return token, pos + 1


def _parse_term(
    tokens: list[int | str], pos: int, intermediates: list[int]
) -> tuple[int, int]:
    """解析乘除项（高优先级）。除数为零或不整除即拒绝。"""
    value, pos = _parse_factor(tokens, pos, intermediates)
    while pos < len(tokens) and tokens[pos] in _HIGH_PRECEDENCE:
        operator = tokens[pos]
        rhs, pos = _parse_factor(tokens, pos + 1, intermediates)
        if operator == _OP_MUL:
            value = value * rhs
        else:
            if rhs == 0 or value % rhs != 0:
                raise _InvalidExpression
            value = value // rhs
        intermediates.append(value)
    return value, pos


def _parse_expr(
    tokens: list[int | str], pos: int, intermediates: list[int]
) -> tuple[int, int]:
    """解析加减表达式（低优先级），项内先完成乘除。"""
    value, pos = _parse_term(tokens, pos, intermediates)
    while pos < len(tokens) and tokens[pos] in _LOW_PRECEDENCE:
        operator = tokens[pos]
        rhs, pos = _parse_term(tokens, pos + 1, intermediates)
        value = value + rhs if operator == _OP_ADD else value - rhs
        intermediates.append(value)
    return value, pos


def _evaluate_tokens(tokens: list[int | str]) -> tuple[int, list[int]]:
    """按先乘除后加减（含一层括号）求值 token 序列。

    返回 (最终结果, 按求值顺序排列的全部中间结果)；候选表达式
    存在除数为零或不整除时抛出 :class:`_InvalidExpression`。
    """
    intermediates: list[int] = []
    value, pos = _parse_expr(tokens, 0, intermediates)
    if pos != len(tokens):
        raise _InvalidExpression
    return value, intermediates


def _generate_mixed(rng: random.Random, config: PracticeConfig, level: int) -> Question | None:
    """生成一道四则混合运算题。

    表达式含 2–3 个运算符（随机），严格遵循先乘除后加减；每个
    除法步骤整除；所有中间结果与最终结果均落在有效范围内
    （``allow_negative=True`` 时允许为负且绝对值不超过 ``N``）。
    ``include_parentheses=True`` 时约半数题目含一层括号。
    采样的候选经求值器校验，不满足约束即重试。
    """
    n = config.range_n
    for _ in range(_MIXED_ATTEMPTS):
        operator_count = rng.choice((2, 3))
        paren_pos = None
        if config.include_parentheses and rng.random() < 0.5:
            paren_pos = rng.randrange(operator_count)
        operators = _random_mixed_operators(rng, operator_count)
        if level == 0:
            operands = [rng.randint(1, n) for _ in range(operator_count + 1)]
        else:
            operands = [rng.randint(0, n) for _ in range(operator_count + 1)]
        tokens = _build_tokens(operands, operators, paren_pos)
        try:
            value, intermediates = _evaluate_tokens(tokens)
        except _InvalidExpression:
            continue
        if not all(
            _in_bounds(item, n, config.allow_negative) for item in (*intermediates, value)
        ):
            continue
        return Question(
            expression=_format_tokens(tokens),
            answer=value,
            operands=tuple(operands),
            operators=tuple(operators),
        )
    return None


#: 类别 -> 单题生成函数
_CATEGORY_GENERATORS = {
    OperationCategory.ADD: _generate_add,
    OperationCategory.SUB: _generate_sub,
    OperationCategory.ADD_SUB: _generate_add_sub,
    OperationCategory.MUL: _generate_mul,
    OperationCategory.DIV: _generate_div,
    OperationCategory.MUL_DIV: _generate_mul_div,
    OperationCategory.MIXED: _generate_mixed,
}


def _generate_one(rng: random.Random, config: PracticeConfig) -> Question:
    """按放宽级别从高到低（0 -> 1）生成一道题，全部失败返回 None。

    级别 0 的约束更严格（避免零因子、``a÷1`` 等平凡题目），
    级别 1 放开这些限制，保证小范围下仍能出题。
    """
    generator = _CATEGORY_GENERATORS[config.category]
    for level in (0, 1):
        question = generator(rng, config, level)
        if question is not None:
            return question
    return None


def generate_questions(config: PracticeConfig) -> list[Question]:
    """按配置批量生成口算题目。

    返回恰好 ``config.count`` 道题目（小范围下由放宽级别保证
    可出题；混合运算在极小范围内可能少于请求数量）。
    """
    rng = random.Random(config.seed)
    questions: list[Question] = []
    for _ in range(config.count):
        question = _generate_one(rng, config)
        if question is None:
            break
        questions.append(question)
    return questions
