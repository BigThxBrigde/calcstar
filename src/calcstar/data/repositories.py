"""练习记录仓库层：基于 database.py 的三张表提供函数式数据访问 API。

每个函数首参均为 sqlite3.Connection（由 connect() 创建、init_db() 初始化），
数据以纯 dict/tuple 传入传出，供 services/bridge 层组合调用。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional


def _now() -> str:
    """返回当前本地时间的 ISO 格式字符串（秒级精度）。"""
    return datetime.now().isoformat(timespec="seconds")


def create_session(
    conn: sqlite3.Connection,
    category: str,
    range_n: int,
    count: int,
    duration_minutes: Optional[int],
    allow_negative: bool,
    include_parentheses: bool,
    per_page: int,
    started_at: Optional[str] = None,
) -> int:
    """创建一局练习会话，返回会话 id。

    Args:
        conn: 数据库连接；
        category: 题型类别；
        range_n: 取数范围；
        count: 出题数量；
        duration_minutes: 限时分钟数，None 表示不限时；
        allow_negative: 是否允许负数中间结果；
        include_parentheses: 是否包含括号；
        per_page: 每页题数；
        started_at: 开始时间（ISO 文本），缺省取当前时间。

    Returns:
        新会话的 session_id（自增主键）。
    """
    cur = conn.execute(
        """
        INSERT INTO sessions (
            category, range_n, count, duration_minutes,
            allow_negative, include_parentheses, per_page, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            category,
            range_n,
            count,
            duration_minutes,
            int(bool(allow_negative)),
            int(bool(include_parentheses)),
            per_page,
            started_at if started_at is not None else _now(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def save_questions(
    conn: sqlite3.Connection,
    session_id: int,
    questions: list[dict],
) -> None:
    """批量写入一局练习的题目明细。

    Args:
        conn: 数据库连接；
        session_id: 所属会话 id；
        questions: 题目字典列表，每项至少含 seq（题内序号，从 0 起）、
            expression（表达式文本）、answer（正确答案整数）。
    """
    conn.executemany(
        """
        INSERT INTO questions (session_id, seq, expression, answer)
        VALUES (?, ?, ?, ?)
        """,
        [
            (session_id, int(q["seq"]), q["expression"], int(q["answer"]))
            for q in questions
        ],
    )
    conn.commit()


def submit_answers(
    conn: sqlite3.Connection,
    session_id: int,
    answers: dict[int, Optional[int]],
    graded: list[dict],
    duration_seconds: float,
    finished_at: Optional[str] = None,
) -> None:
    """提交一局练习的作答：写判分、更新会话统计、聚合错题本。

    Args:
        conn: 数据库连接；
        session_id: 会话 id；
        answers: {seq: 用户答案或 None(未作答)}；
        graded: 判分结果列表，每项含 seq/expression/answer/
            user_answer/is_correct（is_correct 为 1/0）；
        duration_seconds: 本局用时秒数；
        finished_at: 完成时间（ISO 文本），缺省取当前时间。

    行为：
        1. 按 seq 更新 questions 表的 user_answer / is_correct；
        2. 更新 sessions 的 correct_count / total_count / duration_seconds /
           finished_at / score（百分制四舍五入）/ status='submitted' /
           passed（全对为 1，否则 0）；
        3. 对答错的题聚合写 wrong_book：(expression, answer) 已存在时
           wrong_count+1 并刷新 last_wrong_at / category / range_n，
           否则插入新记录 wrong_count=1。
    """
    if finished_at is None:
        finished_at = _now()

    graded_by_seq = {g["seq"]: g for g in graded}
    total = len(graded)
    correct = sum(1 for g in graded if g["is_correct"])

    # 1. 逐题写入作答与判分。
    conn.executemany(
        """
        UPDATE questions
        SET user_answer = ?, is_correct = ?
        WHERE session_id = ? AND seq = ?
        """,
        [
            (g["user_answer"], int(g["is_correct"]), session_id, g["seq"])
            for g in graded
        ],
    )

    # 2. 更新会话统计（answers 中未出现在 graded 的键同样按未判分处理）。
    conn.execute(
        """
        UPDATE sessions
        SET correct_count = ?, total_count = ?, duration_seconds = ?,
            finished_at = ?, score = ?, status = 'submitted', passed = ?
        WHERE id = ?
        """,
        (
            correct,
            total,
            duration_seconds,
            finished_at,
            round(correct / total * 100) if total else 0,
            1 if total > 0 and correct == total else 0,
            session_id,
        ),
    )

    # 3. 聚合错题本。
    session = conn.execute(
        "SELECT category, range_n FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    wrong_items = [g for g in graded if not g["is_correct"]]
    if wrong_items and session is not None:
        category = session["category"]
        range_n = session["range_n"]
        for g in wrong_items:
            conn.execute(
                """
                INSERT INTO wrong_book (
                    expression, answer, category, range_n,
                    wrong_count, last_wrong_at
                )
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(expression, answer) DO UPDATE SET
                    wrong_count = wrong_count + 1,
                    last_wrong_at = excluded.last_wrong_at,
                    category = excluded.category,
                    range_n = excluded.range_n
                """,
                (
                    g["expression"],
                    g["answer"],
                    category,
                    range_n,
                    finished_at,
                ),
            )

    conn.commit()


def update_correction(
    conn: sqlite3.Connection,
    session_id: int,
    seq: int,
    user_answer: Optional[int],
    is_correct: bool,
) -> None:
    """记录单题订正结果。

    更新该题的 user_answer / is_correct；答错时该题 correction_count+1
    并将错题本对应条目 wrong_count+1（无则插入）；答对时不累计错误。

    Args:
        conn: 数据库连接；
        session_id: 会话 id；
        seq: 题目序号；
        user_answer: 订正时填写的答案（可为 None 表示未作答）；
        is_correct: 订正判分结果。
    """
    row = conn.execute(
        """
        SELECT expression, answer FROM questions
        WHERE session_id = ? AND seq = ?
        """,
        (session_id, seq),
    ).fetchone()
    if row is None:
        return

    conn.execute(
        """
        UPDATE questions
        SET user_answer = ?, is_correct = ?,
            correction_count = correction_count + ?
        WHERE session_id = ? AND seq = ?
        """,
        (
            user_answer,
            int(is_correct),
            0 if is_correct else 1,
            session_id,
            seq,
        ),
    )

    if not is_correct:
        session = conn.execute(
            "SELECT category, range_n FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO wrong_book (
                expression, answer, category, range_n,
                wrong_count, last_wrong_at
            )
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(expression, answer) DO UPDATE SET
                wrong_count = wrong_count + 1,
                last_wrong_at = excluded.last_wrong_at,
                category = excluded.category,
                range_n = excluded.range_n
            """,
            (
                row["expression"],
                row["answer"],
                session["category"] if session else None,
                session["range_n"] if session else None,
                _now(),
            ),
        )

    conn.commit()


def mark_session_passed(conn: sqlite3.Connection, session_id: int) -> None:
    """将会话标记为达标：订正轮数 +1、状态置 passed、passed 置 1。

    Args:
        conn: 数据库连接；
        session_id: 会话 id。
    """
    conn.execute(
        """
        UPDATE sessions
        SET correction_round = correction_round + 1,
            status = 'passed',
            passed = 1
        WHERE id = ?
        """,
        (session_id,),
    )
    conn.commit()


def increment_correction_round(conn: sqlite3.Connection, session_id: int) -> None:
    """仅递增会话的订正轮数（correction_round +1），不改状态。

    Args:
        conn: 数据库连接；
        session_id: 会话 id。
    """
    conn.execute(
        """
        UPDATE sessions
        SET correction_round = correction_round + 1
        WHERE id = ?
        """,
        (session_id,),
    )
    conn.commit()


def list_history(
    conn: sqlite3.Connection,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """分页列出历史练习会话（按开始时间倒序）。

    Args:
        conn: 数据库连接；
        page: 页码，从 1 起；
        page_size: 每页条数。

    Returns:
        {"items": [session dict, ...], "total": 总条数,
         "page": 页码, "page_size": 每页条数}。
    """
    page = max(1, int(page))
    page_size = max(1, int(page_size))
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM sessions"
    ).fetchone()["n"]
    rows = conn.execute(
        """
        SELECT * FROM sessions
        ORDER BY started_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, (page - 1) * page_size),
    ).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_session_detail(conn: sqlite3.Connection, session_id: int) -> Optional[dict]:
    """获取会话详情：会话字段 + 按 seq 升序排列的题目列表。

    Args:
        conn: 数据库连接；
        session_id: 会话 id。

    Returns:
        会话 dict（附加 "questions": 题目 dict 列表），会话不存在时返回 None。
    """
    row = conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if row is None:
        return None
    detail = dict(row)
    qrows = conn.execute(
        """
        SELECT * FROM questions
        WHERE session_id = ?
        ORDER BY seq ASC
        """,
        (session_id,),
    ).fetchall()
    detail["questions"] = [dict(q) for q in qrows]
    return detail


def list_wrong_book(
    conn: sqlite3.Connection,
    category: Optional[str] = None,
    order_by: str = "wrong_count",
) -> list[dict]:
    """列出错题本条目。

    Args:
        conn: 数据库连接；
        category: 类别筛选，None 表示全部类别；
        order_by: 排序字段，支持 "wrong_count"（按错误次数倒序）与
            "last_wrong_at"（按最近做错时间倒序），其他值按 wrong_count 处理。

    Returns:
        错题 dict 列表，按指定字段倒序排列。
    """
    column = "last_wrong_at" if order_by == "last_wrong_at" else "wrong_count"
    sql = "SELECT * FROM wrong_book"
    params: list = []
    if category is not None:
        sql += " WHERE category = ?"
        params.append(category)
    sql += f" ORDER BY {column} DESC, id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def clear_history(conn: sqlite3.Connection) -> int:
    """清空全部练习历史（sessions 及随会话级联的 questions 明细）。

    错题本（wrong_book）为独立聚合表，不在清空范围内。

    Args:
        conn: 数据库连接。

    Returns:
        被删除的会话数量。
    """
    deleted = int(
        conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    )
    # questions 表对 sessions 有 ON DELETE CASCADE，但 SQLite 级联
    # 依赖外键开关，显式删除更稳妥（幂等）。
    conn.execute("DELETE FROM questions")
    conn.execute("DELETE FROM sessions")
    conn.commit()
    return deleted
