"""tests/services：PracticeService 单元测试（tmp_path 独立数据库）。"""

import pytest

from calcstar.config import MAX_COUNT
from calcstar.data.repositories import get_session_detail, list_wrong_book
from calcstar.services.practice_service import (
    InvalidParamsError,
    PracticeService,
    SessionNotFoundError,
)


@pytest.fixture()
def service(tmp_path):
    """每个用例使用独立的临时数据库。"""
    svc = PracticeService(tmp_path / "calcstar.db")
    yield svc
    svc._conn.close()


def _create(service, count=5):
    """用固定参数创建一局练习（加法，范围 10）。"""
    return service.create_practice({
        "category": "add",
        "range_n": 10,
        "count": count,
        "duration_minutes": 5,
        "per_page": 5,
    })


def _answers_of(service, session_id):
    """从库中取回某会话全部题目的正确答案 {seq: answer}。"""
    rows = get_session_detail(service._conn, session_id)["questions"]
    return {row["seq"]: row["answer"] for row in rows}


def _sessions_count(service):
    """当前数据库中的会话总数。"""
    return service._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]


class TestCreatePractice:
    def test_invalid_params_range_and_count(self, service):
        """范围为 0、题量超限等非法参数抛 InvalidParamsError 且逐条列出。"""
        with pytest.raises(InvalidParamsError) as excinfo:
            service.create_practice({
                "category": "add", "range_n": 0, "count": 500,
                "duration_minutes": None, "per_page": 10,
            })
        assert isinstance(excinfo.value, ValueError)
        errors = excinfo.value.errors
        assert any("数值范围" in item for item in errors)
        assert any("题目数量" in item for item in errors)

    def test_invalid_category(self, service):
        """未知类别抛 InvalidParamsError。"""
        with pytest.raises(InvalidParamsError) as excinfo:
            service.create_practice({
                "category": "nope", "range_n": 10, "count": 5,
                "duration_minutes": None, "per_page": 5,
            })
        assert any("运算类别" in item for item in excinfo.value.errors)

    def test_invalid_duration_and_per_page(self, service):
        """限时为 0、每页题数为 0 均判非法。"""
        with pytest.raises(InvalidParamsError) as excinfo:
            service.create_practice({
                "category": "add", "range_n": 10, "count": 20,
                "duration_minutes": 0, "per_page": 0,
            })
        errors = excinfo.value.errors
        assert any("限时" in item for item in errors)
        assert any("每页题数" in item for item in errors)

    def test_returns_structure_and_paging(self, service):
        """正常创建：返回结构与分页元数据完整且题目不含答案。"""
        result = _create(service, count=20)
        assert isinstance(result["session_id"], int)
        assert result["total_count"] == 20
        assert len(result["questions"]) == 20
        assert [q["seq"] for q in result["questions"]] == list(range(20))
        assert all(set(q) == {"seq", "expression"} for q in result["questions"])
        assert result["per_page"] == 5
        assert result["total_pages"] == 4
        assert result["duration_seconds"] == 300
        assert result["category"] == "add"
        assert result["range_n"] == 10
        detail = get_session_detail(service._conn, result["session_id"])
        assert detail["count"] == 20
        assert detail["status"] == "in_progress"
        assert len(detail["questions"]) == 20

    def test_unlimited_duration(self, service):
        """不限时：duration_seconds 为 None，页数向上取整。"""
        result = service.create_practice({
            "category": "sub", "range_n": 20, "count": 6,
            "duration_minutes": None, "per_page": 5,
        })
        assert result["duration_seconds"] is None
        assert result["total_pages"] == 2

    def test_invalid_blank_position_and_operand_count(self, service):
        """blank_position/operand_count 非法值抛 InvalidParamsError。"""
        with pytest.raises(InvalidParamsError) as excinfo:
            service.create_practice({
                "category": "add", "range_n": 10, "count": 5,
                "duration_minutes": None, "per_page": 5,
                "blank_position": "unknown", "operand_count": 11,
            })
        errors = excinfo.value.errors
        assert any("填空位置" in item for item in errors)
        assert any("操作数个数" in item for item in errors)

    def test_create_with_blank_any_and_random_operand_count(self, service):
        """blank_position=any 与 operand_count="random" 正常创建：
        随机目数两/三目均出现，填空位置不定且表达式互不重复。"""
        result = service.create_practice({
            "category": "add", "range_n": 20, "count": 40,
            "duration_minutes": None, "per_page": 10,
            "blank_position": "any", "operand_count": "random",
        })
        assert result["total_count"] == 40
        expressions = [q["expression"] for q in result["questions"]]
        assert len(set(expressions)) == 40
        assert any(expr.count("+") == 2 for expr in expressions)
        assert any(expr.count("+") == 1 for expr in expressions)
        # 末尾空与中间空都用 ( ) 占位：按等号前的部分区分两种题型
        assert any("( )" in expr.partition(" = ")[0] for expr in expressions)
        assert any("( )" not in expr.partition(" = ")[0] for expr in expressions)

    @pytest.mark.parametrize(
        "blank_position,operand_count", [("middle", 4), ("last", 10), ("any", -1)]
    )
    def test_create_with_new_form_options(self, service, blank_position, operand_count):
        """新增填空模式与 2~10 目/随机目数均可创建练习并落库。"""
        result = service.create_practice({
            "category": "add", "range_n": 100, "count": 12,
            "duration_minutes": None, "per_page": 5,
            "blank_position": blank_position, "operand_count": operand_count,
        })
        questions = result["questions"]
        assert result["total_count"] == 12
        detail = get_session_detail(service._conn, result["session_id"])
        assert detail["blank_position"] == blank_position
        assert detail["operand_count"] == operand_count
        if operand_count > 0:
            for item in questions:
                assert len(item["expression"].split(" ")) >= operand_count * 2 - 1


