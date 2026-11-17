"""口算练习应用服务层（services）。

组合 domain 层（生成/判分）与 data 层（仓库持久化），为桥接层提供
面向用例的完整业务 API：创建练习、提交作答、订正流转。
可 import domain 与 data 两层；bridge 层之外不依赖任何 UI。

分层规则：services → domain/data。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional, Union

from calcstar.config import (
    DEFAULT_COUNT,
    DEFAULT_PER_PAGE,
    DEFAULT_RANGE,
    MAX_COUNT,
    MIN_COUNT,
    OPERAND_COUNT_RANDOM,
    OperationCategory,
    get_db_path,
    validate_params,
)
from calcstar.data.database import connect, init_db
from calcstar.data.repositories import (
    create_session,
    get_session_detail,
    increment_correction_round,
    list_wrong_book,
    mark_session_passed,
    save_questions,
    submit_answers,
    update_correction,
)
from calcstar.domain.generator import generate_questions
from calcstar.domain.grading import grade_answers
from calcstar.domain.models import PracticeConfig, Question

_DBPath = Union[str, Path]


class InvalidParamsError(ValueError):
    """练习参数非法异常。

    属性:
        errors: 参数校验的错误信息列表（每条对应一处不合法项）。
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("；".join(self.errors))


class SessionNotFoundError(ValueError):
    """指定练习会话不存在的异常。"""


