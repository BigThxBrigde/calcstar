"""SQLite 数据库连接与建表模块。

data 层仅依赖标准库（sqlite3），通过纯 dict/tuple 与上层传递数据，
不 import domain/services/bridge/desktop。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union

_DBPath = Union[str, Path]


def connect(db_path: _DBPath) -> sqlite3.Connection:
    """建立 SQLite 数据库连接。

    Args:
        db_path: 数据库文件路径，Path 或 str 均可（``:memory:`` 亦可）。

    Returns:
        已启用外键约束的 sqlite3.Connection，行以 dict 风格的
        sqlite3.Row 返回，便于按键名取值。
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    # WAL 提升并发读写性能；内存数据库不支持，忽略失败即可。
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    return conn


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, ddl: str
) -> None:
    """为已有表幂等补齐缺失列（旧库迁移）。

    Args:
        conn: 数据库连接；
        table: 表名；
        column: 列名；
        ddl: ``ALTER TABLE`` 使用的列定义（含默认值）。
    """
    cols = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db(conn: sqlite3.Connection) -> None:
    """初始化数据库表结构（幂等，可重复调用）。

    创建三张表——练习记录主表 sessions、题目明细表 questions
    以及错题本 wrong_book。

    练习记录主表 sessions：

    - id: 主键自增；
    - category: 题型类别（如 add/sub/mul/div/mixed）；
    - range_n: 取数范围（如 20/100）；
    - count: 本局出题数量；
    - duration_minutes: 限时分钟数，NULL 表示不限时；
    - allow_negative / include_parentheses / per_page: 练习选项；
    - blank_position / operand_count: 算式形式（填空位置与算式目数，
      后增列，旧库经幂等迁移补齐，历史行为默认值）；
    - started_at: 开始时间（ISO 格式文本）；
    - finished_at / duration_seconds / correct_count / total_count /
      score: 提交后写入的作答统计，score 为百分制；
    - correction_round: 已完成的订正轮数，默认 0；
    - status: 会话状态（in_progress/submitted/passed），默认 in_progress；
    - passed: 是否达标（1/0），默认 0。

    题目明细表 questions（随会话级联删除）：

    - session_id: 外键指向 sessions(id)，ON DELETE CASCADE；
    - seq: 题目在会话内的序号，从 0 开始，与会话联合唯一；
    - expression / answer: 题目表达式与正确答案；
    - user_answer: 用户作答，NULL 表示未作答；
    - is_correct: 判分结果（1/0），NULL 表示未判分；
    - correction_count: 该题答错的次数（订正中再错累计），默认 0。

    错题本 wrong_book（按表达式+答案去重聚合）：

    - expression / answer: 联合唯一键，同一题只存一条记录；
    - category / range_n: 最近一次做错时的题型与范围；
    - wrong_count: 累计做错次数，默认 1；
    - last_wrong_at: 最近一次做错时间（ISO 格式文本）。
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            seq INTEGER NOT NULL,
            expression TEXT NOT NULL,
            answer INTEGER NOT NULL,
            user_answer INTEGER,
            is_correct INTEGER,
            correction_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(session_id, seq),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
                ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wrong_book (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expression TEXT NOT NULL,
            answer INTEGER NOT NULL,
            category TEXT,
            range_n INTEGER,
            wrong_count INTEGER NOT NULL DEFAULT 1,
            last_wrong_at TEXT,
            UNIQUE(expression, answer)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            range_n INTEGER NOT NULL,
            count INTEGER NOT NULL,
            duration_minutes INTEGER,
            allow_negative INTEGER NOT NULL,
            include_parentheses INTEGER NOT NULL,
            per_page INTEGER NOT NULL,
            blank_position TEXT NOT NULL DEFAULT 'last',
            operand_count INTEGER NOT NULL DEFAULT 0,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            duration_seconds REAL,
            correct_count INTEGER,
            total_count INTEGER,
            score INTEGER,
            correction_round INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'in_progress',
            passed INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    # 旧库幂等迁移：sessions 表补齐后增的算式形式两列（有默认值，历史行安全）。
    _ensure_column(
        conn,
        "sessions",
        "blank_position",
        "blank_position TEXT NOT NULL DEFAULT 'last'",
    )
    _ensure_column(
        conn,
        "sessions",
        "operand_count",
        "operand_count INTEGER NOT NULL DEFAULT 0",
    )
    conn.commit()
