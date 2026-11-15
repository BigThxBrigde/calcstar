"""tests/data 仓库层测试：基于 tmp_path 独立数据库覆盖三表与仓库 API。"""

import sqlite3

import pytest

from calcstar.data import repositories
from calcstar.data.database import connect, init_db


@pytest.fixture()
def conn(tmp_path) -> sqlite3.Connection:
    """每个用例使用独立的临时数据库连接。"""
    c = connect(tmp_path / "calcstar.db")
    init_db(c)
    yield c
    c.close()


def _make_questions():
    """构造 5 道题：3 加法 + 2 减法（其中 7-9=… 演示可错题）。"""
    return [
        {"seq": 0, "expression": "3+5", "answer": 8},
        {"seq": 1, "expression": "7-9", "answer": -2},
        {"seq": 2, "expression": "10+4", "answer": 14},
        {"seq": 3, "expression": "15-6", "answer": 9},
        {"seq": 4, "expression": "6+6", "answer": 12},
    ]


def _new_session(conn, **overrides):
    """创建会话并写入默认 5 题，返回 (session_id, questions)。"""
    kwargs = dict(
        category="mixed",
        range_n=20,
        count=5,
        duration_minutes=10,
        allow_negative=False,
        include_parentheses=False,
        per_page=5,
    )
    kwargs.update(overrides)
    session_id = repositories.create_session(conn, **kwargs)
    questions = _make_questions()
    repositories.save_questions(conn, session_id, questions)
    return session_id, questions


def _graded_for(questions, answers):
    """按 answers{seq: user_answer} 构造 graded 判分列表。"""
    graded = []
    for q in questions:
        ua = answers.get(q["seq"])
        graded.append(
            {
                "seq": q["seq"],
                "expression": q["expression"],
                "answer": q["answer"],
                "user_answer": ua,
                "is_correct": 1 if ua == q["answer"] else 0,
            }
        )
    return graded


class TestInitDb:
    def test_init_db_idempotent(self, tmp_path):
        """init_db 连续调用两次不报错，表结构保持不变。"""
        c = connect(tmp_path / "a.db")
        init_db(c)
        init_db(c)  # 幂等
        names = {
            r["name"]
            for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"sessions", "questions", "wrong_book"} <= names
        c.close()

    def test_connect_accepts_str_path(self, tmp_path):
        """connect 接受 str 路径并启用外键约束。"""
        c = connect(str(tmp_path / "b.db"))
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert c.row_factory is sqlite3.Row
        c.close()


class TestSubmitAnswers:
    def test_full_correct_scoring(self, conn):
        """全对：score=100、correct_count=total、status=submitted、passed=1。"""
        session_id, questions = _new_session(conn)
        answers = {q["seq"]: q["answer"] for q in questions}
        repositories.submit_answers(
            conn, session_id, answers,
            _graded_for(questions, answers), 120.5,
            finished_at="2026-01-01T10:00:00",
        )
        s = repositories.get_session_detail(conn, session_id)
        assert s["score"] == 100
        assert s["correct_count"] == 5
        assert s["total_count"] == 5
        assert s["status"] == "submitted"
        assert s["passed"] == 1
        assert s["duration_seconds"] == pytest.approx(120.5)
        assert s["finished_at"] == "2026-01-01T10:00:00"

    def test_partial_wrong_updates_questions(self, conn):
        """部分答错：逐题判分写入 questions，score 按比例四舍五入。"""
        session_id, questions = _new_session(conn)
        answers = {0: 8, 1: 3, 2: 14, 3: 9, 4: None}
        # seq1 错（7-9 答成 3）、seq4 未作答 → 3/5 正确，score=60
        repositories.submit_answers(
            conn, session_id, answers,
            _graded_for(questions, answers), 80.0,
        )
        s = repositories.get_session_detail(conn, session_id)
        assert s["score"] == 60
        assert s["correct_count"] == 3
        assert s["status"] == "submitted"
        assert s["passed"] == 0
        qs = {q["seq"]: q for q in s["questions"]}
        assert qs[0]["is_correct"] == 1
        assert qs[1]["user_answer"] == 3
        assert qs[1]["is_correct"] == 0
        assert qs[4]["user_answer"] is None
        assert qs[4]["is_correct"] == 0

    def test_wrong_book_aggregation_and_repeat(self, conn):
        """答错聚合入错题本；同一表达式错两次 wrong_count=2 且时间刷新。"""
        session_id, questions = _new_session(conn)
        wrong = {1: 3, 4: 5}
        answers = {q["seq"]: q["answer"] for q in questions}
        answers.update(wrong)
        repositories.submit_answers(
            conn, session_id, answers,
            _graded_for(questions, answers), 60.0,
            finished_at="2026-01-01T10:00:00",
        )
        rows = repositories.list_wrong_book(conn)
        assert len(rows) == 2
        by_expr = {r["expression"]: r for r in rows}
        assert by_expr["7-9"]["wrong_count"] == 1
        assert by_expr["7-9"]["category"] == "mixed"
        assert by_expr["7-9"]["range_n"] == 20
        assert by_expr["7-9"]["last_wrong_at"] == "2026-01-01T10:00:00"

        # 第二局再次答错 7-9 → wrong_count=2、last_wrong_at 更新
        session_id2, questions2 = _new_session(
            conn, category="sub", range_n=100,
        )
        answers2 = {q["seq"]: q["answer"] for q in questions2}
        answers2[1] = -3  # 仍然错
        repositories.submit_answers(
            conn, session_id2, answers2,
            _graded_for(questions2, answers2), 50.0,
            finished_at="2026-02-02T11:30:00",
        )
        rows = repositories.list_wrong_book(conn)
        assert len(rows) == 2  # 仍去重为两条
        by_expr = {r["expression"]: r for r in rows}
        assert by_expr["7-9"]["wrong_count"] == 2
        assert by_expr["7-9"]["last_wrong_at"] == "2026-02-02T11:30:00"
        # 类别/范围按最近一次做错刷新
        assert by_expr["7-9"]["category"] == "sub"
        assert by_expr["7-9"]["range_n"] == 100


