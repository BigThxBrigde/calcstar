"""CalcStar 配置模块。

仅依赖标准库，负责：
- 用户数据目录、数据库文件、前端资源路径的定位；
- 练习参数的运算类别枚举、默认常量定义与合法性校验。
"""

from __future__ import annotations

import os
import sys
from enum import StrEnum
from pathlib import Path


class OperationCategory(StrEnum):
    """练习题目的运算类别枚举。"""

    ADD = "add"
    SUB = "sub"
    ADD_SUB = "add_sub"
    MUL = "mul"
    DIV = "div"
    MUL_DIV = "mul_div"
    MIXED = "mixed"


# ---- 常量默认值 ----

RANGE_PRESETS: tuple[int, ...] = (10, 20, 30, 50, 100)
COUNT_PRESETS: tuple[int, ...] = (20, 50, 100)
DURATION_PRESETS_MINUTES: tuple[int, ...] = (5, 10, 15, 30)
PER_PAGE_PRESETS: tuple[int, ...] = (5, 10, 20)

MIN_RANGE = 1
MAX_RANGE = 999
MIN_COUNT = 1
MAX_COUNT = 200
MIN_DURATION_MINUTES = 1
MAX_DURATION_MINUTES = 180
DEFAULT_RANGE = 10
DEFAULT_COUNT = 20
DEFAULT_PER_PAGE = 10


def get_user_data_dir() -> Path:
    """获取用户数据目录并确保其存在（目录不存在时自动创建）。

    Windows 下使用 ``%APPDATA%\\CalcStar``；APPDATA 环境变量缺失时
    回退到 ``~/.calcstar``。
    """
    appdata = os.environ.get("APPDATA")
    data_dir = Path(appdata) / "CalcStar" if appdata else Path.home() / ".calcstar"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """获取 SQLite 数据库文件路径。

    优先读取环境变量 ``CALCSTAR_DB``，否则使用用户数据目录下的
    ``calcstar.db``。
    """
    env_db = os.environ.get("CALCSTAR_DB")
    return Path(env_db) if env_db else get_user_data_dir() / "calcstar.db"


def get_resource_dir() -> Path:
    """获取前端资源目录（web/）。

    PyInstaller 打包态（``sys.frozen`` 为真）返回解包临时目录下的
    ``web/``；开发态返回仓库根目录的 ``web/``。
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "web"
    return Path(__file__).resolve().parents[2] / "web"


def get_index_html_path() -> Path:
    """获取前端入口页面 index.html 的路径。"""
    return get_resource_dir() / "index.html"


def validate_params(
    category: str,
    range_n: int,
    count: int,
    duration_minutes: int | None,
    per_page: int,
) -> list[str]:
    """校验练习参数，返回错误信息列表（空列表表示参数合法）。

    规则：
    - category 必须是 OperationCategory 的取值之一；
    - range_n 落在 [MIN_RANGE, MAX_RANGE]；
    - count 落在 [MIN_COUNT, MAX_COUNT]；
    - duration_minutes 为 None（不限时）或落在
      [MIN_DURATION_MINUTES, MAX_DURATION_MINUTES]；
    - per_page 属于 PER_PAGE_PRESETS，或至少为 1 且不超过 count。
    """
    errors: list[str] = []

    valid_categories = {member.value for member in OperationCategory}
    if category not in valid_categories:
        errors.append(
            f"运算类别无效：{category}（可选值：{', '.join(valid_categories)}）"
        )

    if not MIN_RANGE <= range_n <= MAX_RANGE:
        errors.append(
            f"数值范围超出限制：{range_n}（应在 {MIN_RANGE}~{MAX_RANGE} 之间）"
        )

    if not MIN_COUNT <= count <= MAX_COUNT:
        errors.append(
            f"题目数量超出限制：{count}（应在 {MIN_COUNT}~{MAX_COUNT} 之间）"
        )

    if duration_minutes is not None and not (
        MIN_DURATION_MINUTES <= duration_minutes <= MAX_DURATION_MINUTES
    ):
        errors.append(
            f"限时分钟数超出限制：{duration_minutes}"
            f"（应为 None 或在 {MIN_DURATION_MINUTES}~{MAX_DURATION_MINUTES} 之间）"
        )

    if per_page not in PER_PAGE_PRESETS and not 1 <= per_page <= count:
        errors.append(
            f"每页题数无效：{per_page}"
            f"（应属于 {PER_PAGE_PRESETS}，或满足 1 ≤ 每页题数 ≤ 题目数量）"
        )

    return errors
