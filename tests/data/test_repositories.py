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


class TestWrongBookManagement:
    def _seed_wrong_rows(self, conn):
        """一局 5 题全部答错，聚合出 5 条错题。"""
        session_id, questions = _new_session(conn)
        answers = {q["seq"]: q["answer"] + 1000 for q in questions}
        repositories.submit_answers(
            conn, session_id, answers, _graded_for(questions, answers), 60.0
        )
        return session_id

    def test_list_wrong_book_page(self, conn):
        """分页返回 items/total/page/page_size，越界页返回空且不报错。"""
        self._seed_wrong_rows(conn)
        first = repositories.list_wrong_book_page(conn, page=1, page_size=2)
        assert first["total"] == 5
        assert first["page"] == 1
        assert first["page_size"] == 2
        assert len(first["items"]) == 2

        last = repositories.list_wrong_book_page(conn, page=3, page_size=2)
        assert len(last["items"]) == 1
        beyond = repositories.list_wrong_book_page(conn, page=9, page_size=2)
        assert beyond["items"] == [] and beyond["total"] == 5

        normalized = repositories.list_wrong_book_page(conn, page=0, page_size=0)
        assert normalized["page"] == 1 and normalized["page_size"] == 1

        filtered = repositories.list_wrong_book_page(
            conn, category="mixed", page=1, page_size=10
        )
        assert filtered["total"] == 5
        assert repositories.list_wrong_book_page(
            conn, category="mul", page=1, page_size=10
        )["total"] == 0

    def test_delete_wrong_book_entry(self, conn):
        """单条删除幂等，且不影响其余条目与练习历史。"""
        session_id = self._seed_wrong_rows(conn)
        entry_id = repositories.list_wrong_book(conn)[0]["id"]
        assert repositories.delete_wrong_book_entry(conn, entry_id) is True
        assert len(repositories.list_wrong_book(conn)) == 4
        assert repositories.delete_wrong_book_entry(conn, entry_id) is False
        assert repositories.get_session_detail(conn, session_id) is not None

    def test_clear_wrong_book(self, conn):
        """清空错题本返回条数，练习历史保留；空库清空返回 0。"""
        session_id = self._seed_wrong_rows(conn)
        assert repositories.clear_wrong_book(conn) == 5
        assert repositories.list_wrong_book(conn) == []
        assert repositories.get_session_detail(conn, session_id) is not None
        assert repositories.clear_wrong_book(conn) == 0


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


class TestDeleteSession:
    def test_delete_removes_session_and_questions(self, conn):
        """删除单条会话后其明细一并清除，其余会话不受影响。"""
        sid_keep, _ = _new_session(conn)
        sid_del, _ = _new_session(conn)
        assert repositories.delete_session(conn, sid_del) is True
        assert repositories.get_session_detail(conn, sid_del) is None
        kept = repositories.get_session_detail(conn, sid_keep)
        assert kept is not None and len(kept["questions"]) == 5
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1

    def test_delete_keeps_wrong_book(self, conn):
        """删除会话不影响错题本聚合数据。"""
        session_id, questions = _new_session(conn)
        answers = {q["seq"]: q["answer"] for q in questions}
        answers[1] = 100  # 答错
        repositories.submit_answers(conn, session_id, answers,
                                    _graded_for(questions, answers), 60.0)
        repositories.delete_session(conn, session_id)
        assert [r["expression"] for r in repositories.list_wrong_book(conn)] == ["7-9"]

    def test_delete_missing_session(self, conn):
        """会话不存在时返回 False（幂等）。"""
        assert repositories.delete_session(conn, 9999) is False