class TestSubmitPractice:
    def test_empty_answers_all_wrong(self, service):
        """空作答：全部按错计、score=0。"""
        result = _create(service)
        res = service.submit_practice(result["session_id"], {})
        assert res["score"] == 0
        assert res["correct_count"] == 0
        assert res["total_count"] == 5
        assert res["passed"] is False
        assert len(res["wrong_answers"]) == 5
        assert all(w["user_answer"] is None for w in res["wrong_answers"])

    def test_none_answers_counted_wrong(self, service):
        """答案为 None 视为未作答，按错计。"""
        result = _create(service)
        res = service.submit_practice(result["session_id"], {0: None, 1: None})
        assert res["score"] == 0
        assert res["correct_count"] == 0
        assert len(res["wrong_answers"]) == 5

    def test_all_correct(self, service):
        """全对提交：score=100、passed=True、会话状态落库。"""
        result = _create(service)
        answers = _answers_of(service, result["session_id"])
        res = service.submit_practice(result["session_id"], answers, 88.0)
        assert res["score"] == 100
        assert res["correct_count"] == 5
        assert res["passed"] is True
        assert res["wrong_answers"] == []
        detail = get_session_detail(service._conn, result["session_id"])
        assert detail["status"] == "submitted"
        assert detail["passed"] == 1
        assert detail["score"] == 100
        assert detail["duration_seconds"] == pytest.approx(88.0)

    def test_partial_correct(self, service):
        """部分对提交：得分比例正确、错题明细含正确答案与用户答案。"""
        result = _create(service)
        answers = _answers_of(service, result["session_id"])
        seqs = sorted(answers)
        submitted = dict(answers)
        submitted[seqs[0]] = answers[seqs[0]] + 7  # 必错
        submitted[seqs[1]] = None  # 未作答按错
        res = service.submit_practice(result["session_id"], submitted, 40.0)
        assert res["correct_count"] == 3
        assert res["score"] == 60
        assert res["passed"] is False
        assert {w["seq"] for w in res["wrong_answers"]} == {seqs[0], seqs[1]}
        first = next(w for w in res["wrong_answers"] if w["seq"] == seqs[0])
        assert first["answer"] == answers[seqs[0]]
        assert first["user_answer"] == answers[seqs[0]] + 7

    def test_timeout_submission_persists(self, service):
        """超时提交：duration_seconds 照常落库且状态为 submitted。"""
        result = _create(service)
        answers = _answers_of(service, result["session_id"])
        res = service.submit_practice(
            result["session_id"], answers, duration_seconds=9999.5
        )
        assert res["passed"] is True
        detail = get_session_detail(service._conn, result["session_id"])
        assert detail["duration_seconds"] == pytest.approx(9999.5)
        assert detail["finished_at"] is not None

    def test_wrong_answers_aggregated_to_wrong_book(self, service):
        """提交后错题聚合进错题本。"""
        result = _create(service)
        submitted = {
            seq: ans + 7
            for seq, ans in _answers_of(service, result["session_id"]).items()
        }
        service.submit_practice(result["session_id"], submitted, 30.0)
        wrong = list_wrong_book(service._conn)
        assert len(wrong) == 5
        assert all(row["wrong_count"] == 1 for row in wrong)

    def test_session_not_found(self, service):
        """不存在的会话抛 SessionNotFoundError。"""
        with pytest.raises(SessionNotFoundError):
            service.submit_practice(999, {})


