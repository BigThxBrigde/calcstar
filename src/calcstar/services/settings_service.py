"""设置服务（services 层）：设置页参数的持久化读写。

持久化位置由 data.settings_store 决定（用户数据目录 settings.json）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from calcstar.data.settings_store import load_settings, save_settings

_PathLike = Union[str, Path]


class SettingsService:
    """设置持久化服务：读取与保存设置页参数。"""

    def __init__(self, settings_path: Optional[_PathLike] = None) -> None:
        """初始化服务。

        Args:
            settings_path: 设置文件路径；None 时使用用户数据目录默认位置。
        """
        self._path = settings_path

    def load(self) -> dict:
        """读取设置；无历史设置时返回空字典。"""
        return load_settings(self._path)

    def save(self, settings: dict) -> None:
        """保存设置（未知字段被忽略，原子写入）。"""
        save_settings(settings, self._path)
