"""口算练习判分逻辑（domain 层）。

按题目顺序比对用户答案与正确答案，产出逐题判分记录与
整次练习的汇总结果（正确数、总分百分制）。纯逻辑，不做 IO。
"""

from __future__ import annotations

from dataclasses import dataclass

from calcstar.domain.models import Question


@dataclass(frozen=True)
class AnswerRecord:
    """单题判分记录。

    属性:
        seq: 题号，从 0 开始。
        expression: 题目显示文本。
        answer: 正确答案。
        user_answer: 用户作答；None 表示未作答。
        is_correct: 是否答对（未作答按错误计）。
    """

    seq: int
    expression: str
    answer: int
    user_answer: int | None
    is_correct: bool


@dataclass(frozen=True)
class GradeResult:
    """一次练习的整体判分结果。

    属性:
        results: 按题号顺序排列的逐题判分记录。
        correct_count: 答对题数。
        total_count: 总题数。
        score: 百分制得分（四舍五入取整）。
    """

    results: tuple[AnswerRecord, ...]
    correct_count: int
    total_count: int
    score: int


def grade_answers(
    questions: list[Question], answers: dict[int, int | None]
) -> GradeResult:
    """按题号比对用户答案，生成判分结果。

    ``answers`` 以题号（从 0 开始）为键；缺失的键与值为 None 的
    键均视为未作答，按错误计。得分为 ``正确数 / 总数 × 100``
    四舍五入取整；题目列表为空时得分为 0。
    """
    records: list[AnswerRecord] = []
    for seq, question in enumerate(questions):
        user_answer = answers.get(seq)
        records.append(
            AnswerRecord(
                seq=seq,
                expression=question.expression,
                answer=question.answer,
                user_answer=user_answer,
                is_correct=(
                    user_answer is not None
                    and user_answer == question.answer
                ),
            )
        )
    total = len(records)
    correct = sum(record.is_correct for record in records)
    if total == 0:
        score = 0
    else:
        # 半舍入到整数：score = round(correct/total*100)，用整数
        # 运算实现四舍五入（half-up），避免浮点误差。
        score = (correct * 200 + total) // (total * 2)
    return GradeResult(
        results=tuple(records),
        correct_count=correct,
        total_count=total,
        score=score,
    )
