"""CalcStar 桌面壳。

基于 QWebEngineView 的主窗口：加载本地 web/index.html 页面，
并通过 QWebChannel 注册后端桥接对象（bridge）供前端调用。
单窗口应用，关闭主窗口后 QApplication 随之结束、进程退出。
"""

import sys

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QIcon
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineProfile, QWebEngineView
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow

from calcstar.config import get_icon_path, get_index_html_path


def _make_report_exporter(window: QMainWindow):
    """构造成绩单导出器：按格式弹另存为对话框后本地同步渲染。

    供 desktop 注入 bridge；用户取消对话框返回 None（不视为错误）。
    """

    def exporter(detail: dict, suggested_filename: str, fmt: str = "pdf") -> str | None:
        from calcstar.desktop.report_exporter import (
            ReportExportError,
            build_default_filename,
            export_report,
            normalize_format,
        )

        format_key = normalize_format(fmt)
        default_name = suggested_filename or build_default_filename(detail, format_key)
        filters = {
            "pdf": "PDF 文件 (*.pdf)",
            "png": "PNG 图片 (*.png)",
        }
        target, _ = QFileDialog.getSaveFileName(
            window,
            "保存成绩单",
            default_name,
            f"{filters[format_key]};;所有文件 (*.*)",
        )
        if not target:
            return None
        try:
            return export_report(detail, target, format_key)
        except ReportExportError as exc:
            raise RuntimeError(str(exc)) from exc

    return exporter


class MainWindow(QMainWindow):
    """主窗口：内嵌 QWebEngineView 加载页面，并注册 QWebChannel 桥接。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CalcStar · 口算练习")
        self.resize(1024, 720)
        self.setMinimumSize(960, 640)

        # 应用图标：任务栏/标题栏/窗口均使用内置 ico（缺席时静默跳过）
        icon_path = get_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Profile 须保存在 self 上，防止被垃圾回收导致页面崩溃
        self._profile = QWebEngineProfile(self)
        self._page = QWebEnginePage(self._profile, self)
        self._view = QWebEngineView(self)
        self._view.setPage(self._page)
        self.setCentralWidget(self._view)

        self._channel = QWebChannel(self)
        self._page.setWebChannel(self._channel)

        # 桥接对象由 calcstar.bridge.api 提供，缺席时跳过注册
        self._bridge = None
        try:
            from calcstar.bridge.api import create_bridge
        except ImportError:
            create_bridge = None

        if create_bridge is not None:
            try:
                self._bridge = create_bridge(
                    report_exporter=_make_report_exporter(self)
                )
            except Exception:
                self._bridge = None
            if self._bridge is not None:
                self._channel.registerObject("bridge", self._bridge)

        self._view.load(QUrl.fromLocalFile(str(get_index_html_path())))


def main() -> int:
    """应用入口：创建 QApplication 与主窗口并进入事件循环。"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec_()
