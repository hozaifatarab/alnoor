"""تخطيط الشاشات: الترويسة، قائمة التنقّل، بطاقات المؤشرات، التنبيهات."""
from __future__ import annotations

from html import escape
from typing import Any, Sequence

from pywebio.output import (
    put_buttons,
    put_collapse,
    put_html,
    put_markdown,
    put_row,
    put_scope,
    put_text,
    use_scope,
)
from pywebio.session import go_app, set_env

from core import config
from core.repos import settings as settings_repo

# عناصر القائمة الرئيسية (تُفلتر حسب صلاحية المستخدم)
# (معرّف التطبيق, العنوان, الصلاحية المطلوبة)
NAV_ITEMS: list[tuple[str, str, str]] = [
    ("dashboard", "لوحة المعلومات", config.PERM_DASHBOARD),
    ("attendance_scan", "تسجيل الحضور بـ QR", config.PERM_ATTENDANCE),
    ("attendance", "الحضور والغياب", config.PERM_ATTENDANCE),
    ("grades", "الدرجات", config.PERM_GRADES),
    ("finance", "المالية", config.PERM_FINANCE),
    ("student_cards", "🔒 بطاقات الطلاب", config.PERM_STUDENT_CARDS),
    ("id_cards", "🆔 توليد بطاقة QR", config.PERM_STUDENT_CARDS),
    ("students", "الطلاب", config.PERM_STUDENTS),
    ("teachers", "المعلمون", config.PERM_TEACHERS),
    ("academic", "البنية الأكاديمية", config.PERM_ACADEMIC),
    ("classes", "الفصول", config.PERM_ACADEMIC),
    ("subjects", "المواد", config.PERM_ACADEMIC),
    ("enrollments", "التسجيل", config.PERM_ENROLLMENTS),
    ("assignments", "الإسناد التدريسي", config.PERM_ACADEMIC),
    ("users", "المستخدمون", config.PERM_USERS),
    ("people", "تسجيل طالب/معلّم", config.PERM_USERS),
    ("settings", "الإعدادات", config.PERM_SETTINGS),
]

ACCOUNT_ITEM = ("my_account", "حسابي", None)

# تجميع القائمة في مجموعات منطقية (عنوان المجموعة -> معرّفات التطبيقات).
# المجموعة التي تحوي الصفحة النشطة تُفتح تلقائياً؛ البقية مطويّة.
NAV_GROUPS: list[tuple[str, list[str]]] = [
    ("🏠 الرئيسية", ["dashboard"]),
    ("📋 الحضور والدرجات", ["attendance_scan", "attendance", "grades"]),
    ("🪪 البطاقات", ["student_cards", "id_cards"]),
    ("👥 الأشخاص", ["students", "teachers"]),
    ("🎓 البنية الأكاديمية", ["academic", "classes", "subjects", "enrollments", "assignments"]),
    ("⚙️ النظام", ["finance", "users", "people", "settings", "my_account"]),
]


def escape_html(value: Any) -> str:
    """تحويل قيمة غير موثوقة إلى نص آمن داخل HTML."""
    return escape(str(value), quote=True)


def nav_items_for(user: dict[str, Any] | None) -> list[tuple[str, str, str]]:
    role = (user or {}).get("role")
    items = [item for item in NAV_ITEMS if config.can(role, item[2])]
    items.append(ACCOUNT_ITEM)  # type: ignore[arg-type]
    return items


def page_header(
    user: dict[str, Any] | None,
    active: str | None = None,
    subtitle: str | None = None,
    institution: str | None = None,
) -> None:
    """شريط جانبي على اليسار + عنوان الصفحة داخل المحتوى."""
    institution = institution or settings_repo.institution_name()
    title = institution if not subtitle else f"{subtitle} | {institution}"
    set_env(title=title, output_animation=False)
    _sidebar(user, active, institution)
    if subtitle:
        put_html(f'<div class="inst-pagebar">{escape_html(subtitle)}</div>')


