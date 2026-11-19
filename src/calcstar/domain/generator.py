"""口算题目生成器（domain 层）。

根据 :class:`PracticeConfig` 生成各类别的口算题目：

- 内部使用独立播种的 :class:`random.Random`，同一种子生成结果
  完全可复现；
- 严格满足各范畴的范围约束（操作数、结果均落在 ``[0, N]``，
  除法整除、乘法积不超界等），并尽量避免 ``a+0``、``a-0``、
  ``a-a``、``0×a``、``a÷1`` 这类过于简单的题目（空间不足时自动
  放宽）；
- 批量生成时以表达式文本判重，保证题目互不重复；候选空间
  不足时按级别放宽约束（放开零因子与 ``a÷1`` 限制、必要时
  穷举全部合法组合），仍不足则返回实际可用数量，绝不重复、
  绝不死循环；
- 纯逻辑实现，不做任何 IO。
"""

from __future__ import annotations

import random
from dataclasses import replace

from calcstar.config import (
    BLANK_POSITION_ANY,
    BLANK_POSITION_LAST,
    BLANK_POSITION_MIDDLE,
    OPERAND_COUNT_RANDOM,
    OperationCategory,
)
from calcstar.domain.models import PracticeConfig, Question

#: 加法显示符号
_OP_ADD = "+"
#: 减法显示符号
_OP_SUB = "-"
#: 乘法显示符号
_OP_MUL = "×"
#: 除法显示符号
_OP_DIV = "÷"

#: 填空统一占位记号：空在中间或末尾都用括号占位
_BLANK_TOKEN = "( )"

#: 低优先级运算符（加减）
_LOW_PRECEDENCE = (_OP_ADD, _OP_SUB)
#: 高优先级运算符（乘除）
_HIGH_PRECEDENCE = (_OP_MUL, _OP_DIV)

#: 同一放宽级别内单题生成的最大尝试次数
_MAX_ATTEMPTS = 100
#: 混合运算单题的最大采样尝试次数（含整除性等拒绝重试）
_MIXED_ATTEMPTS = 300
#: 批量生成每个放宽级别的基础尝试次数上限
_BATCH_ATTEMPTS_BASE = 500
#: 批量生成每个放宽级别按题数追加的尝试次数
_BATCH_ATTEMPTS_PER_QUESTION = 60
#: 同一放宽级别内连续未产出新题（采样失败或重复）的容忍次数
_LEVEL_STALL_LIMIT = 500
#: 穷举兜底允许的最大候选格数，超过视为空间充足、跳过穷举
_MAX_ENUM_CELLS = 250_000


def _make_question(
    operands: tuple[int, ...], operators: tuple[str, ...], answer: int
) -> Question:
    """按统一格式把操作数与运算符组装成 :class:`Question`。"""
    parts = [str(operands[0])]
    for operator, operand in zip(operators, operands[1:]):
        parts.append(operator)
        parts.append(str(operand))
    return Question(
        expression=" ".join(parts) + " = " + _BLANK_TOKEN,
        answer=answer,
        operands=operands,
        operators=operators,
    )


# ---- 四则基本类别的单题生成（直接构造，不依赖拒绝采样） ----


