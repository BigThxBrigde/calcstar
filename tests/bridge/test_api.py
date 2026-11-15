"""tests/bridge：CalcStarBridge JSON 桥接测试（tmp_path 独立数据库）。"""

import json

import pytest

from calcstar.bridge.api import create_bridge


@pytest.fixture()
def bridge(tmp_path):
    """每个用例使用独立的临时数据库（桥内两个服务共享同一路径）。"""
    b = create_bridge(tmp_path / "calcstar.db")
    yield b
    b._practice._conn.close()
    b._stats._conn.close()


def _create(bridge, count=5):
    """经桥接创建一局默认练习（加法，范围 10），返回 data。"""
    resp = json.loads(bridge.create_practice(json.dumps({
        "category": "add", "range_n": 10, "count": count,
        "duration_minutes": 5, "per_page": 5,
    })))
    assert resp["ok"] is True
    return resp["data"]


def _answers_via_bridge(bridge, session_id):
    """经桥接取回会话题目的正确答案 {seq: answer}。"""
    resp = json.loads(bridge.get_session_detail(
        json.dumps({"session_id": session_id})
    ))
    assert resp["ok"] is True
    return {q["seq"]: q["answer"] for q in resp["data"]["questions"]}


class TestCreatePractice:
    def test_ok_structure(self, bridge):
        """合法 payload：ok=True 且 data 结构正确。"""
        resp = json.loads(bridge.create_practice(json.dumps({
            "category": "add", "range_n": 10, "count": 20,
            "duration_minutes": 5, "per_page": 10,
        })))
        assert resp["ok"] is True
        data = resp["data"]
        assert data["total_count"] == 20
        assert data["total_pages"] == 2
        assert data["duration_seconds"] == 300
        assert len(data["questions"]) == 20
        assert set(data["questions"][0]) == {"seq", "expression"}

    def test_invalid_json_returns_error(self, bridge):
        """非法 JSON：ok=False 且含 error。"""
        resp = json.loads(bridge.create_practice("not-json"))
        assert resp["ok"] is False
        assert resp["error"]

    def test_non_object_payload(self, bridge):
        """payload 非 JSON 对象：ok=False。"""
        resp = json.loads(bridge.list_history("[]"))
        assert resp["ok"] is False

    def test_invalid_params_returns_error(self, bridge):
        """非法参数：ok=False 且 error 含校验信息。"""
        resp = json.loads(bridge.create_practice(json.dumps({
            "category": "add", "range_n": 0, "count": 500,
            "duration_minutes": None, "per_page": 10,
        })))
        assert resp["ok"] is False
        assert "数值范围" in resp["error"]


