"""tests/desktop：report_exporter 纯逻辑函数测试。

Qt 渲染函数 ``export_report_pdf`` 依赖 QApplication 与离屏
QtWebEngine（运行态专属），不在此覆盖；仅测试纯逻辑的默认文件名
构造。
"""

from calcstar.desktop.report_exporter import build_default_filename


class TestBuildDefaultFilename:
    def test_from_started_at(self):
        detail = {"started_at": "2026-11-13 07:32:00"}
        assert build_default_filename(detail) == "CalcStar成绩单_20261113-0732.pdf"

    def test_iso_format_started_at(self):
        detail = {"started_at": "2026-11-13T07:32:00"}
        assert build_default_filename(detail) == "CalcStar成绩单_20261113-0732.pdf"

    def test_fallback_to_now(self):
        """无法解析的时间回退到当前时间（仅校验格式）。"""
        filename = build_default_filename({"started_at": "bad-format"})
        assert filename.startswith("CalcStar成绩单_")
        assert filename.endswith(".pdf")

    def test_missing_started_at(self):
        filename = build_default_filename({})
        assert filename.startswith("CalcStar成绩单_")
        assert filename.endswith(".pdf")