def _generate_add(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
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


def _generate_sub(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
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


def _generate_mul(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
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


def _generate_div(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
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


def _generate_add_sub(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成一道加减法题：加法与减法各约 50%。"""
    if rng.random() < 0.5:
        return _generate_add(rng, config, level)
    return _generate_sub(rng, config, level)


def _generate_mul_div(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成一道乘除法题：乘法与除法各约 50%。"""
    if rng.random() < 0.5:
        return _generate_mul(rng, config, level)
    return _generate_div(rng, config, level)


# ---- 三目链式算式（operand_count=3）：三个操作数、两个运算符 ----


def _generate_add3(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成三目加法链 ``a + b + c``：各部分和与结果均落在 ``[0, N]``。

    level 0 要求各操作数至少为 1（避免 ``+0``）；level 1 放开。
    """
    n = config.range_n
    if level == 0:
        if n < 3:
            return None
        a = rng.randint(1, n - 2)
        b = rng.randint(1, n - a - 1)
        c = rng.randint(1, n - a - b)
    else:
        a = rng.randint(0, n)
        b = rng.randint(0, n - a)
        c = rng.randint(0, n - a - b)
    return _make_question((a, b, c), (_OP_ADD, _OP_ADD), a + b + c)


def _generate_sub3(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成三目减法链 ``a - b - c``。

    非负模式要求中间与最终结果均落在 ``[0, N]``（level 0 额外避免
    ``-0`` 与 ``a-a``）；``allow_negative=True`` 时结果与中间值可为
    负但绝对值不超过 ``N``。
    """
    n = config.range_n
    if config.allow_negative:
        for _ in range(_MAX_ATTEMPTS):
            a = rng.randint(0, n)
            b = rng.randint(0, n)
            c = rng.randint(0, n)
            first = a - b
            result = first - c
            if not (-n <= first <= n and -n <= result <= n):
                continue
            if level == 0 and (b == 0 or c == 0 or a == b):
                continue
            return _make_question((a, b, c), (_OP_SUB, _OP_SUB), result)
        return None
    if level == 0:
        if n < 2:
            return None
        result = rng.randint(0, n - 2)
        c = rng.randint(1, n - 1 - result)
        b = rng.randint(1, n - result - c)
        a = b + c + result
    else:
        result = rng.randint(0, n)
        c = rng.randint(0, n - result)
        b = rng.randint(0, n - result - c)
        a = b + c + result
    return _make_question((a, b, c), (_OP_SUB, _OP_SUB), a - b - c)


def _generate_mul3(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成三目乘法链 ``a × b × c``：积不超过 ``N``。

    level 0 额外避免 0 因子；level 1 放开该限制。
    """
    n = config.range_n
    if level == 0:
        a = rng.randint(1, n)
        b = rng.randint(1, n // a)
        c = rng.randint(1, n // (a * b))
    else:
        a = rng.randint(0, n)
        if a == 0:
            b = rng.randint(0, n)
            c = rng.randint(0, n)
        else:
            b = rng.randint(0, n // a)
            c = rng.randint(0, n // (a * b)) if b else rng.randint(0, n)
    return _make_question((a, b, c), (_OP_MUL, _OP_MUL), a * b * c)


def _generate_div3(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成三目除法链 ``a ÷ b ÷ c``：从商出发构造保证整除。

    level 0 要求除数至少为 2、商至少为 1；level 1 放开除数为 1。
    被除数 = 商 × b × c，不超过 ``N``。
    """
    n = config.range_n
    if level == 0:
        if n < 4:
            return None
        for _ in range(_MAX_ATTEMPTS):
            quotient = rng.randint(1, n // 4)
            b = rng.randint(2, n // quotient)
            hi = n // (quotient * b)
            if hi >= 2:
                c = rng.randint(2, hi)
                return _make_question(
                    (quotient * b * c, b, c), (_OP_DIV, _OP_DIV), quotient
                )
        return None
    quotient = rng.randint(1, n)
    b = rng.randint(1, n // quotient)
    c = rng.randint(1, n // (quotient * b))
    return _make_question(
        (quotient * b * c, b, c), (_OP_DIV, _OP_DIV), quotient
    )


def _generate_chain_n(
    rng: random.Random,
    config: PracticeConfig,
    level: int,
    pool: tuple[str, ...],
    count: int,
) -> Question | None:
    """生成 ``count + 1`` 目、``count`` 个运算符的链式算式。

    运算符均从 ``pool`` 随机取得（单元素池即固定运算），同级运算
    从左到右依次求值。操作数逐项采样：乘法按剩余空间收缩上界、
    除法从当前值的因子中选取以保证整除；每个中间结果与最终结果
    均落在有效范围内。不满足约束即拒绝重试，耗尽返回 ``None``。
    """
    n = config.range_n
    for _ in range(_MIXED_ATTEMPTS):
        operators = tuple(rng.choice(pool) for _ in range(count))
        cur = rng.randint(1 if level == 0 else 0, n)
        operands: list[int] = [cur]
        ok = True
        for operator in operators:
            if operator == _OP_DIV:
                magnitude = abs(cur)
                low = 2 if level == 0 else 1
                if magnitude == 0:
                    if level == 0:
                        ok = False
                        break
                    operand = rng.randint(1, n)
                else:
                    divisors = [
                        d
                        for d in range(low, min(magnitude, n) + 1)
                        if magnitude % d == 0
                    ]
                    if not divisors:
                        ok = False
                        break
                    operand = rng.choice(divisors)
                cur = cur // operand
            elif operator == _OP_MUL:
                magnitude = abs(cur)
                if magnitude == 0:
                    operand = rng.randint(0, n)
                else:
                    hi = n // magnitude
                    low = 1 if level == 0 else 0
                    if hi < low:
                        ok = False
                        break
                    operand = rng.randint(low, hi)
                cur = cur * operand
            else:
                operand = rng.randint(1 if level == 0 else 0, n)
                cur = cur + operand if operator == _OP_ADD else cur - operand
                if not config.allow_negative and level == 0 and cur < 1:
                    ok = False
                    break
            if not _in_bounds(cur, n, config.allow_negative):
                ok = False
                break
            operands.append(operand)
        if not ok:
            continue
        return _make_question(tuple(operands), operators, cur)
    return None


def _generate_chain3(
    rng: random.Random,
    config: PracticeConfig,
    level: int,
    pool: tuple[str, str],
) -> Question | None:
    """生成三目双运算符链式算式（保留原有两目池调用约定）。"""
    return _generate_chain_n(rng, config, level, pool, 2)


def _generate_add_n(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成 config.operand_count 目加法链：各操作数之和不超过 N。

    按剩余预算逐项采样，避免多目时随机累加屡屡越界。
    """
    n = config.range_n
    count = config.operand_count
    low = 1 if level == 0 else 0
    operands: list[int] = []
    remaining = n
    for index in range(count):
        hi = remaining - (count - index - 1) * low
        if hi < low:
            return None
        value = rng.randint(low, hi)
        operands.append(value)
        remaining -= value
    return _make_question(
        tuple(operands), (_OP_ADD,) * (count - 1), sum(operands)
    )


def _generate_sub_n(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成 config.operand_count 目减法链：中间与最终结果均为非负。

    从结果和 ``count - 1`` 个减数反推首项，保证从左到右每一步都不小于 0。
    """
    n = config.range_n
    count = config.operand_count
    low = 1 if level == 0 else 0
    tail: list[int] = []
    remaining = n
    for index in range(count - 1):
        hi = remaining - (count - index - 2) * low
        if hi < low:
            return None
        value = rng.randint(low, hi)
        tail.append(value)
        remaining -= value
    result = rng.randint(0, remaining)
    operands = (result + sum(tail), *tail)
    return _make_question(operands, (_OP_SUB,) * (count - 1), result)


def _generate_mul_n(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成 config.operand_count 目乘法链。"""
    return _generate_chain_n(
        rng, config, level, (_OP_MUL,), config.operand_count - 1
    )


def _generate_div_n(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成 config.operand_count 目除法链（逐级整除）。"""
    return _generate_chain_n(
        rng, config, level, (_OP_DIV,), config.operand_count - 1
    )


def _generate_add_sub_n(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成 config.operand_count 目加减混合链。"""
    return _generate_chain_n(
        rng, config, level, _LOW_PRECEDENCE, config.operand_count - 1
    )


def _generate_mul_div_n(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成 config.operand_count 目乘除混合链。"""
    return _generate_chain_n(
        rng, config, level, _HIGH_PRECEDENCE, config.operand_count - 1
    )


def _generate_add_sub3(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成三目加减混合链：两个运算符各自从 ``{+,-}`` 随机。"""
    return _generate_chain3(rng, config, level, _LOW_PRECEDENCE)


def _generate_mul_div3(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成三目乘除混合链：两个运算符各自从 ``{×,÷}`` 随机。"""
    return _generate_chain3(rng, config, level, _HIGH_PRECEDENCE)


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
        operators = [
            rng.choice((*_LOW_PRECEDENCE, *_HIGH_PRECEDENCE))
            for _ in range(count)
        ]
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
    """把 token 序列格式化为算式主体文本，括号内侧不加空格。"""
    text = ""
    for token in tokens:
        piece = str(token)
        if not text:
            text = piece
        elif piece == ")" or text.endswith("("):
            text += piece
        else:
            text += " " + piece
    return text


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


def _generate_mixed(
    rng: random.Random, config: PracticeConfig, level: int
) -> Question | None:
    """生成一道四则混合运算题。

    表达式默认含 2–3 个运算符（随机），``config.operand_count >= 3``
    时固定为目数减 1 个运算符；严格遵循先乘除后加减；每个
    除法步骤整除；所有中间结果与最终结果均落在有效范围内
    （``allow_negative=True`` 时允许为负且绝对值不超过 ``N``）。
    ``include_parentheses=True`` 时约半数题目含一层括号。
    采样的候选经求值器校验，不满足约束即重试。
    """
    n = config.range_n
    for _ in range(_MIXED_ATTEMPTS):
        if config.operand_count >= 3:
            operator_count = config.operand_count - 1
        else:
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
            _in_bounds(item, n, config.allow_negative)
            for item in (*intermediates, value)
        ):
            continue
        return Question(
            expression=_format_tokens(tokens) + " = " + _BLANK_TOKEN,
            answer=value,
            operands=tuple(operands),
            operators=tuple(operators),
            paren_pos=paren_pos,
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

#: 类别 -> 三目（三个操作数）单题生成函数
_CATEGORY_GENERATORS3 = {
    OperationCategory.ADD: _generate_add3,
    OperationCategory.SUB: _generate_sub3,
    OperationCategory.ADD_SUB: _generate_add_sub3,
    OperationCategory.MUL: _generate_mul3,
    OperationCategory.DIV: _generate_div3,
    OperationCategory.MUL_DIV: _generate_mul_div3,
    OperationCategory.MIXED: _generate_mixed,
}

#: 类别 -> 4~10 目单题生成函数（目数取 config.operand_count）
_CATEGORY_GENERATORS_N = {
    OperationCategory.ADD: _generate_add_n,
    OperationCategory.SUB: _generate_sub_n,
    OperationCategory.ADD_SUB: _generate_add_sub_n,
    OperationCategory.MUL: _generate_mul_n,
    OperationCategory.DIV: _generate_div_n,
    OperationCategory.MUL_DIV: _generate_mul_div_n,
    OperationCategory.MIXED: _generate_mixed,
}


# ---- 填空位置：固定末尾、固定在算式中或两种随机 ----


def _blank_question(
    question: Question, rng: random.Random, mode: str
) -> Question:
    """按填空位置模式处理题目。

    无论空在中间还是末尾，统一用括号记号 ``( )`` 占位：

    - ``mode == "last"``：固定求等号右侧结果，形如 ``3 + 5 = ( )``；
    - ``mode == "middle"``：固定在算式中隐藏一个操作数，形如
      ``3 + ( ) - 2 = 5``；
    - ``mode == "any"``：两种随机，约半数求结果。

    答案为被隐藏操作数的值；混合运算中被隐藏操作数与括号组相邻时
    回退为求结果，避免括号包住空白。
    """
    if mode == BLANK_POSITION_LAST or not question.operands:
        return question
    if mode == BLANK_POSITION_MIDDLE:
        hide = True
    elif mode == BLANK_POSITION_ANY:
        hide = rng.random() >= 0.5
    else:
        return question
    if not hide:
        return question
    idx = rng.randrange(len(question.operands))
    if question.paren_pos is not None and idx in (
        question.paren_pos,
        question.paren_pos + 1,
    ):
        return question
    operands = list(question.operands)
    answer = operands[idx]
    operands[idx] = _BLANK_TOKEN
    if question.paren_pos is None:
        parts = [str(operands[0])]
        for operator, operand in zip(question.operators, operands[1:]):
            parts.append(operator)
            parts.append(str(operand))
        expression = " ".join(parts) + " = " + str(question.answer)
    else:
        tokens = _build_tokens(
            operands, list(question.operators), question.paren_pos
        )
        expression = _format_tokens(tokens) + " = " + str(question.answer)
    return Question(
        expression=expression,
        answer=answer,
        operands=question.operands,
        operators=question.operators,
        blank_index=idx,
        paren_pos=question.paren_pos,
    )


# ---- 穷举兜底：候选空间耗尽时枚举全部合法组合 ----


def _enumerate_add(config: PracticeConfig) -> list[Question]:
    """穷举全部加法组合（含 ``+0``）。"""
    n = config.range_n
    return [
        _make_question((a, b), (_OP_ADD,), a + b)
        for a in range(n + 1)
        for b in range(n + 1 - a)
    ]


def _enumerate_sub(config: PracticeConfig) -> list[Question]:
    """穷举全部减法组合（含 ``-0`` 与 ``a-a``）。"""
    n = config.range_n
    if config.allow_negative:
        return [
            _make_question((a, b), (_OP_SUB,), a - b)
            for a in range(n + 1)
            for b in range(n + 1)
        ]
    return [
        _make_question((a, b), (_OP_SUB,), a - b)
        for a in range(n + 1)
        for b in range(a + 1)
    ]


def _enumerate_mul(config: PracticeConfig) -> list[Question]:
    """穷举全部乘法组合（含 0 因子），积不超过 ``N``。"""
    n = config.range_n
    questions: list[Question] = []
    for a in range(n + 1):
        for b in range(n + 1 if a == 0 else n // a + 1):
            questions.append(_make_question((a, b), (_OP_MUL,), a * b))
    return questions


def _enumerate_div(config: PracticeConfig) -> list[Question]:
    """穷举全部除法组合（含 ``a÷1``），商与被除数均不超界。"""
    n = config.range_n
    questions: list[Question] = []
    for quotient in range(1, n + 1):
        for divisor in range(1, n // quotient + 1):
            dividend = quotient * divisor
            questions.append(
                _make_question((dividend, divisor), (_OP_DIV,), quotient)
            )
    return questions


def _enumerate_all(
    config: PracticeConfig, rng: random.Random
) -> list[Question]:
    """穷举当前约束（级别 1）下全部合法表达式，作为兜底候选。

    仅对操作数固定的简单类别实施；混合运算候选空间为指数级，
    放宽采样已能覆盖小范围空间，直接返回空列表。多目模式
    （``operand_count`` 非 0/2）下穷举仅覆盖两目组合，同样
    返回空列表。数值范围过大导致候选格数超出
    :data:`_MAX_ENUM_CELLS` 时同样跳过穷举（此时采样必然充足）。
    返回前随机洗牌，保证补题分布均匀。
    """
    category = config.category
    if (
        category is OperationCategory.MIXED
        or config.operand_count not in (0, 2)
        or (config.range_n + 1) ** 2 > _MAX_ENUM_CELLS
    ):
        return []
    if category is OperationCategory.ADD:
        candidates = _enumerate_add(config)
    elif category is OperationCategory.SUB:
        candidates = _enumerate_sub(config)
    elif category is OperationCategory.MUL:
        candidates = _enumerate_mul(config)
    elif category is OperationCategory.DIV:
        candidates = _enumerate_div(config)
    elif category is OperationCategory.ADD_SUB:
        candidates = _enumerate_add(config) + _enumerate_sub(config)
    else:
        candidates = _enumerate_mul(config) + _enumerate_div(config)
    rng.shuffle(candidates)
    return candidates


def generate_questions(config: PracticeConfig) -> list[Question]:
    """按配置批量生成口算题目，保证互不重复。

    以表达式文本判重，产出至多 ``config.count`` 道题目。生成按
    放宽级别逐级进行：级别 0 尽量避免 ``a+0``、``a-0``、``a-a``、
    ``0×a``、``a÷1`` 等平凡题目；级别 1 放开这些限制；候选空间
    仍不足时穷举全部合法组合去重补齐。可用组合总数少于请求数
    量时返回全部可用组合。各级均设尝试次数与停滞上限，不会
    死循环。

    ``config.operand_count`` 控制算式目数：0（默认两个数，混合
    保持原随机 2–3 个运算符）、2~10（固定目数）、-1（每题在
    2/3/4 中等概率随机）。空白统一用 ``( )`` 占位：求结果时留在
    等号右侧，``"middle"`` 隐藏任一操作数，``"any"`` 两种随机；
    判重以最终显示文本为准。
    """
    rng = random.Random(config.seed)
    questions: list[Question] = []
    seen: set[str] = set()
    generator2 = _CATEGORY_GENERATORS[config.category]
    generator3 = _CATEGORY_GENERATORS3[config.category]
    generator_n = _CATEGORY_GENERATORS_N[config.category]
    if config.operand_count == 3:
        generator = generator3
    elif config.operand_count >= 4:
        generator = generator_n
    elif config.operand_count == OPERAND_COUNT_RANDOM:

        def generator(
            rng: random.Random, cfg: PracticeConfig, level: int
        ) -> Question | None:
            operand_count = rng.choice((2, 3, 4))
            sub_cfg = replace(cfg, operand_count=operand_count)
            if operand_count == 2:
                return generator2(rng, sub_cfg, level)
            if operand_count == 3:
                return generator3(rng, sub_cfg, level)
            return generator_n(rng, sub_cfg, level)

    else:
        generator = generator2
    max_attempts = (
        _BATCH_ATTEMPTS_BASE + _BATCH_ATTEMPTS_PER_QUESTION * config.count
    )
    for level in (0, 1):
        stall = 0
        attempts = 0
        while len(questions) < config.count and attempts < max_attempts:
            attempts += 1
            question = generator(rng, config, level)
            if question is None:
                stall += 1
                if stall >= _LEVEL_STALL_LIMIT:
                    break
                continue
            question = _blank_question(question, rng, config.blank_position)
            if question.expression in seen:
                stall += 1
                if stall >= _LEVEL_STALL_LIMIT:
                    break
                continue
            stall = 0
            seen.add(question.expression)
            questions.append(question)
        if len(questions) >= config.count:
            return questions
    for question in _enumerate_all(config, rng):
        if len(questions) >= config.count:
            break
        question = _blank_question(question, rng, config.blank_position)
        if question.expression in seen:
            continue
        seen.add(question.expression)
        questions.append(question)
    return questions
