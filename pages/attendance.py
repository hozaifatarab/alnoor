"""شاشة الحضور اليدوي والتقارير: شبكة الفصل، تعديل الحالات، وملخص حضور الطالب."""
from __future__ import annotations

from pywebio.input import input, input_group, select
from pywebio.output import put_buttons, put_html
from pywebio.session import go_app

from core import auth, config
from core.repos import attendance as attendance_repo
from core.repos import settings as settings_repo
from core.services import attendance_service, classes_service
from ui import charts, components, layout, options

APP = "attendance"


def attendance() -> None:
    """تسجيل الحضور يدوياً + عرض سجل الفصل."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="الحضور والغياب")

    with components.error_boundary("شاشة الحضور"):
        class_options = options.classes()
        if not class_options:
            layout.alert("لا توجد فصول معرّفة بعد.", "warn")
            go_app("classes", new_window=False)
            return

        today = settings_repo.get("day_close_time", "14:00")
        data = input_group(
            "بيانات الجلسة",
            [
                select("الفصل *", name="class_id", options=class_options, required=True),
                input(
                    "التاريخ",
                    name="date",
                    required=True,
                    help_text="بصيغة YYYY-MM-DD",
                ),
            ],
            cancelable=False,
        )
        class_id = int(data["class_id"])
        date = str(data["date"]).strip()

        _render_grid(class_id, date)
        put_buttons(
            [
                {"label": "💾 حفظ تعديلات الشبكة", "value": "save", "color": "primary"},
                {"label": "✔ الكل حاضر", "value": "bulk", "color": "secondary"},
                {"label": "🔒 إغلاق اليوم", "value": "close", "color": "danger"},
                {"label": "📊 تقرير الفصل", "value": "report", "color": "secondary"},
            ],
            onclick=lambda value: _handle(value, class_id, date),
            small=True,
        )
        put_html(
            f'<div class="section-hint">وقت إغلاق اليوم المعرّف: '
            f'{layout.escape_html(today)}</div>'
        )
        layout.footer()


def _status_options() -> list[dict[str, str]]:
    return [{"label": status, "value": status} for status in config.ATTENDANCE_STATUSES]


def _render_grid(class_id: int, date: str) -> None:
    """شبكة كل طلاب الفصل مع حالتهم الحالية لتاريخ محدد."""
    rows = attendance_repo.list_class_attendance_for_date(class_id, date)
    summary = attendance_repo.class_attendance_summary(class_id, date)
    layout.kpi_cards(
        [
            {"label": "الطلاب", "value": summary["total"]},
            {"label": "حاضر", "value": summary["present"]},
            {"label": "متأخر", "value": summary["late"], "kind": "warn" if summary["late"] else ""},
            {"label": "بعذر", "value": summary["excused"]},
            {"label": "غائب", "value": summary["absent"], "kind": "danger" if summary["absent"] else ""},
            {"label": "لم يُسجَّل", "value": summary["unrecorded"]},
        ]
    )
    layout.section("شبكة الحضور", "تُحفظ التعديلات بزر «حفظ تعديلات الشبكة»")
    components.table(
        ["#", "الرقم الأكاديمي", "الطالب", "الحالة الحالية", "الوقت", "التأخير (دقيقة)", "المصدر"],
        [
            [
                index,
                row["student_no"],
                row["full_name"],
                _status_chip(row.get("attendance_status")),
                row.get("scan_time") or "—",
                row.get("delay_minutes") if row.get("delay_minutes") else "—",
                row.get("source") or "—",
            ]
            for index, row in enumerate(rows, start=1)
        ],
        empty_message="لا يوجد طلاب مسجّلون في هذا الفصل",
    )


def _status_chip(status: str | None) -> str:
    if not status:
        return components.chip("لم يُسجَّل", "muted")
    mapping = {"حاضر": "ok", "متأخر": "warn", "غائب": "bad", "بعذر": "muted"}
    return components.chip(status, mapping.get(status, "muted"))



def _handle(value: str, class_id: int, date: str) -> None:
    if value == "bulk":
        with components.error_boundary("تحضير جماعي"):
            count = attendance_service.bulk_mark_present(class_id, date, actor=auth.current_user())
            components.toast_ok(f"تم تحضير {count} طالباً")
            go_app(APP, new_window=False)
    elif value == "close":
        if not components.confirm("وضع «غائب» لكل من لم يُسجَّل حضوره؟", "إغلاق اليوم", "إلغاء"):
            return
        with components.error_boundary("إغلاق اليوم"):
            count = attendance_service.close_day_attendance(class_id, date, actor=auth.current_user())
            components.toast_ok(f"تم إغلاق اليوم ({count} غائب جديد)")
            go_app(APP, new_window=False)
    elif value == "save":
        _save_grid(class_id, date)
    elif value == "report":
        _render_report(class_id, date)


def _save_grid(class_id: int, date: str) -> None:
    """تعديل حالة حضور طالب مع تسجيل السبب عند العذر."""
    rows = attendance_repo.list_class_attendance_for_date(class_id, date)
    if not rows:
        components.toast_error("لا يوجد طلاب في هذا الفصل")
        return
    data = components.form_modal(
        "تعديل حالة حضور",
        [
            select(
                "الطالب *",
                name="student_id",
                options=[
                    {
                        "label": f"{row['student_no']} — {row['full_name']}"
                        f" ({row.get('attendance_status') or 'لم يُسجَّل'})",
                        "value": str(row["student_id"]),
                    }
                    for row in rows
                ],
                required=True,
            ),
            select("الحالة *", name="status", options=_status_options(), required=True),
            input("سبب العذر (إلزامي لحالة «بعذر»)", name="excuse", required=False),
            input("ملاحظات", name="notes", required=False),
        ],
        size="large",
    )
    if not data:
        return
    with components.error_boundary("تعديل الحضور"):
        attendance_service.record_manual(
            int(data["student_id"]),
            class_id,
            date,
            str(data["status"]),
            excuse_reason=data.get("excuse"),
            notes=data.get("notes"),
            actor=auth.current_user(),
        )
        components.toast_ok("تم تحديث حالة الحضور")
        go_app(APP, new_window=False)


def _render_report(class_id: int, date: str) -> None:
    """تقرير الفصل: إحصائية الحضور وقائمة الغائبين."""
    summary = attendance_repo.class_attendance_summary(class_id, date)
    rows = attendance_repo.list_class_attendance_for_date(class_id, date)
    klass = classes_service.get_class(class_id)

    layout.section(f"تقرير حضور: {klass['name'] if klass else ''}", f"تاريخ {date}")
    charts.bar_chart(
        "توزيع الحضور",
        [
            ("حاضر", summary["present"]),
            ("متأخر", summary["late"]),
            ("بعذر", summary["excused"]),
            ("غائب", summary["absent"]),
            ("لم يُسجَّل", summary["unrecorded"]),
        ],
        total=max(summary["total"], 1),
    )
    absentees = [row for row in rows if row.get("attendance_status") == "غائب"]
    components.table(
        ["الطالب", "الرقم", "الحالة", "ملاحظة"],
        [
            [
                row["full_name"],
                row["student_no"],
                _status_chip(row.get("attendance_status")),
                row.get("excuse_reason") or row.get("notes") or "—",
            ]
            for row in (absentees or rows)
        ],
        empty_message="لا توجد بيانات",
    )


def student_history(student_id: int) -> None:
    """سجل حضور طالب (يُستدعى من ملف الطالب)."""
    rows = attendance_repo.student_attendance_history(student_id, limit=60)
    layout.section("سجل الحضور")
    components.table(
        ["التاريخ", "الفصل", "الحالة", "الوقت", "التأخير (دقيقة)"],
        [
            [
                row["date"],
                row["class_name"],
                _status_chip(row["status"]),
                row.get("scan_time") or "—",
                row.get("delay_minutes") or "—",
            ]
            for row in rows
        ],
        empty_message="لا يوجد سجل حضور لهذا الطالب",
    )
