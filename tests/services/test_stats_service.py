"""tests/services：StatsService 单元测试（tmp_path 独立数据库）。"""

import pytest

from calcstar.services.practice_service import (
    PracticeService,
    SessionNotFoundError,
)
from calcstar.services.stats_service import (
    StatsService,
    WrongBookEntryNotFoundError,
)


@pytest.fixture()
def practice(tmp_path):
    """练习服务（写侧），与 stats 共用同一临时数据库文件。"""
    svc = PracticeService(tmp_path / "calcstar.db")
    yield svc
    svc._conn.close()


@pytest.fixture()
def stats(tmp_path):
    """统计服务（读侧）。"""
    svc = StatsService(tmp_path / "calcstar.db")
    yield svc
    svc._conn.close()


def _create(practice):
    """创建一局默认练习（5 题，加法，不限时）。"""
    return practice.create_practice({
        "category": "add", "range_n": 10, "count": 5,
        "duration_minutes": None, "per_page": 5,
    })


def _submit_with_wrong(practice, stats, session_id, wrong_seq=0):
    """提交某局作答并让指定题号答错（答案 +7），返回错题表达式。"""
    detail = stats.get_session_detail(session_id)
    answers = {q["seq"]: q["answer"] for q in detail["questions"]}
    wrong_expression = next(
        q["expression"] for q in detail["questions"] if q["seq"] == wrong_seq
    )
    answers[wrong_seq] = answers[wrong_seq] + 7
    practice.submit_practice(session_id, answers, 30.0)
    return wrong_expression


class TestListHistory:
    def test_paging_and_desc_order(self, practice, stats):
        """历史按开始时间倒序（同秒以 id 兜底）分页返回。"""
        ids = [_create(practice)["session_id"] for _ in range(3)]
        page1 = stats.list_history(page=1, page_size=2)
        assert page1["total"] == 3
        assert page1["page"] == 1
        assert page1["page_size"] == 2
        assert [item["id"] for item in page1["items"]] == [ids[2], ids[1]]
        page2 = stats.list_history(page=2, page_size=2)
        assert [item["id"] for item in page2["items"]] == [ids[0]]

    def test_default_page_params(self, practice, stats):
        """缺省 page/page_size 生效。"""
        _create(practice)
        history = stats.list_history()
        assert history["page"] == 1
        assert history["page_size"] == 20
        assert history["total"] == 1


class TestSessionDetail:
    def test_detail_fields(self, practice, stats):
        """明细含会话字段与按 seq 升序的题目（含正确答案）。"""
        result = practice.create_practice({
            "category": "sub", "range_n": 20, "count": 6,
            "duration_minutes": 10, "per_page": 5,
        })
        detail = stats.get_session_detail(result["session_id"])
        assert detail["category"] == "sub"
        assert detail["range_n"] == 20
        assert detail["duration_minutes"] == 10
        assert [q["seq"] for q in detail["questions"]] == list(range(6))
        assert "answer" in detail["questions"][0]

    def test_missing_session_raises(self, practice, stats):
        """不存在的会话抛 SessionNotFoundError。"""
        with pytest.raises(SessionNotFoundError):
            stats.get_session_detail(999)


class TestWrongBook:
    def test_aggregation_filter_and_orders(self, practice, stats):
        """错题聚合、类别筛选与 wrong_count / last_wrong_at 排序。"""
        # add 类错 1 题（wrong_count=1）
        add_session = _create(practice)["session_id"]
        add_expression = _submit_with_wrong(practice, stats, add_session, wrong_seq=0)

        # sub 类错 1 题后订正仍错（wrong_count=2）
        sub_session = practice.create_practice({
            "category": "sub", "range_n": 20, "count": 5,
            "duration_minutes": None, "per_page": 5,
        })["session_id"]
        detail = stats.get_session_detail(sub_session)
        answers = {q["seq"]: q["answer"] for q in detail["questions"]}
        sub_expression = detail["questions"][1]["expression"]
        answers[1] = answers[1] + 7
        practice.submit_practice(sub_session, answers, 30.0)
        practice.submit_correction(sub_session, {1: answers[1]})  # 仍错 → 累计 2 次

        rows = stats.list_wrong_book()
        assert [row["expression"] for row in rows] == [sub_expression, add_expression]
        assert rows[0]["wrong_count"] == 2
        assert rows[0]["category"] == "sub"

        rows = stats.list_wrong_book(category="add")
        assert [row["expression"] for row in rows] == [add_expression]
        assert stats.list_wrong_book(category="mul") == []

        rows = stats.list_wrong_book(order_by="last_wrong_at")
        assert [row["expression"] for row in rows] == [
            sub_expression,
            add_expression,
        ]

    def test_empty_wrong_book(self, practice, stats):
        """无错题时返回空列表。"""
        assert stats.list_wrong_book() == []

    def test_page_delete_and_clear(self, practice, stats):
        """服务层分页、单条删除（不存在报错）与清空错题本。"""
        session_id = _create(practice)["session_id"]
        _submit_with_wrong(practice, stats, session_id, wrong_seq=0)

        page = stats.list_wrong_book_page(page=1, page_size=5)
        assert page["total"] == 1 and page["page_size"] == 5
        assert len(page["items"]) == 1
        entry_id = page["items"][0]["id"]

        assert stats.delete_wrong_book_entry(entry_id) is True
        with pytest.raises(WrongBookEntryNotFoundError):
            stats.delete_wrong_book_entry(entry_id)
        assert stats.list_wrong_book() == []

        other = _create(practice)["session_id"]
        _submit_with_wrong(practice, stats, other, wrong_seq=0)
        assert stats.clear_wrong_book() == 1
        assert stats.list_wrong_book() == []
        assert stats.list_history(page=1, page_size=10)["total"] == 2
