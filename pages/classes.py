"""شاشة الفصول: عرض مع السعة، إضافة، تعديل، حذف، وعرض كشف الطلاب."""
from __future__ import annotations

from typing import Any

from pywebio.input import input, input_group, select
from pywebio.output import popup, put_buttons, put_html
from pywebio.pin import pin, put_select
from pywebio.session import go_app

from core import auth
from core.services import classes_service, enrollments_service
from ui import components, layout, options

APP = "classes"


def classes() -> None:
    """شاشة إدارة الفصول."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="الفصول")
    with components.error_boundary("شاشة الفصول"):
        filters = input_group(
            "تصفية",
            [
                select("السنة الدراسية", name="year_id", options=options.years("الكل"), required=False),
                select("المرحلة", name="level_id", options=options.levels("الكل"), required=False),
                input("بحث باسم الفصل", name="search", required=False),
            ],
            cancelable=False,
        )
        year_id = int(filters["year_id"]) if str(filters.get("year_id") or "").isdigit() else None
        level_id = int(filters["level_id"]) if str(filters.get("level_id") or "").isdigit() else None
        search = (filters.get("search") or "").strip() or None
        rows = classes_service.list_classes(year_id, level_id, search)
        _render_table(rows)
        _render_actions(rows)


def _render_table(rows: list[dict[str, Any]]) -> None:
    layout.section("قائمة الفصول", f"عدد النتائج: {len(rows)}")
    components.table(
        ["الفصل", "المرحلة", "السنة", "مشرف الفصل", "السعة", "المسجّلون", "المتاح", "القاعة"],
        [
            [
                row["name"],
                row["level_name"],
                row["year_name"],
                row.get("homeroom_teacher_name") or "—",
                row["capacity"],
                row["enrolled"],
                max(int(row["capacity"]) - int(row["enrolled"]), 0),
                row.get("room") or "—",
            ]
            for row in rows
        ],
        empty_message="لا توجد فصول مطابقة للتصفية",
    )


def _render_actions(rows: list[dict[str, Any]]) -> None:
    layout.section("إجراءات", "اختر الفصل ثم الإجراء المطلوب")
    if rows:
        put_select(
            "class_pick",
            options=[
                {"label": f"{row['name']} — {row['level_name']} ({row['enrolled']}/{row['capacity']})",
                 "value": str(row["id"])}
                for row in rows
            ],
            label="الفصل",
        )
    else:
        put_html('<div class="section-hint">لا توجد فصول لعرض إجراءاتها.</div>')
    put_buttons(
        [
            {"label": "➕ إضافة فصل", "value": "add", "color": "primary"},
            {"label": "👥 كشف الطلاب", "value": "roster", "color": "secondary"},
            {"label": "✎ تعديل", "value": "edit", "color": "secondary"},
            {"label": "🗑 حذف", "value": "delete", "color": "danger"},
        ],
        onclick=_handle,
        small=True,
    )
    layout.footer()


def _fields(klass: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    klass = klass or {}
    return [
        input("اسم الفصل *", name="name", value=klass.get("name") or "", required=True),
        select(
            "المرحلة *",
            name="level_id",
            options=options.levels(),
            value=str(klass.get("level_id") or ""),
            required=True,
        ),
        select(
            "السنة الدراسية *",
            name="year_id",
            options=options.years(),
            value=str(klass.get("year_id") or ""),
            required=True,
        ),
        input("السعة *", name="capacity", value=str(klass.get("capacity") or 30), required=True),
        input("القاعة", name="room", value=klass.get("room") or "", required=False),
        select(
            "مشرف الفصل",
            name="homeroom_teacher_id",
            options=options.teachers("— بدون —"),
            value=str(klass.get("homeroom_teacher_id") or ""),
            required=False,
        ),
    ]


def _handle(value: str) -> None:
    if value == "add":
        _form()
        return
    picked = pin["class_pick"]
    if not picked:
        components.toast_error("اختر الفصل من القائمة أولاً")
        return
    class_id = int(picked)
    if value == "roster":
        _roster(class_id)
    elif value == "edit":
        _form(class_id)
    elif value == "delete":
        _delete(class_id)


def _form(class_id: int | None = None) -> None:
    klass = classes_service.get_class(class_id) if class_id else None
    title = f"تعديل الفصل: {klass['name']}" if klass else "إضافة فصل جديد"
    data = components.form_modal(title, _fields(klass), size="large")
    if not data:
        return
    with components.error_boundary("بيانات الفصل"):
        if klass:
            classes_service.update_class(
                class_id,
                data["name"],
                data["level_id"],
                data["year_id"],
                data["capacity"],
                data.get("room"),
                data.get("homeroom_teacher_id"),
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تم حفظ التعديلات")
        else:
            classes_service.create_class(
                data["name"],
                data["level_id"],
                data["year_id"],
                data["capacity"],
                data.get("room"),
                data.get("homeroom_teacher_id"),
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تمت إضافة الفصل")
        go_app(APP, new_window=False)


def _delete(class_id: int) -> None:
    klass = classes_service.get_class(class_id)
    info = classes_service.capacity_info(class_id)
    if info["enrolled"] > 0:
        components.toast_error(f"لا يمكن الحذف: يوجد {info['enrolled']} طالباً مسجّلاً في الفصل")
        return
    if not components.confirm(f"حذف الفصل «{klass['name']}»؟", "حذف", "إلغاء"):
        return
    with components.error_boundary("حذف فصل"):
        classes_service.delete_class(class_id, actor=auth.current_user(), ip=auth.client_ip())
        components.toast_ok("تم حذف الفصل")
        go_app(APP, new_window=False)


def _roster(class_id: int) -> None:
    klass = classes_service.get_class(class_id)
    rows = enrollments_service.roster(class_id)
    info = classes_service.capacity_info(class_id)
    with popup(f"كشف طلاب: {klass['name']} — {klass['level_name']}", size="large"):
        components.kv_table(
            [
                ("الفصل", klass["name"]),
                ("المرحلة", klass["level_name"]),
                ("السنة", klass["year_name"]),
                ("مشرف الفصل", klass.get("homeroom_teacher_name") or "—"),
                ("السعة", f"{info['enrolled']} / {info['capacity']}"),
            ]
        )
        components.table(
            ["#", "رقم الطالب", "الاسم", "الجنس", "تاريخ التسجيل", "الحالة", "الخصم"],
            [
                [
                    index,
                    row["student_no"],
                    row["full_name"],
                    row.get("gender") or "—",
                    row["enroll_date"],
                    components.status_chip_for_status(row["enrollment_status"]),
                    row["discount"],
                ]
                for index, row in enumerate(rows, start=1)
            ],
            empty_message="لا يوجد طلاب مسجّلون في هذا الفصل",
        )
