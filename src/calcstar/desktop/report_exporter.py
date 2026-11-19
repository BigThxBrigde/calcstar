"""成绩单导出器（desktop 层）。

把 services.report_service 构建的成绩单 HTML 用 QTextDocument 同步排版
为 A4 纵向 PDF 或宽幅 PNG 图片（本地生成，不请求网络资源，不启动第二
渲染进程/离屏页面，避免卡死与崩溃）。

由 desktop.window 注入到 bridge（bridge → desktop 单向依赖，
接口在 bridge._ReportExporter 中定义）。
"""

from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import QMarginsF, Qt
from PyQt5.QtGui import (
    QColor,
    QFont,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QTextDocument,
)
from PyQt5.QtPrintSupport import QPrinter

from calcstar.services.report_service import build_report_html

#: 支持的导出格式（前端 format 参数与默认文件名后缀共用）
SUPPORTED_FORMATS = ("pdf", "png")
_PNG_DPI = 96.0


def normalize_format(fmt: str) -> str:
    """归一化导出格式；未知格式抛 :class:`ReportExportError`。"""
    value = str(fmt or "pdf").strip().lower().lstrip(".")
    if value not in SUPPORTED_FORMATS:
        raise ReportExportError(f"不支持的导出格式：{fmt}（仅支持 pdf / png）")
    return value


class ReportExportError(RuntimeError):
    """成绩单导出失败（含生成结果缺失等异常情况）。"""


def _ensure_suffix(target: Path, fmt: str) -> Path:
    """用户未输入扩展名时补齐目标格式后缀。"""
    if target.suffix.lower() != f".{fmt}":
        return target.with_name(target.name + f".{fmt}")
    return target


def _make_document(detail: dict, width: float | None = None) -> QTextDocument:
    """构建成绩单富文本文档；PNG 导出时指定像素宽度。"""
    doc = QTextDocument()
    doc.setDefaultFont(QFont("Microsoft YaHei UI", 10))
    if width is not None:
        doc.setTextWidth(width)
    doc.setHtml(build_report_html(detail))
    return doc


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
    target = _ensure_suffix(Path(target_path).expanduser().resolve(), "pdf")
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

    doc = _make_document(detail)
    doc.print_(printer)

    if not target.exists():
        raise ReportExportError(f"PDF 生成失败：未找到输出文件 {target}")
    return str(target)


def export_report_png(detail: dict, target_path: str) -> str:
    """把会话明细导出为单张 PNG 图片（宽幅长图，题目全部收录）。

    Args:
        detail: ``data.repositories.get_session_detail`` 返回的会话字典。
        target_path: 目标 PNG 文件路径（含文件名）。

    Returns:
        实际写入的 PNG 绝对路径字符串。

    Raises:
        ReportExportError: 图片写入失败。
    """
    target = _ensure_suffix(Path(target_path).expanduser().resolve(), "png")
    target.parent.mkdir(parents=True, exist_ok=True)

    width_px = round(210.0 / 25.4 * _PNG_DPI)
    doc = _make_document(detail, width=float(width_px))
    height_px = max(1, int(doc.size().height()) + 16)
    image = QImage(width_px, height_px, QImage.Format_ARGB32)
    image.fill(QColor("white"))

    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        doc.drawContents(painter)
    finally:
        painter.end()

    if not image.save(str(target), "PNG"):
        raise ReportExportError(f"PNG 生成失败：无法写入 {target}")
    return str(target)


def export_report(detail: dict, target_path: str, fmt: str = "pdf") -> str:
    """按格式导出成绩单；默认 PDF，支持 ``pdf`` / ``png``。"""
    format_key = normalize_format(fmt)
    if format_key == "png":
        return export_report_png(detail, target_path)
    return export_report_pdf(detail, target_path)


def build_default_filename(started_at: str = "", fmt: str = "pdf") -> str:
    """根据练习开始时间生成默认文件名。

    Args:
        started_at: ISO 时间串（如 ``2026-01-15T10:30:00``）。
        fmt: 导出格式，决定文件名后缀。

    Returns:
        形如 ``CalcStar成绩单_20260115-1030.pdf`` 的文件名；
        时间信息不足时返回不含时间戳的默认名。
    """
    format_key = normalize_format(fmt)
    digits = "".join(ch for ch in str(started_at) if ch.isdigit())
    if len(digits) >= 12:
        return f"CalcStar成绩单_{digits[:8]}-{digits[8:12]}.{format_key}"
    return f"CalcStar成绩单.{format_key}"