class TestResetPractice:
    def test_reset_returns_same_structure_and_session(self, service):
        """重做返回结构同 create_practice，session_id 保持不变。"""
        created = _create(service)
        answers = _answers_of(service, created["session_id"])
        service.submit_practice(created["session_id"], answers, 30.0)

        data = service.reset_practice(created["session_id"])
        assert data["session_id"] == created["session_id"]
        assert data["total_count"] == 5
        assert data["per_page"] == 5
        assert data["total_pages"] == 1
        assert data["duration_seconds"] == 300
        assert data["category"] == "add"
        assert data["range_n"] == 10
        assert len(data["questions"]) == 5
        assert set(data["questions"][0]) == {"seq", "expression"}

    def test_reset_restores_in_progress_state(self, service):
        """重做后会话回到未作答状态，题目保持原卷。"""
        created = _create(service)
        sid = created["session_id"]
        answers = _answers_of(service, sid)
        service.submit_practice(sid, answers, 30.0)

        service.reset_practice(sid)
        detail = get_session_detail(service._conn, sid)
        assert detail["status"] == "in_progress"
        assert detail["score"] is None
        assert all(q["user_answer"] is None for q in detail["questions"])
        # 题目与原卷一致（原卷重做，非重新生成）
        assert [q["expression"] for q in detail["questions"]] == \
            [q["expression"] for q in created["questions"]]

    def test_resubmit_after_reset_updates_same_record(self, service):
        """重做后再提交：同一条历史记录被更新，历史总数不变。"""
        created = _create(service)
        sid = created["session_id"]
        answers = _answers_of(service, sid)
        wrong = {seq: ans + 1 for seq, ans in answers.items()}
        service.submit_practice(sid, wrong, 20.0)
        total_before = _sessions_count(service)

        service.reset_practice(sid)
        service.submit_practice(sid, answers, 55.0)

        assert _sessions_count(service) == total_before
        detail = get_session_detail(service._conn, sid)
        assert detail["score"] == 100
        assert detail["duration_seconds"] == pytest.approx(55.0)

    def test_reset_missing_session(self, service):
        """不存在的会话抛 SessionNotFoundError。"""
        with pytest.raises(SessionNotFoundError):
            service.reset_practice(9999)


