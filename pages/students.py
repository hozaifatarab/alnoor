"""شاشة الطلاب: بحث وتصفية، عرض الملف، إضافة/تعديل، تغيير الحالة، حذف."""
from __future__ import annotations

from typing import Any

from pywebio.input import input, input_group, select, textarea
from pywebio.output import put_html, put_text
from pywebio.pin import pin, put_select
from pywebio.session import go_app

from core import auth, config
from core.services import classes_service, enrollments_service, students_service, years_service
from ui import components, layout

PAGE_SIZE = 20
APP = "students"


def students() -> None:
    """شاشة إدارة الطلاب."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="الطلاب")
    with components.error_boundary("شاشة الطلاب"):
        filters = _render_filters()
        _render_table(filters)
        _render_actions()


def _render_filters() -> dict[str, Any]:
    class_options = [{"label": "كل الفصول", "value": ""}] + [
        {"label": f"{klass['name']} — {klass['level_name']}", "value": str(klass["id"])}
        for klass in classes_service.list_classes()
    ]
    status_options = [{"label": "كل الحالات", "value": ""}] + [
        {"label": status, "value": status} for status in config.STUDENT_STATUSES
    ]
    fields: list[dict[str, Any]] = [
        input("بحث (الاسم / رقم الطالب / الهوية)", name="search", required=False),
        select("الفصل", name="class_id", options=class_options, required=False),
        select("الحالة", name="status", options=status_options, required=False),
    ]
    put_html('<div class="section-hint">اترك الحقول فارغة لعرض الكل</div>')
    data = input_group("بحث وتصفية", fields, cancelable=False)
    data["class_id"] = int(data["class_id"]) if str(data.get("class_id") or "").isdigit() else None
    data["status"] = data.get("status") or None
    data["search"] = (data.get("search") or "").strip() or None
    return data


def _render_table(filters: dict[str, Any]) -> None:
    total = students_service.count_students(
        filters["search"], filters["status"], filters["class_id"]
    )
    rows = students_service.list_students(
        filters["search"], filters["status"], filters["class_id"], limit=PAGE_SIZE
    )
    layout.section("قائمة الطلاب", f"عدد النتائج: {total} (يُعرض {min(total, PAGE_SIZE)})")
    components.table(
        ["رقم الطالب", "الاسم", "الفصل", "ولي الأمر", "جوال ولي الأمر", "الحالة"],
        [
            [
                row["student_no"],
                row["full_name"],
                row.get("class_name") or "— غير مسجّل —",
                row.get("guardian_name") or "—",
                row.get("guardian_phone") or "—",
                components.status_chip_for_status(row["status"]),
            ]
            for row in rows
        ],
        empty_message="لا يوجد طلاب مطابقون لمعايير البحث",
    )
    if total > PAGE_SIZE:
        put_html(
            f'<div class="section-hint">لتصفية النتائج بشكل أدق استخدم البحث أو الفصل '
            f"أو الحالة (المعروض أعلى {PAGE_SIZE} نتيجة)</div>"
        )


def _render_actions() -> None:
    students_list = students_service.list_students(limit=1000)
    layout.section("إجراءات", "اختر الطالب من القائمة ثم اضغط الإجراء المطلوب")
    if not students_list:
        put_html('<div class="section-hint">لا يوجد طلاب مسجّلون — ابدأ بالإضافة.</div>')
    options = [
        {"label": f"{row['student_no']} — {row['full_name']}", "value": str(row["id"])}
        for row in students_list
    ]
    if options:
        put_select("student_pick", options=options, label="الطالب")
    from pywebio.output import put_buttons

    put_buttons(
        [
            {"label": "➕ إضافة طالب", "value": "add", "color": "primary"},
            {"label": "👁 عرض الملف", "value": "view", "color": "secondary"},
            {"label": "✎ تعديل", "value": "edit", "color": "secondary"},
            {"label": "⇄ تغيير الحالة", "value": "status", "color": "secondary"},
            {"label": "🗑 حذف", "value": "delete", "color": "danger"},
        ],
        onclick=_handle_action,
        small=True,
    )
    layout.footer()


def _handle_action(value: str) -> None:
    """تنفيذ الإجراء المختار على الطالب المحدد في القائمة."""
    if value == "add":
        _add_student()
        return
    picked = pin["student_pick"]
    if not picked:
        components.toast_error("اختر الطالب من القائمة أولاً")
        return
    student_id = int(picked)
    if value == "view":
        _view_profile(student_id)
    elif value == "edit":
        _edit_student(student_id)
    elif value == "status":
        _change_status(student_id)
    elif value == "delete":
        _delete_student(student_id)


def _student_fields(
    student: dict[str, Any] | None = None, suggested_no: str | None = None
) -> list[dict[str, Any]]:
    """حقول نموذج الطالب (تُستخدم للإضافة والتعديل معاً)."""
    student = student or {}
    gender_options = [{"label": "غير محدد", "value": ""}] + [
        {"label": gender, "value": gender} for gender in config.GENDERS
    ]
    status_options = [{"label": status, "value": status} for status in config.STUDENT_STATUSES]
    return [
        input(
            "رقم الطالب",
            name="student_no",
            value=student.get("student_no") or (suggested_no or ""),
            required=False,
            help_text="اتركه فارغاً ليولّد النظام الرقم تلقائياً",
        ),
        input("الاسم الكامل *", name="full_name", value=student.get("full_name") or "", required=True),
        input("رقم الهوية", name="national_id", value=student.get("national_id") or "", required=False),
        select(
            "الجنس",
            name="gender",
            options=gender_options,
            value=student.get("gender") or "",
            required=False,
        ),
        input(
            "تاريخ الميلاد",
            name="birth_date",
            value=student.get("birth_date") or "",
            placeholder="2008-05-20",
            required=False,
        ),
        input("ولي الأمر", name="guardian_name", value=student.get("guardian_name") or "", required=False),
        input(
            "جوال ولي الأمر",
            name="guardian_phone",
            value=student.get("guardian_phone") or "",
            required=False,
        ),
        input("العنوان", name="address", value=student.get("address") or "", required=False),
        select(
            "الحالة",
            name="status",
            options=status_options,
            value=student.get("status") or "منتظم",
            required=False,
        ),
        textarea("ملاحظات", name="notes", value=student.get("notes") or "", rows=2, required=False),
    ]


def _add_student() -> None:
    year_name = years_service.current_year_name()
    suggestion = students_service.generate_student_no(year_name)
    data = components.form_modal(
        "إضافة طالب جديد", _student_fields(suggested_no=suggestion), size="large"
    )
    if not data:
        return
    with components.error_boundary("إضافة طالب"):
        students_service.create_student(
            data, year_name=year_name, actor=auth.current_user(), ip=auth.client_ip()
        )
        components.toast_ok("تمت إضافة الطالب بنجاح")
        go_app(APP, new_window=False)


def _edit_student(student_id: int) -> None:
    student = students_service.get_student(student_id)
    data = components.form_modal(
        f"تعديل بيانات: {student['full_name']}", _student_fields(student=student), size="large"
    )
    if data is None:
        return
    data["student_no"] = student["student_no"]
    with components.error_boundary("تعديل طالب"):
        students_service.update_student(
            student_id, data, actor=auth.current_user(), ip=auth.client_ip()
        )
        components.toast_ok("تم حفظ التعديلات")
        go_app(APP, new_window=False)


def _change_status(student_id: int) -> None:
    student = students_service.get_student(student_id)
    data = components.form_modal(
        f"تغيير حالة: {student['full_name']}",
        [
            select(
                "الحالة الجديدة",
                name="status",
                options=[{"label": status, "value": status} for status in config.STUDENT_STATUSES],
                value=student["status"],
                required=True,
            )
        ],
    )
    if not data:
        return
    with components.error_boundary("تغيير حالة طالب"):
        students_service.set_status(
            student_id, data["status"], actor=auth.current_user(), ip=auth.client_ip()
        )
        components.toast_ok("تم تحديث حالة الطالب")
        go_app(APP, new_window=False)


def _delete_student(student_id: int) -> None:
    student = students_service.get_student(student_id)
    if not components.confirm(
        f"سيتم حذف الطالب «{student['full_name']}» وتسجيلاته نهائياً. هل تريد المتابعة؟",
        "حذف نهائي",
        "إلغاء",
    ):
        return
    with components.error_boundary("حذف طالب"):
        students_service.delete_student(student_id, actor=auth.current_user(), ip=auth.client_ip())
        components.toast_ok("تم حذف الطالب")
        go_app(APP, new_window=False)


def _view_profile(student_id: int) -> None:
    from pywebio.output import popup

    student = students_service.get_student(student_id)
    history = enrollments_service.student_history(student_id)
    with popup(f"ملف الطالب: {student['full_name']}", size="large"):
        components.kv_table(
            [
                ("رقم الطالب", student["student_no"]),
                ("الاسم", student["full_name"]),
                ("رقم الهوية", student.get("national_id") or "—"),
                ("الجنس", student.get("gender") or "—"),
                ("تاريخ الميلاد", student.get("birth_date") or "—"),
                ("ولي الأمر", student.get("guardian_name") or "—"),
                ("جوال ولي الأمر", student.get("guardian_phone") or "—"),
                ("العنوان", student.get("address") or "—"),
                ("الحالة", student["status"]),
                ("تاريخ الإضافة", student.get("created_at") or "—"),
            ]
        )
        layout.section("سجل التسجيلات")
        components.table(
            ["السنة", "الفصل", "المرحلة", "تاريخ التسجيل", "الحالة", "الخصم"],
            [
                [
                    row["year_name"],
                    row["class_name"],
                    row["level_name"],
                    row["enroll_date"],
                    components.status_chip_for_status(row["status"]),
                    row["discount"],
                ]
                for row in history
            ],
            empty_message="لا توجد تسجيلات لهذا الطالب",
        )
        put_text("")
