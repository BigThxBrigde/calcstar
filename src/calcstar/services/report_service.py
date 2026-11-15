"""成绩单报告构建服务（services 层）。

由数据层会话明细（``data.repositories.get_session_detail`` 的返回值）
构建一份自包含的成绩单 HTML（内联样式、无外部资源），供桌面层
渲染为 PDF 导出。本模块为纯逻辑，不做任何 IO 与 Qt 依赖。

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

#: 报告页内联样式（A4 纵向打印友好，全部自包含、无外部资源）
_REPORT_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
  color: #3a3a3a;
  padding: 28px 32px;
}
.report-head { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.report-title { font-size: 22px; font-weight: 800; color: #ff8a3d; }
.report-sub { font-size: 12px; color: #9a8f83; margin-bottom: 18px; }
.summary {
  display: flex; flex-wrap: wrap; gap: 10px;
  background: #fff9f2; border: 1px solid #ffe3c8; border-radius: 12px;
  padding: 14px 16px; margin-bottom: 20px;
}
.summary-item { min-width: 128px; }
.summary-label { display: block; font-size: 11px; color: #9a8f83; margin-bottom: 2px; }
.summary-value { font-size: 15px; font-weight: 700; }
.summary-value.pass { color: #2fbf71; }
.summary-value.not-pass { color: #ff5a5f; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { border: 1px solid #eadfd2; padding: 7px 10px; text-align: center; }
th { background: #fff3d6; font-weight: 700; }
td.expr { text-align: left; font-weight: 600; }
tr.wrong td { background: #fff0f0; }
tr.wrong td.user { color: #ff5a5f; font-weight: 700; }
td.correct-user { color: #2fbf71; font-weight: 600; }
.judge { font-weight: 700; }
.judge.ok { color: #2fbf71; }
.judge.bad { color: #ff5a5f; }
.report-foot { margin-top: 16px; font-size: 11px; color: #b3a79a; text-align: center; }
"""


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


def _passed_label(detail: dict) -> tuple[str, str]:
    """会话状态转（标签, css 类）。"""
    if detail.get("status") == "passed" or detail.get("passed"):
        return "已通过", "pass"
    if detail.get("status") == "in_progress":
        return "进行中", ""
    return "未通过", "not-pass"


def _summary_item(label: str, value: str, value_class: str = "") -> str:
    """拼一个概览字段块。"""
    cls = f' class="{value_class}"' if value_class else ""
    return (
        f'<div class="summary-item"><span class="summary-label">{label}</span>'
        f'<span{cls}>{value}</span></div>'
    )


def build_report_html(detail: dict) -> str:
    """把会话明细构建为自包含成绩单 HTML。

    Args:
        detail: ``data.repositories.get_session_detail`` 返回的会话字典
            （含 ``questions`` 逐题列表）。

    Returns:
        完整 HTML 文本（内联样式、UTF-8、无任何外部资源引用）。
    """
    questions = detail.get("questions") or []
    total = int(detail.get("total_count") or len(questions))
    correct = int(detail.get("correct_count") or 0)
    accuracy = round(correct / total * 100) if total > 0 else 0
    passed_label, passed_cls = _passed_label(detail)

    rows: list[str] = []
    for question in questions:
        user_answer = question.get("user_answer")
        is_correct = question.get("is_correct")
        if user_answer is None:
            user_text = "未作答"
        else:
            user_text = str(user_answer)
        row_class = "wrong" if is_correct == 0 else ""
        if is_correct == 1:
            judge = '<span class="judge ok">✔</span>'
            user_cell = f'<td class="user correct-user">{user_text}</td>'
        elif is_correct == 0:
            judge = '<span class="judge bad">✘</span>'
            user_cell = f'<td class="user">{user_text}</td>'
        else:
            judge = "—"
            user_cell = f"<td>{user_text}</td>"
        rows.append(
            f'<tr class="{row_class}">'
            f"<td>{int(question.get('seq', 0)) + 1}</td>"
            f'<td class="expr">{html.escape(str(question.get("expression", "")))}</td>'
            f"{user_cell}"
            f"<td>{question.get('answer', '')}</td>"
            f"<td>{judge}</td>"
            "</tr>"
        )

    summary = "".join(
        [
            _summary_item("练习时间", html.escape(str(detail.get("started_at", "—")))),
            _summary_item("运算类别", _category_label(detail.get("category"))),
            _summary_item("数值范围", f"{detail.get('range_n', '—')} 以内"),
            _summary_item("题量", f"{total} 题"),
            _summary_item("答对", f"{correct} / {total}"),
            _summary_item("正确率", f"{accuracy}%"),
            _summary_item("得分", f"{detail.get('score', '—')} 分"),
            _summary_item(
                "用时", format_duration(detail.get("duration_seconds"))
            ),
            _summary_item("订正轮次", str(detail.get("correction_round", 0))),
            _summary_item("状态", passed_label, passed_cls),
        ]
    )

    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>CalcStar 口算练习成绩单</title><style>{_REPORT_CSS}</style></head><body>"
        '<div class="report-head">'
        '<svg viewBox="0 0 24 24" width="28" height="28" fill="#ff8a3d" aria-hidden="true">'
        '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25'
        'L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>'
        '<span class="report-title">CalcStar 口算练习成绩单</span></div>'
        '<div class="report-sub">本成绩单由 CalcStar 本地生成，可用于存档或发给家长查看</div>'
        f'<div class="summary">{summary}</div>'
        "<table><thead><tr><th>题号</th><th>题目</th><th>你的答案</th>"
        "<th>正确答案</th><th>判定</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        '<div class="report-foot">CalcStar · 小学生口算练习</div>'
        "</body></html>"
    )