class PracticeService:
    """口算练习应用服务：建卷、判分落库与订正流转。

    持有一个 SQLite 连接（构造时初始化表结构），所有方法基于该
    连接读写；线程安全性由调用方保证（Qt 桥接为单线程调用）。
    """

    def __init__(self, db_path: Optional[_DBPath] = None) -> None:
        """初始化服务并打开数据库连接。

        Args:
            db_path: 数据库文件路径；None 时使用 config.get_db_path()
                （环境变量 CALCSTAR_DB 或用户数据目录）。
        """
        if db_path is None:
            db_path = get_db_path()
        self._conn = connect(db_path)
        init_db(self._conn)

    def create_practice(self, params: dict) -> dict:
        """创建一局口算练习：校验参数、生成题目并落库。

        Args:
            params: 参数字典，键为 category(str)/range_n/count/
                duration_minutes(None 表示不限时)/allow_negative/
                include_parentheses/per_page/blank_position("last"|
                "any")/operand_count(0|2|3|"random")。

        Returns:
            会话摘要字典：

            - session_id: 会话 id；
            - questions: [{"seq", "expression"}, ...]（不含答案）；
            - total_count: 实际出题数；
            - per_page: 每页题数；
            - total_pages: 总页数（向上取整）；
            - duration_seconds: 限时秒数（不限时为 None）；
            - category / range_n: 本次练习的类别与取数范围。

        Raises:
            InvalidParamsError: 参数校验失败（errors 含全部错误项）。
        """
        category = params.get("category")
        range_n = params.get("range_n", DEFAULT_RANGE)
        count = params.get("count", DEFAULT_COUNT)
        duration_minutes = params.get("duration_minutes")
        allow_negative = bool(params.get("allow_negative", False))
        include_parentheses = bool(params.get("include_parentheses", False))
        per_page = params.get("per_page", DEFAULT_PER_PAGE)
        blank_position = params.get("blank_position", "last")
        raw_operand_count = params.get("operand_count", 0)
        if raw_operand_count == "random":
            operand_count = OPERAND_COUNT_RANDOM
        else:
            operand_count = int(raw_operand_count)

        errors = validate_params(
            category,
            range_n,
            count,
            duration_minutes,
            per_page,
            blank_position=blank_position,
            operand_count=operand_count,
        )
        if errors:
            raise InvalidParamsError(errors)

        config = PracticeConfig(
            category=OperationCategory(category),
            range_n=range_n,
            count=count,
            duration_minutes=duration_minutes,
            allow_negative=allow_negative,
            include_parentheses=include_parentheses,
            per_page=per_page,
            blank_position=blank_position,
            operand_count=operand_count,
        )
        questions = generate_questions(config)
        question_rows = [
            {
                "seq": index,
                "expression": question.expression,
                "answer": question.answer,
            }
            for index, question in enumerate(questions)
        ]

        session_id = create_session(
            self._conn,
            category=category,
            range_n=range_n,
            count=count,
            duration_minutes=duration_minutes,
            allow_negative=allow_negative,
            include_parentheses=include_parentheses,
            per_page=per_page,
            blank_position=blank_position,
            operand_count=operand_count,
        )
        save_questions(self._conn, session_id, question_rows)

        return self._build_practice_result(
            session_id, question_rows, per_page, duration_minutes, category, range_n
        )

    @staticmethod
    def _build_practice_result(
        session_id: int,
        question_rows: list[dict],
        per_page: int,
        duration_minutes: Optional[int],
        category: str,
        range_n: int,
        source: Optional[str] = None,
    ) -> dict:
        """组装创建练习的统一返回结构（questions 不含答案）。

        source 非 None 时附加来源标记（如 "wrong_book"）。
        """
        total_count = len(question_rows)
        result = {
            "session_id": session_id,
            "questions": [
                {"seq": row["seq"], "expression": row["expression"]}
                for row in question_rows
            ],
            "total_count": total_count,
            "per_page": per_page,
            "total_pages": math.ceil(total_count / per_page) if total_count else 0,
            "duration_seconds": (
                None if duration_minutes is None else duration_minutes * 60
            ),
            "category": category,
            "range_n": range_n,
        }
        if source is not None:
            result["source"] = source
        return result

    def submit_practice(
        self,
        session_id: int,
        answers: dict[int, Optional[int]],
        duration_seconds: float = 0.0,
    ) -> dict:
        """提交一局练习的作答：复用 domain 判分并落库。

        从库中取回题目重建 :class:`Question`（判分仅需 expression/
        answer，operands/operators 以空元组占位），按题号比对后写入
        questions/sessions 并聚合错题本。

        Args:
            session_id: 会话 id；
            answers: {seq: 用户答案或 None(未作答)}，缺失键按未作答计；
            duration_seconds: 本局用时秒数（超时提交照常落库）。

        Returns:
            {"score": 百分制得分, "correct_count": 答对数,
             "total_count": 总题数, "passed": 是否全对,
             "wrong_answers": [{"seq", "expression", "answer",
             "user_answer"}, ...]}。

        Raises:
            SessionNotFoundError: 会话不存在。
        """
        detail = get_session_detail(self._conn, session_id)
        if detail is None:
            raise SessionNotFoundError(f"练习会话不存在：session_id={session_id}")

        questions = [
            Question(
                expression=row["expression"],
                answer=int(row["answer"]),
                operands=(),
                operators=(),
            )
            for row in detail["questions"]
        ]
        normalized = {int(seq): answer for seq, answer in (answers or {}).items()}

        graded_result = grade_answers(questions, normalized)
        graded = [
            {
                "seq": record.seq,
                "expression": record.expression,
                "answer": record.answer,
                "user_answer": record.user_answer,
                "is_correct": record.is_correct,
            }
            for record in graded_result.results
        ]
        submit_answers(self._conn, session_id, normalized, graded, duration_seconds)

        return {
            "score": graded_result.score,
            "correct_count": graded_result.correct_count,
            "total_count": graded_result.total_count,
            "passed": (
                graded_result.total_count > 0
                and graded_result.correct_count == graded_result.total_count
            ),
            "wrong_answers": [
                {
                    "seq": record.seq,
                    "expression": record.expression,
                    "answer": record.answer,
                    "user_answer": record.user_answer,
                }
                for record in graded_result.results
                if not record.is_correct
            ],
        }

    def submit_correction(
        self, session_id: int, corrections: dict[int, int]
    ) -> dict:
        """提交一轮订正：逐题判分落库并驱动订正轮次与达标状态。

        轮次计数规则（与 repositories.mark_session_passed 的语义协调，
        避免轮次重复 +1）：

        - 本轮存在答错的题：仅逐题落库（update_correction 内部对答错
          题累计 correction_count 并累加错题本），不计轮次、不做达标
          判定；
        - 本轮全部答对且整局仍有错题：correction_round +1
          （increment_correction_round）；
        - 本轮处理后整局全部题目 is_correct=1：mark_session_passed
          （其内部已含 correction_round +1 与 status='passed'，故本轮
          不再另行 +1，该 +1 即最后一轮的轮次计数）。

        Args:
            session_id: 会话 id；
            corrections: {seq: 订正答案}；未知题号跳过（与 data 层
                容错语义一致）。

        Returns:
            {"all_correct": 整局是否已全部答对, "passed": 会话是否达标,
             "wrong_answers": 仍错的题列表（含 seq/expression/answer/
             user_answer）, "correction_round": 当前订正轮数}。

        Raises:
            SessionNotFoundError: 会话不存在。
        """
        detail = get_session_detail(self._conn, session_id)
        if detail is None:
            raise SessionNotFoundError(f"练习会话不存在：session_id={session_id}")

        questions_by_seq = {row["seq"]: row for row in detail["questions"]}
        any_wrong_this_round = False
        for raw_seq, user_answer in (corrections or {}).items():
            seq = int(raw_seq)
            row = questions_by_seq.get(seq)
            if row is None:
                continue
            is_correct = user_answer == int(row["answer"])
            update_correction(self._conn, session_id, seq, user_answer, is_correct)
            if not is_correct:
                any_wrong_this_round = True

        if corrections:
            latest = get_session_detail(self._conn, session_id)
            all_correct_now = bool(latest["questions"]) and all(
                row["is_correct"] == 1 for row in latest["questions"]
            )
            if all_correct_now:
                mark_session_passed(self._conn, session_id)
            elif not any_wrong_this_round:
                increment_correction_round(self._conn, session_id)

        detail = get_session_detail(self._conn, session_id)
        wrong_answers = [
            {
                "seq": row["seq"],
                "expression": row["expression"],
                "answer": row["answer"],
                "user_answer": row["user_answer"],
            }
            for row in detail["questions"]
            if row["is_correct"] != 1
        ]
        return {
            "all_correct": not wrong_answers and bool(detail["questions"]),
            "passed": bool(detail["passed"]),
            "wrong_answers": wrong_answers,
            "correction_round": detail["correction_round"],
        }

    def create_practice_from_wrong_book(self, params: dict) -> dict:
        """从错题本创建针对性练习（直接采用错题，不走随机生成器）。

        取错题本条目（可按 category 筛选，按 order 默认错误次数倒序）
        截取前 count 条作为新练习的题目，expression/answer 来自错题
        本；会话的 category/range_n 优先取 params 指定值，否则取第一
        条错题记录的值。

        Args:
            params: category(可选类别筛选)/count(数量上限，缺省取错题
                全部，超过 MAX_COUNT 截断)/range_n(可选，覆盖取数范围)/
                duration_minutes/allow_negative/include_parentheses/
                per_page，后四项语义同 create_practice。

        Returns:
            结构同 create_practice，另附 "source": "wrong_book"。

        Raises:
            InvalidParamsError: 按筛选条件错题本为空，或 count/
                duration_minutes/per_page/range_n 不合法。
        """
        category = params.get("category")
        entries = list_wrong_book(self._conn, category=category)
        if not entries:
            raise InvalidParamsError(["错题本中没有符合条件的错题，无法生成练习"])

        count = params.get("count")
        if count is None:
            count = min(len(entries), MAX_COUNT)
        else:
            count = int(count)
            if not MIN_COUNT <= count <= MAX_COUNT:
                raise InvalidParamsError(
                    [f"题目数量超出限制：{count}（应在 {MIN_COUNT}~{MAX_COUNT} 之间）"]
                )
        selected = entries[:count]

        range_n = params.get("range_n")
        if range_n is None:
            range_n = selected[0]["range_n"]
            if range_n is None:
                range_n = DEFAULT_RANGE
        duration_minutes = params.get("duration_minutes")
        allow_negative = bool(params.get("allow_negative", False))
        include_parentheses = bool(params.get("include_parentheses", False))
        per_page = params.get("per_page", DEFAULT_PER_PAGE)

        session_category = (
            category
            if category is not None
            else (selected[0]["category"] or OperationCategory.ADD.value)
        )
        errors = validate_params(
            session_category, range_n, len(selected), duration_minutes, per_page
        )
        if errors:
            raise InvalidParamsError(errors)

        question_rows = [
            {
                "seq": index,
                "expression": entry["expression"],
                "answer": int(entry["answer"]),
            }
            for index, entry in enumerate(selected)
        ]
        session_id = create_session(
            self._conn,
            category=session_category,
            range_n=range_n,
            count=len(selected),
            duration_minutes=duration_minutes,
            allow_negative=allow_negative,
            include_parentheses=include_parentheses,
            per_page=per_page,
        )
        save_questions(self._conn, session_id, question_rows)

        return self._build_practice_result(
            session_id,
            question_rows,
            per_page,
            duration_minutes,
            session_category,
            range_n,
            source="wrong_book",
        )
