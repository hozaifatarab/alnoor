"""شاشة المعلمين: عرض، إضافة، تعديل، إيقاف/تنشيط، حذف."""
from __future__ import annotations

from typing import Any

from pywebio.input import input, input_group, select
from pywebio.output import put_buttons, put_html
from pywebio.pin import pin, put_select
from pywebio.session import go_app

from core import auth
from core.services import teachers_service
from ui import components, layout

APP = "teachers"


def teachers() -> None:
    """شاشة إدارة المعلمين."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="المعلمون")
    with components.error_boundary("شاشة المعلمين"):
        filters = input_group(
            "بحث وتصفية",
            [
                input("بحث (الاسم / الهوية / الجوال)", name="search", required=False),
                select(
                    "الحالة",
                    name="active",
                    options=[
                        {"label": "— الكل —", "value": ""},
                        {"label": "الفعّالون فقط", "value": "1"},
                        {"label": "غير الفعّالين", "value": "0"},
                    ],
                    required=False,
                ),
            ],
            cancelable=False,
        )
        search = (filters.get("search") or "").strip() or None
        rows = teachers_service.list_teachers(search, active_only=filters.get("active") == "1")
        if filters.get("active") == "0":
            rows = [row for row in rows if not row["is_active"]]
        _render_table(rows)
        _render_actions(rows)


def _render_table(rows: list[dict[str, Any]]) -> None:
    layout.section("قائمة المعلمين", f"عدد النتائج: {len(rows)}")
    components.table(
        ["الاسم", "التخصص", "الهوية", "الجوال", "البريد", "إسناد/إشراف", "الحساب", "الحالة"],
        [
            [
                row["full_name"],
                row.get("specialty") or "—",
                row.get("national_id") or "—",
                row.get("phone") or "—",
                row.get("email") or "—",
                f"{row.get('assignments_count') or 0} / {row.get('homeroom_count') or 0}",
                row.get("account_username") or "— لا يوجد —",
                components.chip(
                    "فعّال" if row["is_active"] else "معطّل", "ok" if row["is_active"] else "bad"
                ),
            ]
            for row in rows
        ],
        empty_message="لا يوجد معلمون مطابقون للبحث",
    )


def _render_actions(rows: list[dict[str, Any]]) -> None:
    layout.section("إجراءات", "اختر المعلم ثم الإجراء المطلوب")
    if rows:
        put_select(
            "teacher_pick",
            options=[{"label": row["full_name"], "value": str(row["id"])} for row in rows],
            label="المعلم",
        )
    else:
        put_html('<div class="section-hint">لا يوجد معلمون لعرض إجراءاتهم.</div>')
    put_buttons(
        [
            {"label": "➕ إضافة معلم", "value": "add", "color": "primary"},
            {"label": "✎ تعديل", "value": "edit", "color": "secondary"},
            {"label": "⏻ إيقاف/تنشيط", "value": "toggle", "color": "secondary"},
            {"label": "🗑 حذف", "value": "delete", "color": "danger"},
        ],
        onclick=_handle,
        small=True,
    )
    layout.footer()


def _handle(value: str) -> None:
    if value == "add":
        _form()
        return
    picked = pin["teacher_pick"]
    if not picked:
        components.toast_error("اختر المعلم من القائمة أولاً")
        return
    teacher_id = int(picked)
    if value == "edit":
        _form(teacher_id)
    elif value == "toggle":
        _toggle(teacher_id)
    elif value == "delete":
        _delete(teacher_id)


def _fields(teacher: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    teacher = teacher or {}
    return [
        input("الاسم الكامل *", name="full_name", value=teacher.get("full_name") or "", required=True),
        input("التخصص", name="specialty", value=teacher.get("specialty") or "", required=False),
        input("رقم الهوية", name="national_id", value=teacher.get("national_id") or "", required=False),
        input("الجوال", name="phone", value=teacher.get("phone") or "", required=False),
        input("البريد الإلكتروني", name="email", value=teacher.get("email") or "", required=False),
        input(
            "تاريخ التعيين",
            name="hire_date",
            value=teacher.get("hire_date") or "",
            placeholder="2024-09-01",
            required=False,
        ),
        input("الراتب", name="salary", value=str(teacher.get("salary") or 0), required=False),
    ]


def _form(teacher_id: int | None = None) -> None:
    teacher = teachers_service.get_teacher(teacher_id) if teacher_id else None
    title = f"تعديل: {teacher['full_name']}" if teacher else "إضافة معلم جديد"
    data = components.form_modal(title, _fields(teacher), size="large")
    if not data:
        return
    with components.error_boundary("بيانات المعلم"):
        if teacher:
            teachers_service.update_teacher(
                teacher_id,
                **data,
                is_active=bool(teacher["is_active"]),
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تم حفظ التعديلات")
        else:
            teachers_service.create_teacher(**data, actor=auth.current_user(), ip=auth.client_ip())
            components.toast_ok("تمت إضافة المعلم")
        go_app(APP, new_window=False)


def _toggle(teacher_id: int) -> None:
    teacher = teachers_service.get_teacher(teacher_id)
    new_state = not bool(teacher["is_active"])
    label = "تنشيط" if new_state else "إيقاف"
    if not components.confirm(f"هل تريد {label} حساب المعلم «{teacher['full_name']}»؟", label, "إلغاء"):
        return
    with components.error_boundary("حالة المعلم"):
        teachers_service.update_teacher(
            teacher_id,
            teacher["full_name"],
            teacher.get("national_id"),
            teacher.get("phone"),
            teacher.get("email"),
            teacher.get("hire_date"),
            teacher.get("specialty"),
            teacher.get("salary") or 0,
            is_active=new_state,
            actor=auth.current_user(),
            ip=auth.client_ip(),
        )
        components.toast_ok(f"تم {label} الحساب")
        go_app(APP, new_window=False)


def _delete(teacher_id: int) -> None:
    teacher = teachers_service.get_teacher(teacher_id)
    if int(teacher.get("assignments_count") or 0) > 0:
        components.toast_error("لا يمكن الحذف: للمعلم إسناد تدريسي قائم")
        return
    if not components.confirm(f"سيتم حذف المعلم «{teacher['full_name']}». متابعة؟", "حذف", "إلغاء"):
        return
    with components.error_boundary("حذف معلم"):
        teachers_service.delete_teacher(teacher_id, actor=auth.current_user(), ip=auth.client_ip())
        components.toast_ok("تم حذف المعلم")
        go_app(APP, new_window=False)
