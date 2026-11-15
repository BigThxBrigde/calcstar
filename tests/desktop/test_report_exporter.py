"""tests/desktop：report_exporter 测试。

导出已改为 QTextDocument + QPrinter 同步排版（不再依赖离屏
QtWebEngine 渲染进程），因此可在测试内以 QApplication 直接验证
真实 PDF 生成；同时覆盖纯逻辑的默认文件名构造。
"""

import pytest
from PyQt5.QtWidgets import QApplication

from calcstar.desktop.report_exporter import (
    build_default_filename,
    export_report_pdf,
)


@pytest.fixture(scope="module")
def qapp():
    """模块级 QApplication（QTextDocument/QPrinter 排版所需）。"""
    app = QApplication.instance() or QApplication([])
    yield app


def _detail() -> dict:
    """最小可导出的会话明细。"""
    return {
        "id": 1,
        "category": "add",
        "range_n": 10,
        "count": 2,
        "started_at": "2026-11-15T09:00:00",
        "duration_seconds": 30.0,
        "correct_count": 1,
        "total_count": 2,
        "score": 50,
        "correction_round": 0,
        "status": "submitted",
        "passed": 0,
        "questions": [
            {"seq": 0, "expression": "1 + 2 =", "answer": 3,
             "user_answer": 3, "is_correct": 1, "correction_count": 0},
            {"seq": 1, "expression": "4 + 5 =", "answer": 9,
             "user_answer": None, "is_correct": 0, "correction_count": 0},
        ],
    }


class TestExportReportPdf:
    def test_exports_real_pdf(self, qapp, tmp_path):
        """导出后生成非空 PDF 文件，返回绝对路径。"""
        target = tmp_path / "成绩单.pdf"
        result = export_report_pdf(_detail(), str(target))
        assert result == str(target)
        assert target.exists()
        assert target.stat().st_size > 0

    def test_creates_missing_parent_dirs(self, qapp, tmp_path):
        """父目录不存在时自动创建。"""
        target = tmp_path / "a" / "b" / "out.pdf"
        export_report_pdf(_detail(), str(target))
        assert target.exists()


class TestBuildDefaultFilename:
    def test_from_space_separated_time(self):
        assert build_default_filename("2026-11-13 07:32:00") == (
            "CalcStar成绩单_20261113-0732.pdf"
        )

    def test_from_iso_time(self):
        assert build_default_filename("2026-11-13T07:32:00") == (
            "CalcStar成绩单_20261113-0732.pdf"
        )

    def test_unparseable_time_falls_back(self):
        """无法提取时间时返回不含时间戳的默认名。"""
        assert build_default_filename("bad-format") == "CalcStar成绩单.pdf"

    def test_missing_started_at(self):
        assert build_default_filename("") == "CalcStar成绩单.pdf"