class TestUpdateCorrection:
    def test_correction_wrong_then_right(self, conn):
        """订正答错 correction_count+1 且错题本累计；答对后不再增加。"""
        session_id, questions = _new_session(conn)
        answers = {q["seq"]: q["answer"] for q in questions}
        answers[1] = 3  # 7-9 答错
        repositories.submit_answers(
            conn, session_id, answers,
            _graded_for(questions, answers), 60.0,
        )
        assert repositories.get_session_detail(conn, session_id)[
            "questions"
        ][1]["correction_count"] == 0

        # 第一次订正仍答错（correction_count=1，错题本 wrong_count=2）
        repositories.update_correction(conn, session_id, 1, -3, False)
        detail = repositories.get_session_detail(conn, session_id)
        assert detail["questions"][1]["correction_count"] == 1
        assert detail["questions"][1]["user_answer"] == -3
        assert detail["questions"][1]["is_correct"] == 0
        wrong = {
            r["expression"]: r
            for r in repositories.list_wrong_book(conn)
        }
        assert wrong["7-9"]["wrong_count"] == 2

        # 第二次订正答对（correction_count 不再 +1，错题本不再累计）
        repositories.update_correction(conn, session_id, 1, -2, True)
        detail = repositories.get_session_detail(conn, session_id)
        assert detail["questions"][1]["correction_count"] == 1
        assert detail["questions"][1]["user_answer"] == -2
        assert detail["questions"][1]["is_correct"] == 1
        wrong = {
            r["expression"]: r
            for r in repositories.list_wrong_book(conn)
        }
        assert wrong["7-9"]["wrong_count"] == 2

    def test_correction_first_try_wrong(self, conn):
        """答错题首次订正又错：错题本在原有基础上再 +1。"""
        session_id, questions = _new_session(conn)
        answers = {q["seq"]: q["answer"] for q in questions}
        answers[1] = 3
        repositories.submit_answers(
            conn, session_id, answers,
            _graded_for(questions, answers), 60.0,
        )
        # 错题本已有 7-9（wrong_count=1），订正又错 → 2
        repositories.update_correction(conn, session_id, 1, 5, False)
        wrong = {
            r["expression"]: r
            for r in repositories.list_wrong_book(conn)
        }
        assert wrong["7-9"]["wrong_count"] == 2


class TestSessionLifecycle:
    def test_mark_session_passed(self, conn):
        """mark_session_passed：correction_round+1、status=passed、passed=1。"""
        session_id, _ = _new_session(conn)
        repositories.mark_session_passed(conn, session_id)
        s = repositories.get_session_detail(conn, session_id)
        assert s["correction_round"] == 1
        assert s["status"] == "passed"
        assert s["passed"] == 1

    def test_increment_correction_round(self, conn):
        """increment_correction_round 仅递增轮数，不改状态。"""
        session_id, _ = _new_session(conn)
        repositories.increment_correction_round(conn, session_id)
        s = repositories.get_session_detail(conn, session_id)
        assert s["correction_round"] == 1
        assert s["status"] == "in_progress"