class TestSubmitCorrection:
    def test_multi_round_until_passed(self, service):
        """先答错 2 题；轮 1 错 1 对 1 不计轮次，轮 2 全对 → passed。"""
        result = _create(service)
        sid = result["session_id"]
        answers = _answers_of(service, sid)
        seqs = sorted(answers)
        submitted = dict(answers)
        submitted[seqs[0]] = answers[seqs[0]] + 7
        submitted[seqs[1]] = answers[seqs[1]] + 7
        service.submit_practice(sid, submitted, 60.0)

        # 轮 1：第一题改对、第二题仍错 → 本轮有错，不计轮次
        round1 = service.submit_correction(sid, {
            seqs[0]: answers[seqs[0]],
            seqs[1]: answers[seqs[1]] + 3,
        })
        assert round1["all_correct"] is False
        assert round1["passed"] is False
        assert round1["correction_round"] == 0
        assert [w["seq"] for w in round1["wrong_answers"]] == [seqs[1]]

        # 轮 2：改对剩余错题 → 整局全对，mark_session_passed 计入该轮
        round2 = service.submit_correction(sid, {seqs[1]: answers[seqs[1]]})
        assert round2["all_correct"] is True
        assert round2["passed"] is True
        assert round2["correction_round"] == 1
        assert round2["wrong_answers"] == []

        detail = get_session_detail(service._conn, sid)
        assert detail["status"] == "passed"
        assert detail["passed"] == 1

    def test_correct_round_without_session_complete(self, service):
        """本轮全对但整局仍有错：轮次 +1 且不达标；再答错不累计轮次。"""
        result = _create(service)
        sid = result["session_id"]
        answers = _answers_of(service, sid)
        seqs = sorted(answers)
        submitted = dict(answers)
        submitted[seqs[0]] = answers[seqs[0]] + 7
        submitted[seqs[1]] = answers[seqs[1]] + 7
        service.submit_practice(sid, submitted, 50.0)

        round1 = service.submit_correction(sid, {seqs[0]: answers[seqs[0]]})
        assert round1["correction_round"] == 1
        assert round1["passed"] is False

        round2 = service.submit_correction(sid, {seqs[1]: answers[seqs[1]] + 5})
        assert round2["correction_round"] == 1  # 本轮有错不累计
        assert round2["passed"] is False

    def test_session_not_found(self, service):
        """不存在的会话抛 SessionNotFoundError。"""
        with pytest.raises(SessionNotFoundError):
            service.submit_correction(999, {})


class TestCreateFromWrongBook:
    def test_questions_match_wrong_book(self, service):
        """用错题生成新练习：题目与错题本一致、来源标记与截断正确。"""
        result = _create(service)
        answers = _answers_of(service, result["session_id"])
        seqs = sorted(answers)
        submitted = dict(answers)
        for seq in seqs[:3]:
            submitted[seq] = answers[seq] + 7
        service.submit_practice(result["session_id"], submitted, 30.0)

        wrong_book = list_wrong_book(service._conn)
        assert len(wrong_book) == 3

        limited = service.create_practice_from_wrong_book(
            {"count": 2, "duration_minutes": 5, "per_page": 5}
        )
        assert limited["source"] == "wrong_book"
        assert limited["total_count"] == 2
        assert limited["duration_seconds"] == 300
        detail = get_session_detail(service._conn, limited["session_id"])
        wrong_expressions = {row["expression"] for row in wrong_book}
        new_expressions = {q["expression"] for q in detail["questions"]}
        assert new_expressions < wrong_expressions  # 全部来自错题本且截断 1 条
        assert len(detail["questions"]) == 2

        # 不传 count → 错题全部
        full = service.create_practice_from_wrong_book({})
        assert full["total_count"] == 3
        assert full["source"] == "wrong_book"

    def test_category_filter_uses_wrong_book_meta(self, service):
        """按类别筛选；category/range_n 取错题本条目值。"""
        result = _create(service)  # add / range 10
        submitted = {
            seq: ans + 7
            for seq, ans in _answers_of(service, result["session_id"]).items()
        }
        service.submit_practice(result["session_id"], submitted, 30.0)

        filtered = service.create_practice_from_wrong_book({"category": "add"})
        assert filtered["total_count"] == 5
        assert filtered["category"] == "add"
        assert filtered["range_n"] == 10

        with pytest.raises(InvalidParamsError):
            service.create_practice_from_wrong_book({"category": "mixed"})

    def test_invalid_count_and_range(self, service):
        """count 越界 / range_n 非法 / 空错题本均抛 InvalidParamsError。"""
        with pytest.raises(InvalidParamsError):
            service.create_practice_from_wrong_book({})  # 空错题本

        result = _create(service)
        submitted = {
            seq: ans + 7
            for seq, ans in _answers_of(service, result["session_id"]).items()
        }
        service.submit_practice(result["session_id"], submitted, 30.0)

        with pytest.raises(InvalidParamsError):
            service.create_practice_from_wrong_book({"count": 0})
        with pytest.raises(InvalidParamsError):
            service.create_practice_from_wrong_book({"count": MAX_COUNT + 1})
        with pytest.raises(InvalidParamsError):
            service.create_practice_from_wrong_book({"range_n": 0})
