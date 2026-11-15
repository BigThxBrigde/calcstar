"""成绩单 PDF 导出器（desktop 层）。

把 services.report_service 构建的成绩单 HTML 用 QTextDocument +
QPrinter 同步排版为 A4 纵向 PDF（本地生成，不请求网络资源，
不启动第二渲染进程/离屏页面，避免卡死与崩溃）。

由 desktop.window 注入到 bridge（bridge → desktop 单向依赖，
接口在 bridge._ReportExporter 中定义）。
"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QMarginsF
from PyQt5.QtGui import QFont, QPageLayout, QPageSize, QTextDocument
from PyQt5.QtPrintSupport import QPrinter

from calcstar.services.report_service import build_report_html


class ReportExportError(RuntimeError):
    """成绩单导出失败（含生成结果缺失等异常情况）。"""


def export_report_pdf(detail: dict, target_path: str) -> str:
    """把会话明细导出为成绩单 PDF（同步、本地）。

    Args:
        detail: ``data.repositories.get_session_detail`` 返回的会话字典。
        target_path: 目标 PDF 文件路径（含文件名）。

    Returns:
        实际写入的 PDF 绝对路径字符串。

    Raises:
        ReportExportError: 文件创建失败或生成结果缺失。
    """
    target = Path(target_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(target))
    printer.setPageLayout(
        QPageLayout(
            QPageSize(QPageSize.A4),
            QPageLayout.Portrait,
            QMarginsF(12.0, 12.0, 12.0, 12.0),
            QPageLayout.Millimeter,
        )
    )

    doc = QTextDocument()
    doc.setDefaultFont(QFont("Microsoft YaHei UI", 10))
    doc.setHtml(build_report_html(detail))
    doc.print_(printer)

    if not target.exists():
        raise ReportExportError(f"PDF 生成失败：未找到输出文件 {target}")
    return str(target)


def build_default_filename(started_at: str = "") -> str:
    """根据练习开始时间生成默认文件名。

    Args:
        started_at: ISO 时间串（如 ``2026-01-15T10:30:00``）。

    Returns:
        形如 ``CalcStar成绩单_20260115-1030.pdf`` 的文件名；
        时间信息不足时返回不含时间戳的默认名。
    """
    digits = "".join(ch for ch in str(started_at) if ch.isdigit())
    if len(digits) >= 12:
        return f"CalcStar成绩单_{digits[:8]}-{digits[8:12]}.pdf"
    return "CalcStar成绩单.pdf"
