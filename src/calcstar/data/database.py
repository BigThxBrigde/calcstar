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


def init_db(conn: sqlite3.Connection) -> None:
    """初始化数据库表结构（幂等，可重复调用）。

    创建练习记录主表 sessions：

    - id: 主键自增；
    - category: 题型类别（如 add/sub/mul/div/mixed）；
    - range_n: 取数范围（如 20/100）；
    - count: 本局出题数量；
    - duration_minutes: 限时分钟数，NULL 表示不限时；
    - allow_negative / include_parentheses / per_page: 练习选项；
    - started_at: 开始时间（ISO 格式文本）；
    - finished_at / duration_seconds / correct_count / total_count /
      score: 提交后写入的作答统计，score 为百分制；
    - correction_round: 已完成的订正轮数，默认 0；
    - status: 会话状态（in_progress/submitted/passed），默认 in_progress；
    - passed: 是否达标（1/0），默认 0。
    """
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
    conn.commit()