def _sidebar(
    user: dict[str, Any] | None, active: str | None, institution: str
) -> None:
    """شريط تنقّل جانبي احترافي على اليسار (HTML خالص، بلا أزرار PyWebIO).

    الروابط عادية ``<a href="?app=...">`` تعمل لأن الجلسة محفوظة في كوكي
    موقّع (``inst_auth``) يُرسل مع كل طلب. الخروج وحده يحتاج إجراءً خادمياً،
    لذا يشير إلى مسار ``?app=logout`` المستقل.
    """
    allowed = {app_name: label for app_name, label, _perm in nav_items_for(user)}
    label_of = {app_name: label for app_name, label, _perm in NAV_ITEMS}
    label_of[ACCOUNT_ITEM[0]] = ACCOUNT_ITEM[1]

    parts = ['<nav class="inst-sidebar" aria-label="قائمة التنقّل">']
    parts.append(
        '<a class="sb-brand" href="?app=dashboard">'
        f'<div class="sb-brand-title">{escape_html(institution)}</div>'
        '<div class="sb-brand-sub">نظام إدارة المؤسسة</div></a>'
    )
    parts.append('<div class="sb-nav">')

    for group_title, app_ids in NAV_GROUPS:
        links: list[str] = []
        for app_id in app_ids:
            if app_id not in allowed:
                continue
            is_active = " active" if active == app_id else ""
            links.append(
                f'<a class="sb-link{is_active}" href="?app={app_id}">'
                f"{escape_html(allowed[app_id])}</a>"
            )
        if not links:
            continue
        parts.append('<div class="sb-group">')
        parts.append(f'<div class="sb-group-title">{escape_html(group_title)}</div>')
        parts.extend(links)
        parts.append("</div>")

    parts.append("</div>")  # /sb-nav

    # تذييل المستخدم + خروج
    parts.append('<div class="sb-foot">')
    if user:
        parts.append(f'<div class="sb-user-name">{escape_html(user["full_name"])}</div>')
        parts.append(
            f'<div class="sb-user-role">{config.role_label(user["role"])}</div>'
        )
    parts.append('<a class="sb-link sb-logout" href="?app=logout">⬅️ خروج</a>')
    parts.append("</div>")  # /sb-foot
    parts.append("</nav>")

    put_html("".join(parts))


def _nav_bar(user: dict[str, Any] | None, active: str | None) -> None:
    """(مهجورة) استُبدلت بالشريط الجانبي ``_sidebar`` — تُبقي للتوافق فقط."""
    _sidebar(user, active, settings_repo.institution_name())


def alert(message: str, kind: str = "info") -> None:
    """تنبيه ملوّن داخل الصفحة (بديل الرسائل النصية الجافة)."""
    colors = {
        "info": ("#eaf4ff", "#1a6ea8"),
        "success": ("#e5f6ee", "#1e7a4c"),
        "warn": ("#fdf1e2", "#a86416"),
        "error": ("#fbe9e7", "#b3372a"),
    }
    background, color = colors.get(kind, colors["info"])
    put_html(
        f'<div style="background:{background};color:{color};border-radius:8px;'
        f'padding:8px 12px;margin:6px 0;font-size:14px">{escape_html(message)}</div>'
    )


def section(title: str, hint: str | None = None) -> None:
    put_html(f'<div class="section-title">{escape_html(title)}</div>')
    if hint:
        put_html(f'<div class="section-hint">{escape_html(hint)}</div>')


def kpi_cards(cards: Sequence[dict[str, Any]]) -> None:
    """بطاقات مؤشرات: كل عنصر {label, value, kind?, hint?}."""
    html = ['<div class="kpi-grid">']
    for card in cards:
        kind = card.get("kind") or ""
        hint = card.get("hint") or ""
        html.append(
            f'<div class="kpi-card {escape_html(kind)}">'
            f'<div class="kpi-label">{escape_html(card.get("label", ""))}</div>'
            f'<div class="kpi-value">{escape_html(card.get("value", "—"))}</div>'
            f'<div class="kpi-label">{escape_html(hint)}</div>'
            "</div>"
        )
    html.append("</div>")
    put_html("".join(html))


def card(content_markdown: str, title: str | None = None) -> None:
    if title:
        section(title)
    put_html('<div class="inst-card">')
    put_markdown(content_markdown, lstrip=True)
    put_html("</div>")


def back_home() -> None:
    put_row([put_buttons([{"label": "العودة للوحة المعلومات", "value": "dashboard", "color": "primary"}],
                         onclick=lambda value: go_app(value, new_window=False), small=True)])


def scope_row(scope_name: str) -> None:
    put_scope(scope_name)


def footer(extra: str = "") -> None:
    from core import config as _config

    text = f"{_config.APP_SHORT} — الحضور والدرجات"
    if extra:
        text = f"{text} | {extra}"
    put_html(f'<div class="inst-footer">{escape_html(text)}</div>')


def centered_notice(title: str, message: str, kind: str = "info") -> None:
    """شاشة رسالة مركّزة (لحالات عدم الصلاحية أو الخطأ)."""
    put_html('<div class="inst-card" style="text-align:center;padding:26px">')
    put_html(f'<div class="section-title">{escape_html(title)}</div>')
    alert(message, kind)
    put_html("</div>")
    back_home()


def with_scope(name: str) -> Any:
    """اختصار لفتح نطاق تحديث (مفيد في التحديث الجزئي لاحقاً)."""
    return use_scope(name, clear=True)


def plain(text: str) -> None:
    put_text(text)