class TestSubmitAndCorrect:
    def test_submit_with_string_keys(self, bridge):
        """前端字符串键答案经桥接转换为 int 并正确判分。"""
        data = _create(bridge)
        answers = _answers_via_bridge(bridge, data["session_id"])
        resp = json.loads(bridge.submit_practice(json.dumps({
            "session_id": data["session_id"],
            "answers": {str(seq): ans for seq, ans in answers.items()},
            "duration_seconds": 42.5,
        })))
        assert resp["ok"] is True
        assert resp["data"]["score"] == 100
        assert resp["data"]["passed"] is True

    def test_correction_flow(self, bridge):
        """经桥接的两轮订正至全对。"""
        data = _create(bridge)
        sid = data["session_id"]
        answers = _answers_via_bridge(bridge, sid)
        seqs = sorted(answers)
        payload_answers = {str(seq): ans for seq, ans in answers.items()}
        payload_answers[str(seqs[0])] = answers[seqs[0]] + 7
        payload_answers[str(seqs[1])] = answers[seqs[1]] + 7
        sub = json.loads(bridge.submit_practice(json.dumps({
            "session_id": sid, "answers": payload_answers,
            "duration_seconds": 30,
        })))
        assert sub["data"]["passed"] is False

        round1 = json.loads(bridge.submit_correction(json.dumps({
            "session_id": sid,
            "corrections": {
                str(seqs[0]): answers[seqs[0]],
                str(seqs[1]): answers[seqs[1]] + 3,
            },
        })))
        assert round1["data"]["passed"] is False
        assert round1["data"]["correction_round"] == 0

        round2 = json.loads(bridge.submit_correction(json.dumps({
            "session_id": sid,
            "corrections": {str(seqs[1]): answers[seqs[1]]},
        })))
        assert round2["data"]["all_correct"] is True
        assert round2["data"]["passed"] is True
        assert round2["data"]["correction_round"] == 1

    def test_create_from_wrong_book(self, bridge):
        """错题建卷经桥接可用，题目与错题本一致。"""
        data = _create(bridge)
        answers = _answers_via_bridge(bridge, data["session_id"])
        bridge.submit_practice(json.dumps({
            "session_id": data["session_id"],
            "answers": {str(seq): ans + 7 for seq, ans in answers.items()},
            "duration_seconds": 30,
        }))
        resp = json.loads(bridge.create_practice_from_wrong_book(
            json.dumps({"count": 5})
        ))
        assert resp["ok"] is True
        assert resp["data"]["source"] == "wrong_book"
        assert resp["data"]["total_count"] == 5
        wrong_detail = json.loads(bridge.get_session_detail(
            json.dumps({"session_id": data["session_id"]})
        ))
        wrong_set = {
            q["expression"]
            for q in wrong_detail["data"]["questions"]
            if q["is_correct"] == 0
        }
        assert {q["expression"] for q in resp["data"]["questions"]} == wrong_set


class TestQueries:
    def test_list_history(self, bridge):
        """历史查询：缺省与显式分页参数均可用。"""
        _create(bridge)
        resp = json.loads(bridge.list_history("{}"))
        assert resp["ok"] is True
        assert resp["data"]["total"] == 1
        resp = json.loads(bridge.list_history(
            json.dumps({"page": 1, "page_size": 5})
        ))
        assert resp["data"]["page_size"] == 5

    def test_list_wrong_book(self, bridge):
        """错题本查询：支持类别筛选与缺省参数。"""
        data = _create(bridge)
        answers = _answers_via_bridge(bridge, data["session_id"])
        bridge.submit_practice(json.dumps({
            "session_id": data["session_id"],
            "answers": {str(seq): ans + 7 for seq, ans in answers.items()},
            "duration_seconds": 30,
        }))
        resp = json.loads(bridge.list_wrong_book(json.dumps({"category": "add"})))
        assert resp["ok"] is True
        assert len(resp["data"]) == 5
        resp = json.loads(bridge.list_wrong_book("{}"))
        assert len(resp["data"]) == 5

    def test_get_session_detail_missing(self, bridge):
        """不存在的会话：ok=False 且 error 提示不存在。"""
        resp = json.loads(bridge.get_session_detail(
            json.dumps({"session_id": 999})
        ))
        assert resp["ok"] is False
        assert "不存在" in resp["error"]


