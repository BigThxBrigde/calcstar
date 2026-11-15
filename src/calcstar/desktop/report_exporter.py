"""成绩单 PDF 导出器（desktop 层）。

用离屏 :class:`QWebEnginePage` 加载报告 HTML，等待渲染完成后调用
``printToPdf`` 输出 A4 纵向 PDF。全程本地生成，无网络请求。

依赖 QApplication 事件循环，仅在桌面运行态可用；单元测试不覆盖
本模块（desktop 层当前 0% 覆盖率为既有基线）。
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QEventLoop, QMarginsF, QTimer, QUrl
from PyQt5.QtGui import QPageLayout, QPageSize
from PyQt5.QtWebEngineWidgets import QWebEnginePage

from calcstar.services.report_service import build_report_html

#: 渲染 + 打印总等待超时（毫秒）
_PRINT_TIMEOUT_MS = 30_000


class ReportExportError(RuntimeError):
    """成绩单导出失败（渲染超时或打印失败）。"""


def build_default_filename(detail: dict) -> str:
    """按会话开始时间构造默认文件名，如 ``CalcStar成绩单_20261113-0732.pdf``。"""
    started = str(detail.get("started_at") or "")
    stamp = ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            stamp = datetime.strptime(started, fmt).strftime("%Y%m%d-%H%M")
            break
        except ValueError:
            continue
    if not stamp:
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return f"CalcStar成绩单_{stamp}.pdf"


def export_report_pdf(detail: dict, target_path: str | Path) -> str:  # pragma: no cover
    """把会话明细渲染为 PDF 成绩单并写入目标路径。

    Args:
        detail: ``get_session_detail`` 返回的会话字典（含 questions）。
        target_path: PDF 保存路径（须已确定，另存为弹窗由调用方负责）。

    Returns:
        写入的绝对路径字符串。

    Raises:
        ReportExportError: 渲染或打印失败/超时、文件未落盘时抛出。

    Note:
        依赖 QApplication 与离屏 QtWebEngine 渲染，仅在桌面运行态
        可执行，不纳入单元测试覆盖率。
    """
    target = Path(target_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    # 报告 HTML 写入临时文件后交给离屏页面加载
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".html", prefix="calcstar_report_")
    page: QWebEnginePage | None = None
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(build_report_html(detail))

        loop = QEventLoop()
        state = {"loaded": False, "printed": False}

        def on_load_finished(ok: bool) -> None:
            if not ok:
                loop.quit()
                return
            state["loaded"] = True
            layout = QPageLayout(
                QPageSize(QPageSize.A4),
                QPageLayout.Portrait,
                QMarginsF(12, 12, 12, 12),
            )
            page.printToPdf(str(target), layout)

        def on_pdf_finished(_file_path: str, ok: bool) -> None:
            state["printed"] = ok
            loop.quit()

        page = QWebEnginePage()
        page.loadFinished.connect(on_load_finished)
        page.pdfPrintingFinished.connect(on_pdf_finished)
        # 兜底超时：渲染或打印卡死时唤醒事件循环，事后按 state 判定
        QTimer.singleShot(_PRINT_TIMEOUT_MS, loop.quit)
        page.load(QUrl.fromLocalFile(tmp_name))

        loop.exec_()

        if not state["loaded"]:
            raise ReportExportError("成绩单页面加载失败，请重试")
        if not state["printed"]:
            raise ReportExportError("PDF 生成超时，请重试")
        if not target.exists():
            raise ReportExportError("PDF 文件未写入，请检查保存路径")
        return str(target)
    finally:
        if page is not None:
            page.deleteLater()
        try:
            os.remove(tmp_name)
        except OSError:
            pass
