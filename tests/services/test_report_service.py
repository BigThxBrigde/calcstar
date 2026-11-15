"""report_service 成绩单 HTML 构建测试。"""

from calcstar.services.report_service import build_report_html, format_duration


def _make_detail() -> dict:
    """构造一份典型会话明细。"""
    return {
        "id": 7,
        "category": "add_sub",
        "range_n": 10,
        "count": 3,
        "duration_minutes": 5,
        "allow_negative": 0,
        "include_parentheses": 0,
        "per_page": 10,
        "started_at": "2026-11-13 07:32:00",
        "finished_at": "2026-11-13 07:33:46",
        "duration_seconds": 106.0,
        "correct_count": 2,
        "total_count": 3,
        "score": 67,
        "correction_round": 1,
        "status": "submitted",
        "passed": 0,
        "questions": [
            {
                "seq": 0,
                "expression": "3 + 5 =",
                "answer": 8,
                "user_answer": 8,
                "is_correct": 1,
                "correction_count": 0,
            },
            {
                "seq": 1,
                "expression": "9 - 2 =",
                "answer": 7,
                "user_answer": 5,
                "is_correct": 0,
                "correction_count": 1,
            },
            {
                "seq": 2,
                "expression": "4 + 6 =",
                "answer": 10,
                "user_answer": None,
                "is_correct": 0,
                "correction_count": 0,
            },
        ],
    }


class TestFormatDuration:
    def test_seconds_only(self):
        assert format_duration(59) == "59秒"

    def test_minutes(self):
        assert format_duration(106) == "1分46秒"

    def test_hours(self):
        assert format_duration(3661) == "1小时1分1秒"

    def test_none_and_negative(self):
        assert format_duration(None) == "0秒"
        assert format_duration(-5) == "0秒"


class TestBuildReportHtml:
    def test_contains_summary_fields(self):
        html_text = build_report_html(_make_detail())
        assert "CalcStar 口算练习成绩单" in html_text
        assert "2026-11-13 07:32:00" in html_text
        assert "加减法" in html_text
        assert "10 以内" in html_text
        assert "67 分" in html_text
        assert "1分46秒" in html_text
        assert "订正轮次" in html_text

    def test_pass_status(self):
        detail = _make_detail()
        detail["status"] = "passed"
        detail["passed"] = 1
        html_text = build_report_html(detail)
        assert "已通过" in html_text

    def test_contains_question_rows(self):
        html_text = build_report_html(_make_detail())
        assert "3 + 5 =" in html_text
        assert "9 - 2 =" in html_text
        assert "4 + 6 =" in html_text

    def test_wrong_and_unanswered_highlighted(self):
        html_text = build_report_html(_make_detail())
        # 错题行与未作答标记
        assert '<tr class="wrong">' in html_text
        assert "未作答" in html_text
        # 判定符号：2 错 1 对
        assert html_text.count('class="judge bad"') == 2
        assert html_text.count('class="judge ok"') == 1

    def test_expression_html_escaped(self):
        detail = _make_detail()
        detail["questions"][0]["expression"] = "<b>3 + 5</b> ="
        html_text = build_report_html(detail)
        assert "<b>3 + 5</b>" not in html_text
        assert "&lt;b&gt;3 + 5&lt;/b&gt;" in html_text

    def test_self_contained_no_external_resources(self):
        html_text = build_report_html(_make_detail())
        assert "http://" not in html_text
        assert "https://" not in html_text
        assert "<link" not in html_text
        assert "<script" not in html_text

    def test_empty_questions_fallback(self):
        detail = _make_detail()
        detail["questions"] = []
        detail["total_count"] = 0
        html_text = build_report_html(detail)
        assert "0%" in html_text
        assert "<tbody></tbody>" in html_text
