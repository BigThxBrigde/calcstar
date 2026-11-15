"""设置持久化存储（data 层）。

把设置页的全部参数以 JSON 形式保存在用户数据目录
（``%APPDATA%\\CalcStar\\settings.json``），应用重启后自动恢复。
仅依赖标准库；未知字段一律丢弃，文件缺失或损坏时返回空配置。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

from calcstar.config import get_user_data_dir

#: 设置文件名（位于用户数据目录下）
SETTINGS_FILENAME = "settings.json"

#: 允许持久化的设置字段白名单（与设置页 collectConfig 输出一致）
_VALID_KEYS = frozenset(
    {
        "category",
        "range_n",
        "count",
        "duration_minutes",
        "allow_negative",
        "include_parentheses",
        "per_page",
        "operand_count",
        "blank_position",
    }
)

_PathLike = Union[str, Path]


def get_settings_path() -> Path:
    """获取设置文件路径（用户数据目录下 settings.json）。"""
    return get_user_data_dir() / SETTINGS_FILENAME


def load_settings(path: Optional[_PathLike] = None) -> dict:
    """读取设置；文件缺失、损坏或非对象时返回空字典。

    Args:
        path: 设置文件路径；None 时使用用户数据目录默认位置。
    """
    settings_path = Path(path) if path is not None else get_settings_path()
    if not settings_path.exists():
        return {}
    try:
        with open(settings_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {key: data[key] for key in _VALID_KEYS if key in data}


def save_settings(settings: dict, path: Optional[_PathLike] = None) -> None:
    """保存设置（白名单过滤后写 JSON）。

    先写临时文件再原子替换，避免写入中途异常导致配置损坏。

    Args:
        settings: 待保存的设置字典（未知字段被忽略）。
        path: 设置文件路径；None 时使用用户数据目录默认位置。
    """
    payload = {key: settings[key] for key in _VALID_KEYS if key in settings}
    settings_path = Path(path) if path is not None else get_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(settings_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp_name, settings_path)
    except BaseException:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise
