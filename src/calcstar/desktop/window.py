"""CalcStar 桌面壳。

基于 QWebEngineView 的主窗口：加载本地 web/index.html 页面，
并通过 QWebChannel 注册后端桥接对象（bridge）供前端调用。
单窗口应用，关闭主窗口后 QApplication 随之结束、进程退出。
"""

import sys

from PyQt5.QtCore import QUrl
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineProfile, QWebEngineView
from PyQt5.QtWidgets import QApplication, QMainWindow

from calcstar.config import get_index_html_path


class MainWindow(QMainWindow):
    """主窗口：内嵌 QWebEngineView 加载页面，并注册 QWebChannel 桥接。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CalcStar · 口算练习")
        self.resize(1024, 720)
        self.setMinimumSize(960, 640)

        # Profile 须保存在 self 上，防止被垃圾回收导致页面崩溃
        self._profile = QWebEngineProfile(self)
        self._page = QWebEnginePage(self._profile, self)
        self._view = QWebEngineView(self)
        self._view.setPage(self._page)
        self.setCentralWidget(self._view)

        self._channel = QWebChannel(self)
        self._page.setWebChannel(self._channel)

        # 桥接对象由 calcstar.bridge.api 提供（后续任务实现），缺席时跳过注册
        self._bridge = None
        try:
            from calcstar.bridge.api import create_bridge
        except ImportError:
            create_bridge = None

        if create_bridge is not None:
            try:
                self._bridge = create_bridge()
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
