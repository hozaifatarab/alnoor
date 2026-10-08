"""شاشة التسجيل: تسجيل الطلاب في الفصول، النقل، الخصم، إلغاء التسجيل."""
from __future__ import annotations

from typing import Any

from pywebio.input import input, input_group, select
from pywebio.output import put_buttons, put_html
from pywebio.pin import pin, put_select
from pywebio.session import go_app

from core import auth
from core.services import enrollments_service
from ui import components, layout, options

APP = "enrollments"


def enrollments() -> None:
    """شاشة إدارة التسجيلات."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="التسجيل")
    with components.error_boundary("شاشة التسجيل"):
        filters = input_group(
            "تصفية",
            [
                select("السنة الدراسية", name="year_id", options=options.years("الكل"), required=False),
                select(
                    "الفصل", name="class_id", options=options.classes(any_label="الكل"), required=False
                ),
            ],
            cancelable=False,
        )
        year_id = int(filters["year_id"]) if str(filters.get("year_id") or "").isdigit() else None
        class_id = int(filters["class_id"]) if str(filters.get("class_id") or "").isdigit() else None
        rows = enrollments_service.list_enrollments(year_id, class_id)
        _render_table(rows)
        _render_actions(rows)


def _render_table(rows: list[dict[str, Any]]) -> None:
    active = [row for row in rows if row["status"] == "مسجّل"]
    layout.section("التسجيلات", f"العدد الكلي: {len(rows)} — الفعّالة: {len(active)}")
    components.table(
        [
            "رقم الطالب",
            "الطالب",
            "الفصل",
            "المرحلة",
            "السنة",
            "الفصل الدراسي",
            "تاريخ التسجيل",
            "الخصم",
            "الحالة",
        ],
        [
            [
                row["student_no"],
                row["full_name"],
                row["class_name"],
                row["level_name"],
                row["year_name"],
                row.get("term_name") or "—",
                row["enroll_date"],
                row["discount"],
                components.status_chip_for_status(row["status"]),
            ]
            for row in rows
        ],
        empty_message="لا توجد تسجيلات مطابقة للتصفية",
    )


def _render_actions(rows: list[dict[str, Any]]) -> None:
    active_rows = [row for row in rows if row["status"] == "مسجّل"]
    layout.section("إجراءات", "اختر التسجيل ثم الإجراء المطلوب")
    if active_rows:
        put_select(
            "enroll_pick",
            options=[
                {
                    "label": f"{row['student_no']} — {row['full_name']} ({row['class_name']})",
                    "value": str(row["id"]),
                }
                for row in active_rows
            ],
            label="التسجيل",
        )
    else:
        put_html('<div class="section-hint">لا توجد تسجيلات فعّالة لعرض إجراءاتها.</div>')
    put_buttons(
        [
            {"label": "➕ تسجيل طالب", "value": "add", "color": "primary"},
            {"label": "⇄ نقل إلى فصل", "value": "move", "color": "secondary"},
            {"label": "٪ تعديل الخصم", "value": "discount", "color": "secondary"},
            {"label": "⛔ إلغاء التسجيل", "value": "withdraw", "color": "danger"},
            {"label": "🗑 حذف التسجيل", "value": "delete", "color": "danger"},
        ],
        onclick=_handle,
        small=True,
    )
    layout.footer()


def _handle(value: str) -> None:
    if value == "add":
        _add()
        return
    picked = pin["enroll_pick"]
    if not picked:
        components.toast_error("اختر التسجيل من القائمة أولاً")
        return
    enrollment_id = int(picked)
    if value == "move":
        _move(enrollment_id)
    elif value == "discount":
        _discount(enrollment_id)
    elif value == "withdraw":
        _withdraw(enrollment_id)
    elif value == "delete":
        _delete(enrollment_id)


def _add() -> None:
    data = components.form_modal(
        "تسجيل طالب في فصل",
        [
            select("الطالب *", name="student_id", options=options.students(), required=True),
            select("الفصل *", name="class_id", options=options.classes(), required=True),
            select(
                "السنة الدراسية",
                name="year_id",
                options=options.years("— السنة الحالية —"),
                required=False,
            ),
            input("تاريخ التسجيل", name="enroll_date", required=False, help_text="افتراضياً: تاريخ اليوم"),
            input("الخصم", name="discount", value="0", required=False),
        ],
        size="large",
    )
    if not data:
        return
    with components.error_boundary("تسجيل طالب"):
        enrollments_service.enroll(
            data["student_id"],
            data["class_id"],
            year_id=data.get("year_id") or None,
            discount=data.get("discount"),
            enroll_date=data.get("enroll_date"),
            actor=auth.current_user(),
            ip=auth.client_ip(),
        )
        components.toast_ok("تم تسجيل الطالب بنجاح")
        go_app(APP, new_window=False)


def _move(enrollment_id: int) -> None:
    enrollment = enrollments_service.get_enrollment(enrollment_id)
    data = components.form_modal(
        "نقل الطالب إلى فصل آخر",
        [
            select(
                "الفصل الجديد *",
                name="class_id",
                options=options.classes(int(enrollment["year_id"])),
                required=True,
            )
        ],
    )
    if not data:
        return
    with components.error_boundary("نقل طالب"):
        enrollments_service.change_class(
            enrollment_id, data["class_id"], actor=auth.current_user(), ip=auth.client_ip()
        )
        components.toast_ok("تم نقل الطالب")
        go_app(APP, new_window=False)


def _discount(enrollment_id: int) -> None:
    enrollment = enrollments_service.get_enrollment(enrollment_id)
    data = components.form_modal(
        "تعديل الخصم",
        [input("الخصم", name="discount", value=str(enrollment["discount"]), required=True)],
    )
    if not data:
        return
    with components.error_boundary("تعديل الخصم"):
        enrollments_service.set_discount(
            enrollment_id, data["discount"], actor=auth.current_user(), ip=auth.client_ip()
        )
        components.toast_ok("تم تحديث الخصم")
        go_app(APP, new_window=False)


def _withdraw(enrollment_id: int) -> None:
    if not components.confirm("سيتم إلغاء التسجيل (يبقى السجل بحالة «منسحب»). متابعة؟", "إلغاء", "رجوع"):
        return
    with components.error_boundary("إلغاء تسجيل"):
        enrollments_service.withdraw(enrollment_id, actor=auth.current_user(), ip=auth.client_ip())
        components.toast_ok("تم إلغاء التسجيل")
        go_app(APP, new_window=False)


def _delete(enrollment_id: int) -> None:
    if not components.confirm("حذف سجل التسجيل نهائياً؟", "حذف", "إلغاء"):
        return
    with components.error_boundary("حذف تسجيل"):
        enrollments_service.delete_enrollment(
            enrollment_id, actor=auth.current_user(), ip=auth.client_ip()
        )
        components.toast_ok("تم حذف التسجيل")
        go_app(APP, new_window=False)
