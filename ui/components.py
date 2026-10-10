"""مكوّنات واجهة قابلة لإعادة الاستخدام: الجداول، النماذج، التأكيد، معالجة الأخطاء."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Sequence

from pywebio.input import actions, input_group
from pywebio.output import (
    clear_scope,
    popup,
    put_buttons,
    put_error,
    put_html,
    put_table,
    put_text,
    toast,
    use_scope,
)

from core.exceptions import AppError
from ui.layout import escape_html

logger = logging.getLogger(__name__)

CHIP_KINDS = {"ok": "chip-ok", "warn": "chip-warn", "bad": "chip-bad", "muted": "chip-muted"}


def chip(text: Any, kind: str = "muted") -> str:
    """شريحة حالة ملوّنة (تُستخدم داخل خلايا الجداول)."""
    css = CHIP_KINDS.get(kind, "chip-muted")
    return f'<span class="chip {css}">{escape_html(text)}</span>'


def table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    empty_message: str = "لا توجد بيانات لعرضها",
) -> None:
    """جدول بيانات موحّد الشكل مع رسالة عند عدم وجود بيانات."""
    if not rows:
        put_html(f'<div class="section-hint">{escape_html(empty_message)}</div>')
        return
    put_table([list(headers)] + [list(row) for row in rows])


def kv_table(pairs: Sequence[tuple[str, Any]]) -> None:
    """جدول تفاصيل (مفتاح/قيمة) لعرض ملف عنصر."""
    rows = [[label, "" if value is None else str(value)] for label, value in pairs]
    table(["الحقل", "القيمة"], rows)


def status_chip_for_status(status: str) -> str:
    mapping = {
        "منتظم": "ok",
        "متخرج": "muted",
        "منسحب": "bad",
        "موقوف": "warn",
        "مسجّل": "ok",
        "منقول": "warn",
        "فعال": "ok",
        "معطّل": "bad",
    }
    return chip(status, mapping.get(status, "muted"))


@contextmanager
def error_boundary(context: str = "") -> Iterator[None]:
    """حدود معالجة الأخطاء: تحويل استثناءات النظام إلى رسائل عربية واضحة."""
    try:
        yield
    except AppError as exc:
        logger.warning("خطأ متوقع%s: %s", f" في {context}" if context else "", exc)
        put_error(f"⚠ {exc.user_message}")
    except Exception as exc:  # pragma: no cover - حماية نهائية
        logger.exception("خطأ غير متوقع%s", f" في {context}" if context else "")
        put_error("حدث خطأ غير متوقع، تم تسجيله في ملف السجلات")


def toast_ok(message: str) -> None:
    toast(message, duration=2, position="center", color="#1e7a4c")


_PASSWORD_TOGGLE_CSS = """
<style>
.pw-field-wrap { position: relative; display: block; width: 100%; }
.pw-field-wrap input[type="password"], .pw-field-wrap input[data-pw-visible] { padding-left: 40px !important; }
.pw-toggle-btn {
    position: absolute; left: 6px; top: 50%; transform: translateY(-50%);
    z-index: 5; background: transparent; border: none; cursor: pointer;
    font-size: 17px; line-height: 1; padding: 4px 6px; color: #475569;
    user-select: none;
}
.pw-toggle-btn:hover { color: #0f6e5c; }
</style>
"""

_PASSWORD_TOGGLE_JS = """
(function () {
    if (window.__pwToggleBound) { return; }
    window.__pwToggleBound = true;
    function decorate(field) {
        if (field.dataset && field.dataset.pwDecorated) { return; }
        if (field.dataset) { field.dataset.pwDecorated = '1'; }
        var wrap = document.createElement('div');
        wrap.className = 'pw-field-wrap';
        field.parentNode.insertBefore(wrap, field);
        wrap.appendChild(field);
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.setAttribute('data-pw-toggle', 'off');
        btn.className = 'pw-toggle-btn';
        btn.textContent = '\\u{1F441}';
        btn.title = 'إظهار كلمة المرور';
        wrap.appendChild(btn);
    }
    function scan() {
        document.querySelectorAll('input[type="password"], input[data-pw-visible="1"]').forEach(decorate);
    }
    if (window.MutationObserver) {
        new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
    }
    scan();
    var tries = 0;
    var iv = setInterval(function () { scan(); if (++tries > 40) { clearInterval(iv); } }, 400);
    document.addEventListener('click', function (ev) {
        var btn = ev.target && ev.target.closest ? ev.target.closest('[data-pw-toggle]') : null;
        if (!btn) { return; }
        ev.preventDefault();
        var wrap = btn.parentNode;
        var field = wrap ? wrap.querySelector('input') : null;
        if (!field) { return; }
        var show = btn.getAttribute('data-pw-toggle') !== 'on';
        field.type = show ? 'text' : 'password';
        field.setAttribute('data-pw-visible', show ? '1' : '0');
        btn.setAttribute('data-pw-toggle', show ? 'on' : 'off');
        btn.textContent = show ? '\\u{1F648}' : '\\u{1F441}';
        btn.title = show ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور';
    });
})();
"""


def password_toggle_hint() -> None:
    """حقن زر إظهار/إخفاء كلمة المرور *داخل* حقل كلمة المرور نفسه.

    يُغلّف كل ``input[type=password]`` في الصفحة ويضع أيقونة عين داخله على
    اليسار، فتنقلب بين النقاط والنص عند الضغط. يناسب الدخول وتغيير كلمة
    المرور وإدارة المستخدمين — ويعمل عبر JS خالص داخل المتصفح.
    """
    from pywebio.session import run_js

    put_html(_PASSWORD_TOGGLE_CSS)
    run_js(_PASSWORD_TOGGLE_JS)



def toast_error(message: str) -> None:
    toast(message, duration=3, position="center", color="#b3372a")


def toast_warn(message: str) -> None:
    toast(message, duration=2, position="center", color="#a86416")


def form_modal(
    title: str,
    fields: Sequence[dict[str, Any]],
    size: str = "normal",
    help_text: str | None = None,
    cancelable: bool = True,
) -> dict[str, Any] | None:
    """نموذج داخل نافذة منبثقة، يُعيد بيانات النموذج أو None عند الإلغاء."""
    if not fields:
        return {}
    with popup(title, size=size):
        if help_text:
            put_html(f'<div class="section-hint">{escape_html(help_text)}</div>')
        if any(f.get("type") == "password" for f in fields):
            password_toggle_hint()
        data = input_group("", list(fields), cancelable=cancelable)
        if data is None:
            return None
        return data


def confirm(message: str, confirm_label: str = "تأكيد", cancel_label: str = "إلغاء") -> bool:
    """تأكيد إجراء حساس قبل التنفيذ."""
    answer = actions(
        buttons=[
            {"label": confirm_label, "value": True, "color": "danger"},
            {"label": cancel_label, "value": False, "color": "secondary"},
        ],
        help_text=message,
    )
    return bool(answer)


def ask_choice(
    title: str,
    options: Sequence[dict[str, Any]],
    message: str | None = None,
) -> Any:
    """سؤال متعدد الخيارات داخل نافذة منبثقة (يُعيد قيمة الخيار أو None)."""
    with popup(title):
        if message:
            put_html(f'<div class="section-hint">{escape_html(message)}</div>')
        rows = [list(item.keys()) for item in options]
        table(
            [key for key in options[0].keys()],
            [[item[key] for key in options[0].keys()] for item in options],
        )
        return actions(buttons=[{"label": "إلغاء", "value": None, "color": "secondary"}])


def refresh_scope(scope: str, render: Callable[[], None]) -> None:
    """إعادة رسم نطاق (تحديث جزئي بلا إعادة تحميل الصفحة)."""
    clear_scope(scope)
    with use_scope(scope):
        render()


def pager(
    scope: str,
    total: int,
    page: int,
    page_size: int,
    on_page: Callable[[int], None],
) -> None:
    """ترقيم صفحات بسيط مع أزرار السابق/التالي."""
    pages = max((total + page_size - 1) // page_size, 1)
    first = (page - 1) * page_size + 1 if total else 0
    last = min(page * page_size, total)
    with use_scope(scope, clear=True):
        put_html(
            f'<div class="section-hint">عرض {first}-{last} من {total} سجل — '
            f"صفحة {page} من {pages}</div>"
        )
        if pages <= 1:
            return
        buttons = []
        if page > 1:
            buttons.append({"label": "‹ السابق", "value": page - 1, "color": "secondary"})
        for candidate in _page_window(page, pages):
            buttons.append(
                {
                    "label": str(candidate),
                    "value": candidate,
                    "color": "primary" if candidate == page else "secondary",
                }
            )
        if page < pages:
            buttons.append({"label": "التالي ›", "value": page + 1, "color": "secondary"})
        put_buttons(buttons, onclick=on_page, small=True, outline=True)


def _page_window(page: int, pages: int, window: int = 2) -> list[int]:
    start = max(1, page - window)
    end = min(pages, page + window)
    return list(range(start, end + 1))


def subtitle(text: str) -> None:
    put_text(text)
