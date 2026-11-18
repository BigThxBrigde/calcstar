"""练习领域模型。

定义口算题目与练习配置的纯数据结构，供生成、判分等
domain 层逻辑使用；本模块只包含数据定义，不含 IO 与业务规则。
"""

from __future__ import annotations

from dataclasses import dataclass

from calcstar.config import OperationCategory


@dataclass(frozen=True)
class Question:
    """一道口算题目。

    属性:
        expression: 题目显示文本，如 ``"3 + 5 = ( )"``；运算符使用
            显示符号 ``+``、``-``、``×``、``÷``。无论空在中间还是末尾，
            统一以括号记号 ``( )`` 占位，如 ``"3 + ( ) - 2 = 5"``。
        answer: 正确答案（整数）；填空求操作数时即为该操作数的值。
        operands: 按表达式中出现顺序排列的操作数元组。
        operators: 按表达式中出现顺序排列的运算符元组（显示符号）。
        blank_index: 填空位置；None 表示求结果（空白在等号右侧，
            以 ``( )`` 占位），否则为被隐藏操作数在 ``operands`` 中的下标。
        paren_pos: 混合运算括号组对应的运算符下标（``_build_tokens``
            的 ``paren_pos`` 参数）；无括号时为 None。
    """

    expression: str
    answer: int
    operands: tuple[int, ...]
    operators: tuple[str, ...]
    blank_index: int | None = None
    paren_pos: int | None = None


@dataclass(frozen=True)
class PracticeConfig:
    """一次口算练习的配置参数。

    属性:
        category: 运算类别。
        range_n: 数值范围上限 N，操作数与结果均受其约束。
        count: 题目数量。
        duration_minutes: 限时分钟数；None 表示不限时。
        allow_negative: 是否允许结果为负数（减法/混合运算）。
        include_parentheses: 混合运算是否允许出现一层括号。
        per_page: 每页展示的题目数量。
        seed: 随机种子；指定后生成结果完全可复现，便于测试。
        blank_position: 填空位置模式；``"last"`` 固定填等号右侧
            （求结果），``"any"`` 每题随机填结果或任一操作数。
        operand_count: 每题操作数个数；0 表示默认两个数（混合运算
            保持原随机 2–3 个运算符），2/3 表示固定目数，
            :data:`OPERAND_COUNT_RANDOM`（-1）表示每题随机 2 或 3。
    """

    category: OperationCategory
    range_n: int
    count: int
    duration_minutes: int | None
    allow_negative: bool = False
    include_parentheses: bool = False
    per_page: int = 10
    seed: int | None = None
    blank_position: str = "last"
    operand_count: int = 0
