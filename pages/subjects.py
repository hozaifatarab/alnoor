"""شاشة المواد الدراسية: عرض، إضافة، تعديل، تنشيط/إيقاف، حذف."""
from __future__ import annotations

from typing import Any

from pywebio.input import input, input_group, select
from pywebio.output import put_buttons, put_html
from pywebio.pin import pin, put_select
from pywebio.session import go_app

from core import auth
from core.services import subjects_service
from ui import components, layout, options

APP = "subjects"


def subjects() -> None:
    """شاشة إدارة المواد الدراسية."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="المواد الدراسية")
    with components.error_boundary("شاشة المواد"):
        filters = input_group(
            "تصفية",
            [
                select("المرحلة", name="level_id", options=options.levels("الكل"), required=False),
                input("بحث (الاسم/الرمز)", name="search", required=False),
            ],
            cancelable=False,
        )
        level_id = int(filters["level_id"]) if str(filters.get("level_id") or "").isdigit() else None
        rows = subjects_service.list_subjects(
            level_id, (filters.get("search") or "").strip() or None
        )
        _render_table(rows)
        _render_actions(rows)


def _render_table(rows: list[dict[str, Any]]) -> None:
    layout.section("قائمة المواد", f"عدد النتائج: {len(rows)}")
    components.table(
        ["الرمز", "المادة", "المرحلة", "ساعات أسبوعية", "الدرجة العظمى", "الإسناد", "الحالة"],
        [
            [
                row.get("code") or "—",
                row["name"],
                row.get("level_name") or "مشتركة",
                row["weekly_hours"],
                row["max_score"],
                row.get("assignments_count") or 0,
                components.chip(
                    "فعّالة" if row["is_active"] else "موقوفة", "ok" if row["is_active"] else "bad"
                ),
            ]
            for row in rows
        ],
        empty_message="لا توجد مواد مطابقة للتصفية",
    )


def _render_actions(rows: list[dict[str, Any]]) -> None:
    layout.section("إجراءات", "اختر المادة ثم الإجراء المطلوب")
    if rows:
        put_select(
            "subject_pick",
            options=[{"label": row["name"], "value": str(row["id"])} for row in rows],
            label="المادة",
        )
    else:
        put_html('<div class="section-hint">لا توجد مواد لعرض إجراءاتها.</div>')
    put_buttons(
        [
            {"label": "➕ إضافة مادة", "value": "add", "color": "primary"},
            {"label": "✎ تعديل", "value": "edit", "color": "secondary"},
            {"label": "⏻ إيقاف/تنشيط", "value": "toggle", "color": "secondary"},
            {"label": "🗑 حذف", "value": "delete", "color": "danger"},
        ],
        onclick=_handle,
        small=True,
    )
    layout.footer()


def _fields(subject: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    subject = subject or {}
    return [
        input("اسم المادة *", name="name", value=subject.get("name") or "", required=True),
        input("الرمز", name="code", value=subject.get("code") or "", required=False),
        select(
            "المرحلة",
            name="level_id",
            options=options.levels("— مشتركة —"),
            value=str(subject.get("level_id") or ""),
            required=False,
        ),
        input(
            "الساعات الأسبوعية",
            name="weekly_hours",
            value=str(subject.get("weekly_hours") or 0),
            required=False,
        ),
        input(
            "الدرجة العظمى",
            name="max_score",
            value=str(subject.get("max_score") or 100),
            required=False,
        ),
    ]


def _handle(value: str) -> None:
    if value == "add":
        _form()
        return
    picked = pin["subject_pick"]
    if not picked:
        components.toast_error("اختر المادة أولاً")
        return
    subject_id = int(picked)
    if value == "edit":
        _form(subject_id)
    elif value == "toggle":
        _toggle(subject_id)
    elif value == "delete":
        _delete(subject_id)


def _form(subject_id: int | None = None) -> None:
    subject = subjects_service.get_subject(subject_id) if subject_id else None
    title = f"تعديل المادة: {subject['name']}" if subject else "إضافة مادة جديدة"
    data = components.form_modal(title, _fields(subject))
    if not data:
        return
    with components.error_boundary("بيانات المادة"):
        if subject:
            subjects_service.update_subject(
                subject_id,
                data["name"],
                data.get("code"),
                data.get("level_id"),
                data.get("weekly_hours"),
                data.get("max_score"),
                is_active=bool(subject["is_active"]),
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تم حفظ التعديلات")
        else:
            subjects_service.create_subject(
                data["name"],
                data.get("code"),
                data.get("level_id"),
                data.get("weekly_hours"),
                data.get("max_score"),
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تمت إضافة المادة")
        go_app(APP, new_window=False)


def _toggle(subject_id: int) -> None:
    subject = subjects_service.get_subject(subject_id)
    with components.error_boundary("حالة المادة"):
        subjects_service.update_subject(
            subject_id,
            subject["name"],
            subject.get("code"),
            subject.get("level_id"),
            subject.get("weekly_hours"),
            subject.get("max_score"),
            is_active=not bool(subject["is_active"]),
            actor=auth.current_user(),
            ip=auth.client_ip(),
        )
        components.toast_ok("تم تحديث حالة المادة")
        go_app(APP, new_window=False)


def _delete(subject_id: int) -> None:
    subject = subjects_service.get_subject(subject_id)
    if int(subject.get("assignments_count") or 0) > 0:
        components.toast_error("لا يمكن الحذف: المادة مرتبطة بإسناد تدريسي")
        return
    if not components.confirm(f"حذف المادة «{subject['name']}»؟", "حذف", "إلغاء"):
        return
    with components.error_boundary("حذف مادة"):
        subjects_service.delete_subject(subject_id, actor=auth.current_user(), ip=auth.client_ip())
        components.toast_ok("تم حذف المادة")
        go_app(APP, new_window=False)
