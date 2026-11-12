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
    OperationCategory,
    get_db_path,
    validate_params,
)
from calcstar.data.database import connect, init_db
from calcstar.data.repositories import create_session, save_questions
from calcstar.domain.generator import generate_questions
from calcstar.domain.models import PracticeConfig

_DBPath = Union[str, Path]


class InvalidParamsError(ValueError):
    """练习参数非法异常。

    属性:
        errors: 参数校验的错误信息列表（每条对应一处不合法项）。
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("；".join(self.errors))


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
                include_parentheses/per_page。

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

        errors = validate_params(
            category, range_n, count, duration_minutes, per_page
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
        )
        save_questions(self._conn, session_id, question_rows)

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
        return result
