"""成绩单报告构建服务（services 层）。

由数据层会话明细（``data.repositories.get_session_detail`` 的返回值）
构建一份成绩单 HTML，供桌面层经 QTextDocument 排版导出 PDF。

使用 Qt 富文本引擎支持的 HTML 子集（表格 + 内联属性，不依赖
CSS 类/flex/外部资源），全程离线、同步生成。

分层规则：services → domain/data。
"""

from __future__ import annotations

import html
from typing import Optional

#: 运算类别 -> 中文标签（与前端 CATEGORY_LABELS 保持一致）
CATEGORY_LABELS: dict[str, str] = {
    "add": "加法",
    "sub": "减法",
    "add_sub": "加减法",
    "mul": "乘法",
    "div": "除法",
    "mul_div": "乘除法",
    "mixed": "四则混合",
}

#: 报告配色（与界面规范一致）
_COLOR_INK = "#3A3A3A"
_COLOR_ORANGE = "#FF8A3D"
_COLOR_GREEN = "#2FBF71"
_COLOR_RED = "#FF5A5F"
_COLOR_MUTED = "#9A8F83"
_COLOR_BG_SUMMARY = "#FFF9F2"
_COLOR_BG_HEAD = "#FFF3D6"
_COLOR_BG_WRONG = "#FFF0F0"


def format_duration(seconds: Optional[float]) -> str:
    """把秒数格式化为中文时长文本（如 ``1分46秒``）。"""
    total = max(0, int(seconds or 0))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}小时{minutes}分{secs}秒"
    if minutes > 0:
        return f"{minutes}分{secs:02d}秒"
    return f"{secs}秒"


def _category_label(category: Optional[str]) -> str:
    """类别代码转中文标签，未知值原样展示。"""
    if not category:
        return "未知"
    return CATEGORY_LABELS.get(category, category)


def format_datetime(iso_text: Optional[str]) -> str:
    """把 ISO 时间串格式化为 ``YYYY-MM-DD HH:MM``；空值返回占位符。"""
    if not iso_text:
        return "—"
    text = str(iso_text).replace("T", " ")
    return text[:16] if len(text) >= 16 else text


def _passed_label(detail: dict) -> tuple[str, str]:
    """会话状态转（标签, 颜色）。"""
    if detail.get("status") == "passed" or detail.get("passed"):
        return "已通过", _COLOR_GREEN
    if detail.get("status") == "in_progress":
        return "进行中", _COLOR_MUTED
    return "未通过", _COLOR_RED


def _esc(value) -> str:
    """HTML 转义。"""
    return html.escape(str(value))


def _summary_cell(label: str, value: str, color: Optional[str] = None) -> str:
    """拼一个概览单元格（标签 + 加粗值，居中）。"""
    value_html = f'<font color="{color}">{_esc(value)}</font>' if color else _esc(value)
    return (
        f'<td bgcolor="{_COLOR_BG_SUMMARY}" align="center">'
        f'<font color="{_COLOR_MUTED}" size="2">{_esc(label)}</font><br>'
        f"<b>{value_html}</b></td>"
    )


def _question_row(question: dict) -> str:
    """拼一道题的明细行：错题标红背景，对错用 √/× 标记。"""
    user_answer = question.get("user_answer")
    is_correct = question.get("is_correct")
    user_text = "未作答" if user_answer is None else str(user_answer)

    if is_correct == 1:
        row_bg = ""
        user_cell = f'<font color="{_COLOR_GREEN}"><b>{_esc(user_text)}</b></font>'
        judge = f'<font color="{_COLOR_GREEN}"><b>√</b></font>'
    elif is_correct == 0:
        row_bg = f' bgcolor="{_COLOR_BG_WRONG}"'
        user_cell = f'<font color="{_COLOR_RED}"><b>{_esc(user_text)}</b></font>'
        judge = f'<font color="{_COLOR_RED}"><b>×</b></font>'
    else:
        row_bg = ""
        user_cell = _esc(user_text)
        judge = "—"

    return (
        f"<tr{row_bg}>"
        f'<td align="center">{int(question.get("seq", 0)) + 1}</td>'
        f'<td align="left"><b>{_esc(question.get("expression", ""))}</b></td>'
        f'<td align="center">{user_cell}</td>'
        f'<td align="center">{_esc(question.get("answer", ""))}</td>'
        f'<td align="center">{judge}</td>'
        "</tr>"
    )


def build_report_html(detail: dict) -> str:
    """把会话明细构建为成绩单 HTML（Qt 富文本子集）。

    Args:
        detail: ``data.repositories.get_session_detail`` 返回的会话字典
            （含 ``questions`` 逐题列表）。

    Returns:
        HTML 文本（表格布局、内联配色，无外部资源引用）。
    """
    questions = detail.get("questions") or []
    total = int(detail.get("total_count") or len(questions))
    correct = int(detail.get("correct_count") or 0)
    accuracy = round(correct / total * 100) if total > 0 else 0
    passed_label, passed_color = _passed_label(detail)

    summary_cells = [
        _summary_cell("练习时间", format_datetime(detail.get("started_at"))),
        _summary_cell("运算类别", _category_label(detail.get("category"))),
        _summary_cell("数值范围", f"{detail.get('range_n', '—')} 以内"),
        _summary_cell("题量", f"{total} 题"),
        _summary_cell("答对", f"{correct} / {total}"),
        _summary_cell("正确率", f"{accuracy}%"),
        _summary_cell("得分", f"{detail.get('score', '—')} 分"),
        _summary_cell("用时", format_duration(detail.get("duration_seconds"))),
        _summary_cell("订正轮次", detail.get("correction_round", 0)),
        _summary_cell("状态", passed_label, passed_color),
    ]
    row1 = "".join(summary_cells[:5])
    row2 = "".join(summary_cells[5:])

    header = (
        '<tr bgcolor="' + _COLOR_BG_HEAD + '">'
        "<th>题号</th><th>题目</th><th>你的答案</th>"
        "<th>正确答案</th><th>判定</th></tr>"
    )
    rows = "".join(_question_row(q) for q in questions)

    return (
        '<h2 align="left">'
        f'<font color="{_COLOR_ORANGE}">★</font> '
        f'<font color="{_COLOR_INK}">CalcStar 口算练习成绩单</font></h2>'
        f'<p align="left"><font color="{_COLOR_MUTED}" size="2">'
        "本成绩单由 CalcStar 本地生成，可用于存档或发给家长查看</font></p>"
        '<table width="100%" cellspacing="2" cellpadding="6" border="0">'
        f"<tr>{row1}</tr><tr>{row2}</tr></table>"
        "<p>&nbsp;</p>"
        '<table width="100%" cellspacing="0" cellpadding="5" border="0">'
        f"{header}{rows}</table>"
        f'<p align="center"><font color="{_COLOR_MUTED}" size="2">'
        "CalcStar · 小学生口算练习</font></p>"
    )