class TestQueries:
    def test_list_history_order_and_paging(self, conn):
        """list_history 按 started_at 倒序返回，total/分页正确。"""
        for i in range(3):
            repositories.create_session(
                conn,
                category="mixed",
                range_n=20,
                count=5,
                duration_minutes=None,
                allow_negative=False,
                include_parentheses=False,
                per_page=5,
                started_at=f"2026-03-0{i + 1}T09:00:00",
            )
        page1 = repositories.list_history(conn, page=1, page_size=2)
        assert page1["total"] == 3
        assert page1["page"] == 1
        assert page1["page_size"] == 2
        assert [it["started_at"] for it in page1["items"]] == [
            "2026-03-03T09:00:00",
            "2026-03-02T09:00:00",
        ]
        page2 = repositories.list_history(conn, page=2, page_size=2)
        assert [it["started_at"] for it in page2["items"]] == [
            "2026-03-01T09:00:00",
        ]
        empty = repositories.list_history(conn, page=9, page_size=2)
        assert empty["items"] == []

    def test_get_session_detail_none_for_missing(self, conn):
        """查询不存在的会话返回 None。"""
        assert repositories.get_session_detail(conn, 999) is None

    def test_get_session_detail_questions_sorted(self, conn):
        """get_session_detail 返回会话字段 + 按 seq 升序的题目。"""
        session_id, _ = _new_session(conn)
        detail = repositories.get_session_detail(conn, session_id)
        assert detail["category"] == "mixed"
        assert [q["seq"] for q in detail["questions"]] == [0, 1, 2, 3, 4]
        assert detail["questions"][0]["expression"] == "3+5"

    def test_list_wrong_book_filter_and_orders(self, conn):
        """list_wrong_book 支持类别筛选与 wrong_count/last_wrong_at 两种排序。"""
        # 准备：add 类错 1 次（旧时间）、sub 类错 2 次（新时间）
        sid1, qs1 = _new_session(
            conn, category="add", range_n=20,
        )
        a1 = {q["seq"]: q["answer"] for q in qs1}
        a1[0] = 1  # 3+5 答错
        repositories.submit_answers(
            conn, sid1, a1, _graded_for(qs1, a1), 30.0,
            finished_at="2026-01-10T08:00:00",
        )
        sid2, qs2 = _new_session(
            conn, category="sub", range_n=100,
        )
        a2 = {q["seq"]: q["answer"] for q in qs2}
        a2[1] = 3  # 7-9 答错
        repositories.submit_answers(
            conn, sid2, a2, _graded_for(qs2, a2), 30.0,
            finished_at="2026-01-20T08:00:00",
        )
        # 同一题再错一次 → wrong_count=2
        repositories.update_correction(conn, sid2, 1, -3, False)

        # 全部、按 wrong_count 倒序：7-9(2) 在前，3+5(1) 在后
        rows = repositories.list_wrong_book(conn)
        assert [r["expression"] for r in rows] == ["7-9", "3+5"]

        # 全部、按 last_wrong_at 倒序：7-9 时间较新，仍在前
        rows = repositories.list_wrong_book(conn, order_by="last_wrong_at")
        assert [r["expression"] for r in rows] == ["7-9", "3+5"]

        # 类别筛选：add 只有 3+5
        rows = repositories.list_wrong_book(conn, category="add")
        assert [r["expression"] for r in rows] == ["3+5"]
        rows = repositories.list_wrong_book(conn, category="sub")
        assert [r["expression"] for r in rows] == ["7-9"]
        assert repositories.list_wrong_book(conn, category="mul") == []


class TestClearHistory:
    def test_clear_removes_sessions_and_questions(self, conn):
        """清空后 sessions/questions 为空，返回删除的会话数。"""
        sid1, _ = _new_session(conn)
        sid2, _ = _new_session(conn)
        deleted = repositories.clear_history(conn)
        assert deleted == 2
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0
        assert repositories.get_session_detail(conn, sid1) is None
        assert repositories.get_session_detail(conn, sid2) is None

    def test_clear_keeps_wrong_book(self, conn):
        """错题本为独立聚合表，清空历史不影响其数据。"""
        session_id, questions = _new_session(conn)
        # 答错第 2 题（7-9），经 submit_answers 聚合进 wrong_book
        answers = {q["seq"]: q["answer"] for q in questions}
        answers[1] = 100  # 答错
        repositories.submit_answers(conn, session_id, answers,
                                    _graded_for(questions, answers), 60.0)
        assert len(repositories.list_wrong_book(conn)) == 1
        repositories.clear_history(conn)
        rows = repositories.list_wrong_book(conn)
        assert [r["expression"] for r in rows] == ["7-9"]

    def test_clear_empty_db(self, conn):
        """空库清空：返回 0 且不报错。"""
        assert repositories.clear_history(conn) == 0