class TestResetSession:
    def test_reset_clears_answers_and_stats(self, conn):
        """重置后题目作答清空、会话统计归零、状态回到 in_progress。"""
        session_id, questions = _new_session(conn)
        answers = {q["seq"]: q["answer"] for q in questions}
        answers[1] = 100  # 答错
        repositories.submit_answers(conn, session_id, answers,
                                    _graded_for(questions, answers), 60.0)
        repositories.update_correction(conn, session_id, 1, 5, False)

        row = repositories.reset_session(conn, session_id)
        assert row is not None
        assert row["status"] == "in_progress"
        assert row["score"] is None
        assert row["correct_count"] is None
        assert row["total_count"] is None
        assert row["finished_at"] is None
        assert row["duration_seconds"] is None
        assert row["correction_round"] == 0
        assert row["passed"] == 0

        detail = repositories.get_session_detail(conn, session_id)
        assert len(detail["questions"]) == 5
        for q in detail["questions"]:
            assert q["user_answer"] is None
            assert q["is_correct"] is None
            assert q["correction_count"] == 0
        # 题目本身保持原卷不变
        assert [q["expression"] for q in detail["questions"]] == \
            [q["expression"] for q in questions]

    def test_reset_refreshes_started_at(self, conn):
        """重置后 started_at 刷新为当前时间（重做记录排到最新）。"""
        session_id, _ = _new_session(conn)
        before = repositories.get_session_detail(conn, session_id)["started_at"]
        repositories.reset_session(conn, session_id)
        after = repositories.get_session_detail(conn, session_id)["started_at"]
        assert after >= before

    def test_reset_keeps_wrong_book(self, conn):
        """重置不改动错题本聚合数据。"""
        session_id, questions = _new_session(conn)
        answers = {q["seq"]: q["answer"] for q in questions}
        answers[1] = 100  # 答错
        repositories.submit_answers(conn, session_id, answers,
                                    _graded_for(questions, answers), 60.0)
        repositories.reset_session(conn, session_id)
        assert [r["expression"] for r in repositories.list_wrong_book(conn)] == ["7-9"]

    def test_reset_resubmit_updates_same_record(self, conn):
        """重置后再次提交：同一条记录被原地更新，不新增会话。"""
        session_id, questions = _new_session(conn)
        wrong = {q["seq"]: q["answer"] + 1 for q in questions}
        repositories.submit_answers(conn, session_id, wrong,
                                    _graded_for(questions, wrong), 30.0)
        total_before = repositories.list_history(conn)["total"]

        repositories.reset_session(conn, session_id)
        answers = {q["seq"]: q["answer"] for q in questions}
        repositories.submit_answers(conn, session_id, answers,
                                    _graded_for(questions, answers), 45.0)

        assert repositories.list_history(conn)["total"] == total_before
        detail = repositories.get_session_detail(conn, session_id)
        assert detail["score"] == 100
        assert detail["duration_seconds"] == 45.0

    def test_reset_missing_session(self, conn):
        """会话不存在时返回 None（幂等）。"""
        assert repositories.reset_session(conn, 9999) is None


class TestSessionFormColumns:
    def test_create_session_stores_form_params(self, conn):
        """create_session 持久化 blank_position/operand_count。"""
        sid, _ = _new_session(
            conn, blank_position="any", operand_count=3
        )
        detail = repositories.get_session_detail(conn, sid)
        assert detail["blank_position"] == "any"
        assert detail["operand_count"] == 3

    def test_migration_adds_columns_to_legacy_db(self, tmp_path):
        """旧库（无新列）经 init_db 幂等迁移补齐，历史行取默认值。"""
        c = connect(tmp_path / "legacy.db")
        # 手工建一张旧结构 sessions 表
        c.execute(
            """
            CREATE TABLE sessions (
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
        c.execute(
            "INSERT INTO sessions (category, range_n, count, allow_negative,"
            " include_parentheses, per_page, started_at)"
            " VALUES ('mixed', 20, 5, 0, 0, 5, '2026-01-01T00:00:00')"
        )
        c.commit()
        init_db(c)  # 迁移
        cols = {
            r["name"] for r in c.execute("PRAGMA table_info(sessions)").fetchall()
        }
        assert {"blank_position", "operand_count"} <= cols
        row = c.execute("SELECT blank_position, operand_count FROM sessions").fetchone()
        assert row["blank_position"] == "last"
        assert row["operand_count"] == 0
        init_db(c)  # 再次调用幂等
        c.close()
