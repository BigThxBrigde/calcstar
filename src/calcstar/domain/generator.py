"""口算题目生成器（domain 层）。

根据 :class:`PracticeConfig` 生成各类别的口算题目：

- 内部使用独立播种的 :class:`random.Random`，同一种子生成结果
  完全可复现；
- 严格满足各范畴的范围约束（操作数、结果均落在 ``[0, N]``，
  除法整除、乘法积不超界等），并尽量避免 ``a+0``、``a-0``、
  ``a-a``、``0×a``、``a÷1`` 这类过于简单的题目（空间不足时自动
  放宽）；
- 纯逻辑实现，不做任何 IO。

混合运算（mixed）类别由后续任务支持。
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
            b = rng.randint(1, n)
            a = rng.randint(0, n)
            if a == b:
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


#: 类别 -> 单题生成函数
_CATEGORY_GENERATORS = {
    OperationCategory.ADD: _generate_add,
    OperationCategory.SUB: _generate_sub,
    OperationCategory.ADD_SUB: _generate_add_sub,
    OperationCategory.MUL: _generate_mul,
    OperationCategory.DIV: _generate_div,
    OperationCategory.MUL_DIV: _generate_mul_div,
}


def _generate_one(rng: random.Random, config: PracticeConfig) -> Question:
    """按放宽级别从高到低（0 -> 1）生成一道题，全部失败返回 None。

    级别 0 的约束更严格（避免零因子、``a÷1`` 等平凡题目），
    级别 1 放开这些限制，保证小范围下仍能出题。
    """
    generator = _CATEGORY_GENERATORS[config.category]
    for level in (0, 1):
        for _ in range(_MAX_ATTEMPTS):
            question = generator(rng, config, level)
            if question is not None:
                return question
    return None


def generate_questions(config: PracticeConfig) -> list[Question]:
    """按配置批量生成口算题目。

    返回恰好 ``config.count`` 道题目（除法/乘法等在小范围下
    由放宽级别保证可出题）。传入 MIXED 类别时暂不支持。
    """
    rng = random.Random(config.seed)
    if config.category is OperationCategory.MIXED:
        raise NotImplementedError("混合运算（mixed）类别将在后续任务中支持")
    questions: list[Question] = []
    for _ in range(config.count):
        question = _generate_one(rng, config)
        if question is None:
            break
        questions.append(question)
    return questions
