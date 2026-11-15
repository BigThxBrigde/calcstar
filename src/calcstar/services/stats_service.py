"""统计查询应用服务层（services）。

组合 data 层仓库函数，提供历史记录分页、会话明细与错题本查询
等只读统计 API，供桥接层调用。

分层规则：services → domain/data。
"""

from __future__ import annotations

from typing import Optional, Union

from calcstar.config import get_db_path
from calcstar.data.database import connect, init_db
from calcstar.data.repositories import (
    clear_history,
    get_session_detail,
    list_history,
    list_wrong_book,
)
from calcstar.services.practice_service import SessionNotFoundError

_DBPath = Union[str, "os.PathLike[str]"]


class StatsService:
    """统计查询应用服务：历史、明细与错题本。"""

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

    def list_history(self, page: int = 1, page_size: int = 20) -> dict:
        """分页列出历史练习会话（按开始时间倒序）。

        Args:
            page: 页码，从 1 起；
            page_size: 每页条数。

        Returns:
            {"items": 会话字典列表, "total": 总条数, "page": 页码,
            "page_size": 每页条数}。
        """
        return list_history(self._conn, page=page, page_size=page_size)

    def get_session_detail(self, session_id: int) -> dict:
        """获取会话详情（会话字段 + 按 seq 升序的题目列表）。

        Args:
            session_id: 会话 id。

        Returns:
            会话字典（附加 "questions": 题目字典列表）。

        Raises:
            SessionNotFoundError: 会话不存在。
        """
        detail = get_session_detail(self._conn, session_id)
        if detail is None:
            raise SessionNotFoundError(f"练习会话不存在：session_id={session_id}")
        return detail

    def clear_history(self) -> int:
        """清空全部练习历史（会话与逐题明细），错题本保留。

        Returns:
            被删除的会话数量。
        """
        return clear_history(self._conn)

    def list_wrong_book(
        self,
        category: Optional[str] = None,
        order_by: str = "wrong_count",
    ) -> list[dict]:
        """列出错题本条目。

        Args:
            category: 类别筛选，None 表示全部类别；
            order_by: 排序字段，"wrong_count"（默认，按错误次数倒序）
                或 "last_wrong_at"（按最近做错时间倒序）。

        Returns:
            错题字典列表，按指定字段倒序排列。
        """
        return list_wrong_book(self._conn, category=category, order_by=order_by)
