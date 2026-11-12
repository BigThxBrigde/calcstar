"""应用配置：路径、窗口参数与练习参数的预设/边界枚举。"""

import os
from pathlib import Path

APP_NAME = "CalcStar"

# 窗口
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 720
MIN_WIDTH = 960
MIN_HEIGHT = 640

# 运算类别
CATEGORY_ADD = "add"
CATEGORY_SUB = "sub"
CATEGORY_ADDSUB = "addsub"
CATEGORY_MUL = "mul"
CATEGORY_DIV = "div"
CATEGORY_MULDIV = "muldiv"
CATEGORY_MIXED = "mixed"
CATEGORIES = (
    CATEGORY_ADD,
    CATEGORY_SUB,
    CATEGORY_ADDSUB,
    CATEGORY_MUL,
    CATEGORY_DIV,
    CATEGORY_MULDIV,
    CATEGORY_MIXED,
)
CATEGORY_LABELS = {
    CATEGORY_ADD: "加法",
    CATEGORY_SUB: "减法",
    CATEGORY_ADDSUB: "加减法",
    CATEGORY_MUL: "乘法",
    CATEGORY_DIV: "除法",
    CATEGORY_MULDIV: "乘除法",
    CATEGORY_MIXED: "四则混合运算",
}

# 数值范围：预设 + 边界
RANGE_PRESETS = (10, 20, 30, 50, 100)
MIN_RANGE = 1
MAX_RANGE = 1000

# 题目数量：预设 + 边界
COUNT_PRESETS = (20, 50, 100)
MIN_COUNT = 1
MAX_COUNT = 200

# 限时（分钟）：预设 + 边界，None 表示不限时
TIME_LIMIT_PRESETS = (5, 10, 15, 30)
MIN_TIME_LIMIT = 1
MAX_TIME_LIMIT = 180

# 每页题数
PER_PAGE_PRESETS = (5, 10, 20)
DEFAULT_PER_PAGE = 20


def get_data_dir() -> Path:
    """用户数据目录，可用环境变量 CALCSTAR_DATA_DIR 覆盖（默认 %APPDATA%/CalcStar）。"""
    env_dir = os.environ.get("CALCSTAR_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME


def get_db_path() -> Path:
    """SQLite 数据库路径，可用环境变量 CALCSTAR_DB 覆盖。"""
    env_db = os.environ.get("CALCSTAR_DB")
    if env_db:
        return Path(env_db)
    return get_data_dir() / "calcstar.db"