class TestExportReportPdf:
    def _submit(self, bridge):
        """创建并提交一局练习，返回 session_id。"""
        data = _create(bridge)
        answers = _answers_via_bridge(bridge, data["session_id"])
        bridge.submit_practice(json.dumps({
            "session_id": data["session_id"],
            "answers": {str(seq): ans for seq, ans in answers.items()},
            "duration_seconds": 30,
        }))
        return data["session_id"]

    def test_export_ok(self, tmp_path):
        """导出器返回路径：ok=True 且 data 含 path。"""
        b = create_bridge(
            tmp_path / "calcstar.db",
            report_exporter=lambda detail, suggested: "C:/out/report.pdf",
        )
        try:
            sid = self._submit(b)
            resp = json.loads(b.export_report_pdf(
                json.dumps({"session_id": sid})
            ))
            assert resp["ok"] is True
            assert resp["data"]["cancelled"] is False
            assert resp["data"]["path"] == "C:/out/report.pdf"
        finally:
            b._practice._conn.close()
            b._stats._conn.close()

    def test_export_cancelled(self, tmp_path):
        """用户取消（导出器返回 None）：ok=True 且 cancelled=True。"""
        b = create_bridge(
            tmp_path / "calcstar.db",
            report_exporter=lambda detail, suggested: None,
        )
        try:
            sid = self._submit(b)
            resp = json.loads(b.export_report_pdf(
                json.dumps({"session_id": sid})
            ))
            assert resp["ok"] is True
            assert resp["data"]["cancelled"] is True
            assert resp["data"]["path"] is None
        finally:
            b._practice._conn.close()
            b._stats._conn.close()

    def test_export_failure_returns_error(self, tmp_path):
        """导出器抛异常：ok=False 且 error 非空。"""
        def boom(detail, suggested):
            raise RuntimeError("PDF 生成失败")

        b = create_bridge(tmp_path / "calcstar.db", report_exporter=boom)
        try:
            sid = self._submit(b)
            resp = json.loads(b.export_report_pdf(
                json.dumps({"session_id": sid})
            ))
            assert resp["ok"] is False
            assert "PDF 生成失败" in resp["error"]
        finally:
            b._practice._conn.close()
            b._stats._conn.close()

    def test_export_without_exporter(self, bridge):
        """未注入导出器：ok=False 且提示不支持。"""
        sid = self._submit(bridge)
        resp = json.loads(bridge.export_report_pdf(
            json.dumps({"session_id": sid})
        ))
        assert resp["ok"] is False
        assert "不支持" in resp["error"]

    def test_export_missing_session(self, tmp_path):
        """会话不存在：ok=False。"""
        b = create_bridge(
            tmp_path / "calcstar.db",
            report_exporter=lambda detail, suggested: "x.pdf",
        )
        try:
            resp = json.loads(b.export_report_pdf(
                json.dumps({"session_id": 999})
            ))
            assert resp["ok"] is False
            assert "不存在" in resp["error"]
        finally:
            b._practice._conn.close()
            b._stats._conn.close()


class TestClearHistory:
    def test_clear_returns_deleted_count(self, bridge, tmp_path):
        """清空后 ok=True 且 data.deleted 等于会话数；历史变空。"""
        data = _create(bridge)
        bridge.submit_practice(json.dumps({
            "session_id": data["session_id"],
            "answers": {"0": 1},
            "duration_seconds": 10,
        }))
        resp = json.loads(bridge.clear_history("{}"))
        assert resp["ok"] is True
        assert resp["data"]["deleted"] == 1
        listing = json.loads(bridge.list_history(
            json.dumps({"page": 1, "page_size": 10})
        ))
        assert listing["data"]["total"] == 0

    def test_clear_keeps_wrong_book(self, bridge, tmp_path):
        """清空历史后错题本数据保留。"""
        data = _create(bridge)
        bridge.submit_practice(json.dumps({
            "session_id": data["session_id"],
            "answers": {"0": 1},  # 答错聚合进错题本
            "duration_seconds": 10,
        }))
        before = json.loads(bridge.list_wrong_book("{}"))
        assert before["data"]
        bridge.clear_history("{}")
        after = json.loads(bridge.list_wrong_book("{}"))
        assert after["data"] == before["data"]


class TestFactory:
    def test_zero_arg_with_env_db(self, monkeypatch, tmp_path):
        """create_bridge() 零参调用兼容（CALCSTAR_DB 指向临时库）。"""
        monkeypatch.setenv("CALCSTAR_DB", str(tmp_path / "zero.db"))
        b = create_bridge()
        try:
            resp = json.loads(b.list_history("{}"))
            assert resp["ok"] is True
        finally:
            b._practice._conn.close()
            b._stats._conn.close()
