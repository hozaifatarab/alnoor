"""شاشة الإسناد التدريسي: ربط المعلم بالمادة والفصل."""
from __future__ import annotations

from typing import Any

from pywebio.input import input_group, select
from pywebio.output import put_buttons, put_html
from pywebio.pin import pin, put_select
from pywebio.session import go_app

from core import auth
from core.services import teachers_service
from ui import components, layout, options

APP = "assignments"


def assignments() -> None:
    """شاشة إدارة الإسناد التدريسي."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="الإسناد التدريسي")
    with components.error_boundary("الإسناد التدريسي"):
        filters = input_group(
            "تصفية",
            [
                select("المعلم", name="teacher_id", options=options.teachers("الكل"), required=False),
                select("الفصل", name="class_id", options=options.classes(any_label="الكل"), required=False),
            ],
            cancelable=False,
        )
        teacher_id = int(filters["teacher_id"]) if str(filters.get("teacher_id") or "").isdigit() else None
        class_id = int(filters["class_id"]) if str(filters.get("class_id") or "").isdigit() else None
        rows = teachers_service.list_assignments(class_id=class_id, teacher_id=teacher_id)
        _render_table(rows)
        _render_actions(rows)


def _render_table(rows: list[dict[str, Any]]) -> None:
    layout.section("الإسنادات", f"عدد الإسنادات: {len(rows)}")
    components.table(
        ["المعلم", "المادة", "الفصل", "السنة", "الفصل الدراسي"],
        [
            [
                row["teacher_name"],
                f"{row['subject_name']}{' (' + row['subject_code'] + ')' if row.get('subject_code') else ''}",
                row["class_name"],
                row["year_name"],
                row.get("term_name") or "—",
            ]
            for row in rows
        ],
        empty_message="لا توجد إسنادات مطابقة للتصفية",
    )


def _render_actions(rows: list[dict[str, Any]]) -> None:
    layout.section("إجراءات", "اختر الإسناد ثم احذفه، أو أضف إسناداً جديداً")
    if rows:
        put_select(
            "assign_pick",
            options=[
                {
                    "label": f"{row['teacher_name']} — {row['subject_name']} — {row['class_name']}",
                    "value": str(row["id"]),
                }
                for row in rows
            ],
            label="الإسناد",
        )
    else:
        put_html('<div class="section-hint">لا توجد إسنادات لعرض إجراءاتها.</div>')
    put_buttons(
        [
            {"label": "➕ إسناد جديد", "value": "add", "color": "primary"},
            {"label": "🗑 حذف الإسناد", "value": "delete", "color": "danger"},
        ],
        onclick=_handle,
        small=True,
    )
    layout.footer()


def _handle(value: str) -> None:
    if value == "add":
        _add()
        return
    picked = pin["assign_pick"]
    if not picked:
        components.toast_error("اختر الإسناد من القائمة أولاً")
        return
    if value == "delete":
        assignment_id = int(picked)
        if not components.confirm("حذف الإسناد المحدد؟", "حذف", "إلغاء"):
            return
        with components.error_boundary("حذف إسناد"):
            teachers_service.delete_assignment(
                assignment_id, actor=auth.current_user(), ip=auth.client_ip()
            )
            components.toast_ok("تم حذف الإسناد")
            go_app(APP, new_window=False)


def _add() -> None:
    data = components.form_modal(
        "إضافة إسناد تدريسي",
        [
            select("المعلم *", name="teacher_id", options=options.teachers(), required=True),
            select("المادة *", name="subject_id", options=options.subjects(), required=True),
            select("الفصل *", name="class_id", options=options.classes(), required=True),
            select(
                "الفصل الدراسي",
                name="term_id",
                options=options.terms(any_label="— غير محدد —"),
                required=False,
            ),
        ],
        size="large",
    )
    if not data:
        return
    with components.error_boundary("إضافة إسناد"):
        teachers_service.create_assignment(
            data["teacher_id"],
            data["subject_id"],
            data["class_id"],
            data.get("term_id") or None,
            actor=auth.current_user(),
            ip=auth.client_ip(),
        )
        components.toast_ok("تم إضافة الإسناد")
        go_app(APP, new_window=False)
