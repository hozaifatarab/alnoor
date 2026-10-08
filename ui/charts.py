"""رسوم بيانية خفيفة بـ HTML/CSS (بلا أي تبعيات خارجية)."""
from __future__ import annotations

from typing import Any, Iterable, Sequence

from pywebio.output import put_html

from ui.layout import escape_html, section


def _ratio(value: float, total: float) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, float(value) / float(total)))


def bar_chart(
    title: str,
    data: Sequence[tuple[str, float]],
    total: float | None = None,
    hint: str | None = None,
    kinds: dict[str, str] | None = None,
) -> None:
    """رسم أعمدة أفقية: data = [(التسمية, القيمة), ...]."""
    section(title, hint)
    if not data:
        put_html('<div class="section-hint">لا توجد بيانات لعرضها</div>')
        return
    maximum = total if total is not None else max((value for _label, value in data), default=1)
    html: list[str] = ['<div class="inst-card">']
    for label, value in data:
        ratio = _ratio(value, maximum)
        kind = (kinds or {}).get(label, "")
        html.append(
            f'<div class="bar-row"><span>{escape_html(label)}</span><span>{_fmt(value)}</span></div>'
            f'<div class="bar-wrap"><div class="bar-fill {escape_html(kind)}" style="width:{ratio * 100:.1f}%">'
            "</div></div>"
        )
    html.append("</div>")
    put_html("".join(html))


def progress(label: str, value: float, total: float, kind: str = "") -> None:
    """شريط تقدم مفرد (نسبة السعة أو الحضور)."""
    ratio = _ratio(value, total)
    put_html(
        f'<div class="bar-row"><span>{escape_html(label)}</span><span>{_fmt(value)} / {_fmt(total)} '
        f"({ratio * 100:.0f}%)</span></div>"
        f'<div class="bar-wrap"><div class="bar-fill {escape_html(kind)}" style="width:{ratio * 100:.1f}%">'
        "</div></div>"
    )


def percent_bars(rows: Iterable[dict[str, Any]]) -> None:
    """أشرطة نسب من قواميس {label, value, total, kind}."""
    for row in rows:
        progress(
            str(row.get("label", "")),
            float(row.get("value") or 0),
            float(row.get("total") or 0),
            str(row.get("kind") or ""),
        )


def _fmt(value: float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:,.2f}".rstrip("0").rstrip(".")
