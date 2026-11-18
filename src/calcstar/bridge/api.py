"""桥接层：把服务层 API 暴露为 QWebChannel 可调用的 JSON 接口。

每个方法接收前端传入的 JSON 字符串、返回 JSON 字符串，统一响应
信封：成功为 {"ok": true, "data": ...}，任何异常为
{"ok": false, "error": 错误信息}。

分层规则：bridge → services（不直接 import domain/data）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional, Union

from PyQt5.QtCore import QObject, pyqtSlot

from calcstar.services.practice_service import PracticeService
from calcstar.services.settings_service import SettingsService
from calcstar.services.stats_service import StatsService

_DBPath = Union[str, Path]
#: 导出器签名：(会话明细, 建议文件名) -> 保存路径；用户取消返回 None
_ReportExporter = Callable[[dict, str], Optional[str]]


class CalcStarBridge(QObject):
    """前端桥接对象：JSON 字符串进、JSON 字符串出。

    内部持有 PracticeService 与 StatsService 各一个实例（服务单例），
    所有槽方法经统一信封返回，异常不外抛。
    """

    def __init__(
        self,
        practice_service: Optional[PracticeService] = None,
        stats_service: Optional[StatsService] = None,
        settings_service: Optional[SettingsService] = None,
        report_exporter: Optional[_ReportExporter] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        """初始化桥接对象。

        Args:
            practice_service: 练习服务实例；None 时按默认数据库路径创建。
            stats_service: 统计服务实例；None 时按默认数据库路径创建。
            settings_service: 设置服务实例；None 时使用默认设置文件路径。
            report_exporter: 成绩单 PDF 导出器（desktop 层注入）；None 时
                导出接口返回"不支持"错误。
            parent: Qt 父对象。
        """
        super().__init__(parent)
        self._practice = (
            practice_service if practice_service is not None else PracticeService()
        )
        self._stats = stats_service if stats_service is not None else StatsService()
        self._settings = (
            settings_service if settings_service is not None else SettingsService()
        )
        self._report_exporter = report_exporter

    # ---- 内部工具 ----

    @staticmethod
    def _parse_payload(payload: str) -> dict:
        """解析 JSON 字符串并要求其为对象（dict）。"""
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("payload 必须是 JSON 对象")
        return data

    @staticmethod
    def _respond(callback) -> str:
        """统一响应信封：成功 {"ok": True, "data": ...}，异常 {"ok": False, "error": ...}。"""
        try:
            return json.dumps({"ok": True, "data": callback()}, ensure_ascii=False)
        except Exception as exc:  # 统一兜底：任何业务/解析异常都不外抛
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    # ---- 练习流程 ----

    @pyqtSlot(str, result=str)
    def create_practice(self, payload: str) -> str:
        """创建练习：payload 为参数 JSON（category/range_n/count 等）。"""
        return self._respond(
            lambda: self._practice.create_practice(self._parse_payload(payload))
        )

    @pyqtSlot(str, result=str)
    def submit_practice(self, payload: str) -> str:
        """提交作答：payload 为 {session_id, answers, duration_seconds}。

        answers 的键（题号）在前端为字符串，此处统一转为 int。
        """
        def run() -> dict:
            data = self._parse_payload(payload)
            answers = {
                int(seq): answer
                for seq, answer in (data.get("answers") or {}).items()
            }
            return self._practice.submit_practice(
                int(data["session_id"]),
                answers,
                float(data.get("duration_seconds") or 0.0),
            )

        return self._respond(run)

    @pyqtSlot(str, result=str)
    def submit_correction(self, payload: str) -> str:
        """提交订正：payload 为 {session_id, corrections}；题号键转 int。"""
        def run() -> dict:
            data = self._parse_payload(payload)
            corrections = {
                int(seq): int(answer)
                for seq, answer in (data.get("corrections") or {}).items()
            }
            return self._practice.submit_correction(
                int(data["session_id"]), corrections
            )

        return self._respond(run)

    @pyqtSlot(str, result=str)
    def reset_practice(self, payload: str) -> str:
        """重做历史练习：payload 为 {session_id}；不新建记录。

        将该会话重置为未作答状态（题目保持原卷），返回结构同
        create_practice；提交后原地更新同一条历史记录。会话不存在
        返回 ok=False。
        """
        def run() -> dict:
            data = self._parse_payload(payload)
            return self._practice.reset_practice(int(data["session_id"]))

        return self._respond(run)

    @pyqtSlot(str, result=str)
    def create_practice_from_wrong_book(self, payload: str) -> str:
        """从错题本创建练习：payload 为参数 JSON（category/count 等）。"""
        return self._respond(
            lambda: self._practice.create_practice_from_wrong_book(
                self._parse_payload(payload)
            )
        )

    # ---- 统计查询 ----

    @pyqtSlot(str, result=str)
    def list_history(self, payload: str) -> str:
        """分页查询历史：payload 为 {page, page_size}（可缺省）。"""
        def run() -> dict:
            data = self._parse_payload(payload)
            return self._stats.list_history(
                int(data.get("page", 1)), int(data.get("page_size", 20))
            )

        return self._respond(run)

    @pyqtSlot(str, result=str)
    def get_session_detail(self, payload: str) -> str:
        """查询会话明细：payload 为 {session_id}；不存在返回 ok=False。"""
        def run() -> dict:
            data = self._parse_payload(payload)
            return self._stats.get_session_detail(int(data["session_id"]))

        return self._respond(run)

    @pyqtSlot(str, result=str)
    def clear_history(self, payload: str) -> str:
        """清空全部练习历史：payload 忽略；返回 {deleted: 会话数}。

        仅删除会话与逐题明细，错题本（wrong_book）保留。
        """
        def run() -> dict:
            self._parse_payload(payload)
            return {"deleted": self._stats.clear_history()}

        return self._respond(run)

    @pyqtSlot(str, result=str)
    def delete_session(self, payload: str) -> str:
        """删除单条练习会话：payload 为 {session_id}；返回 {deleted: true}。

        仅删除该会话与逐题明细，错题本保留；会话不存在返回 ok=False。
        """
        def run() -> dict:
            data = self._parse_payload(payload)
            self._stats.delete_session(int(data["session_id"]))
            return {"deleted": True}

        return self._respond(run)

    @pyqtSlot(str, result=str)
    def list_wrong_book(self, payload: str) -> str:
        """查询错题本：payload 为 {category, order_by}（均可缺省）。"""
        def run() -> list[dict]:
            data = self._parse_payload(payload)
            return self._stats.list_wrong_book(
                category=data.get("category"),
                order_by=data.get("order_by", "wrong_count"),
            )

        return self._respond(run)

    # ---- 设置持久化 ----

    @pyqtSlot(str, result=str)
    def get_settings(self, payload: str) -> str:
        """读取持久化设置：payload 忽略；无历史设置时返回空对象。"""
        def run() -> dict:
            self._parse_payload(payload)
            return self._settings.load()

        return self._respond(run)

    @pyqtSlot(str, result=str)
    def save_settings(self, payload: str) -> str:
        """保存设置页参数：payload 为设置字典（未知字段被忽略）。"""
        def run() -> dict:
            data = self._parse_payload(payload)
            self._settings.save(data)
            return {"saved": True}

        return self._respond(run)

    # ---- 成绩单导出 ----

    @pyqtSlot(str, result=str)
    def export_report_pdf(self, payload: str) -> str:
        """导出本次练习成绩单 PDF：payload 为 {session_id}。

        流程：查会话明细 → 调用 desktop 注入的导出器（内含另存为
        弹窗与离屏渲染）→ 返回 {path}；用户取消对话框返回
        {cancelled: true}，导出器缺席或生成失败返回 ok=False。
        """
        def run() -> dict:
            data = self._parse_payload(payload)
            if self._report_exporter is None:
                raise RuntimeError("当前环境不支持导出成绩单")
            detail = self._stats.get_session_detail(int(data["session_id"]))
            suggested = data.get("filename") or ""
            path = self._report_exporter(detail, suggested)
            if path is None:
                return {"cancelled": True, "path": None}
            return {"cancelled": False, "path": str(path)}

        return self._respond(run)


def create_bridge(
    db_path: Optional[_DBPath] = None,
    settings_service: Optional[SettingsService] = None,
    report_exporter: Optional[_ReportExporter] = None,
) -> CalcStarBridge:
    """桥接对象工厂：创建并返回 :class:`CalcStarBridge`。

    内部按 db_path 各创建一个 PracticeService / StatsService 实例并
    持有于桥接对象内（服务单例）；db_path 为 None 时使用默认数据库
    路径。与 desktop.window 的零参调用 ``create_bridge()`` 兼容。

    Args:
        db_path: 数据库文件路径；None 时使用 config.get_db_path()。
        settings_service: 设置服务实例；None 时使用默认设置文件路径。
        report_exporter: 成绩单 PDF 导出器（desktop 层注入）。
    """
    return CalcStarBridge(
        practice_service=PracticeService(db_path),
        stats_service=StatsService(db_path),
        settings_service=settings_service,
        report_exporter=report_exporter,
    )
