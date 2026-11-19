"""grading 模块单元测试。"""

from calcstar.domain.grading import grade_answers
from calcstar.domain.models import Question


def make_questions(count: int) -> list[Question]:
    """构造 count 道答案递增的固定题目。"""
    questions = []
    for seq in range(count):
        operand = seq + 1
        questions.append(
            Question(
                expression=f"{operand} + {operand} =",
                answer=operand * 2,
                operands=(operand, operand),
                operators=("+",),
            )
        )
    return questions


def test_all_correct():
    questions = make_questions(3)
    result = grade_answers(questions, {0: 2, 1: 4, 2: 6})
    assert result.total_count == 3
    assert result.correct_count == 3
    assert result.score == 100
    assert all(record.is_correct for record in result.results)


def test_unanswered_counted_wrong():
    questions = make_questions(3)
    # 完全未作答
    result = grade_answers(questions, {})
    assert result.correct_count == 0
    assert result.score == 0
    assert all(record.user_answer is None for record in result.results)
    # 显式提交 None 同样按错误计
    result = grade_answers(questions, {0: None, 1: None, 2: None})
    assert result.correct_count == 0
    assert result.score == 0


def test_partial_correct_score():
    questions = make_questions(4)
    result = grade_answers(questions, {0: 2, 1: 999, 2: None, 3: 999})
    assert result.correct_count == 1
    assert result.total_count == 4
    assert result.score == 25
    assert [
        record.is_correct for record in result.results] == [
        True,
        False,
        False,
        False]


def test_score_rounds_half_up():
    questions = make_questions(8)
    result = grade_answers(questions, {0: 2})
    # 1/8 = 12.5% -> 四舍五入为 13
    assert result.correct_count == 1
    assert result.score == 13


def test_record_fields():
    questions = make_questions(2)
    result = grade_answers(questions, {0: 2, 1: 5})
    first, second = result.results
    assert first.seq == 0
    assert first.expression == "1 + 1 ="
    assert first.answer == 2
    assert first.user_answer == 2
    assert first.is_correct is True
    assert second.seq == 1
    assert second.user_answer == 5
    assert second.is_correct is False
