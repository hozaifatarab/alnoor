"""لوحة المعلومات: مؤشرات سريعة + توزيع الطلاب + آخر العمليات."""
from __future__ import annotations

from typing import Any

from core import auth, config
from core.repos import audit
from core.services import (
    classes_service,
    levels_service,
    students_service,
    teachers_service,
    users_service,
    years_service,
)
from ui import charts, components, layout


def dashboard() -> None:
    """الشاشة الرئيسية بعد تسجيل الدخول."""
    user = auth.current_user()
    layout.page_header(user, active="dashboard", subtitle="لوحة المعلومات")
    with components.error_boundary("لوحة المعلومات"):
        _render_context(user)
        _render_kpis(user)
        _render_today_attendance(user)
        _render_distribution()
        _render_recent_activity()


def _render_context(user: dict[str, Any]) -> None:
    year = years_service.current_year()
    term = None
    if year:
        from core.services import terms_service

        term = terms_service.current_term()
    parts = []
    if year:
        parts.append(f"السنة الدراسية الحالية: {year['name']}")
    else:
        parts.append("لم تُحدَّد سنة دراسية حالية بعد (الإعدادات ← البنية الأكاديمية)")
    if term:
        parts.append(f"الفصل الحالي: {term['name']}")
    layout.alert(" — ".join(parts), "info")


def _render_kpis(user: dict[str, Any]) -> None:
    student_stats = students_service.stats()
    teacher_stats = teachers_service.stats()
    classes = classes_service.list_classes()
    users_stats = users_service.stats()

    active_students = student_stats.get("منتظم", 0)
    capacity = sum(int(klass["capacity"]) for klass in classes)
    enrolled = sum(int(klass["enrolled"]) for klass in classes)
    occupancy = f"{(enrolled / capacity * 100):.0f}%" if capacity else "—"

    cards = [
        {"label": "إجمالي الطلاب", "value": student_stats.get("total", 0)},
        {"label": "الطلاب المنتظمون", "value": active_students},
        {"label": "المعلمون", "value": teacher_stats.get("active", 0), "hint": "فعّالون"},
        {"label": "الفصول", "value": len(classes), "hint": f"إشغال {occupancy}"},
        {
            "label": "غير المنتظمين",
            "value": student_stats.get("total", 0) - active_students,
            "kind": "warn" if (student_stats.get("total", 0) - active_students) else "",
            "hint": "منسحب/متخرج/موقوف",
        },
        {"label": "المستخدمون", "value": users_stats["total"], "hint": f"مديرون: {users_stats['admins']}"},
    ]
    layout.kpi_cards(cards)


def _render_today_attendance(user: dict[str, Any]) -> None:
    """ملخص حضور اليوم (يظهر فقط لمن يملك صلاحية الحضور)."""
    from core import config as _config
    from core import db

    if not _config.can((user or {}).get("role"), _config.PERM_ATTENDANCE):
        return
    today = db.scalar("SELECT date('now','localtime')")
    row = db.query_one(
        "SELECT"
        " COUNT(*) AS total,"
        " SUM(CASE WHEN status = 'حاضر' THEN 1 ELSE 0 END) AS present,"
        " SUM(CASE WHEN status = 'متأخر' THEN 1 ELSE 0 END) AS late,"
        " SUM(CASE WHEN status = 'غائب' THEN 1 ELSE 0 END) AS absent,"
        " SUM(CASE WHEN status = 'بعذر' THEN 1 ELSE 0 END) AS excused"
        " FROM attendance WHERE date = ?",
        (today,),
    )
    data = dict(row) if row else {}
    total = int(data.get("total") or 0)
    if not total:
        layout.alert(f"لم يُسجَّل أي حضور اليوم ({today}) — ابدأ من «تسجيل الحضور بـ QR».", "info")
        return
    present = int(data.get("present") or 0)
    late = int(data.get("late") or 0)
    absent = int(data.get("absent") or 0)
    excused = int(data.get("excused") or 0)
    layout.kpi_cards(
        [
            {"label": f"حضور اليوم ({today})", "value": total},
            {"label": "حاضر", "value": present},
            {"label": "متأخر", "value": late, "kind": "warn" if late else ""},
            {"label": "بعذر", "value": excused},
            {"label": "غائب", "value": absent, "kind": "danger" if absent else ""},
        ]
    )
    charts.progress("نسبة الحضور (حاضر + متأخر)", present + late, total)


def _render_distribution() -> None:
    classes = classes_service.list_classes()
    data = [(f"{klass['name']} ({klass['level_name']})", int(klass["enrolled"])) for klass in classes]
    charts.bar_chart("توزيع الطلاب على الفصول", data, hint="العدد الحالي للتسجيلات الفعّالة")

    levels = levels_service.list_levels()
    if levels:
        labels = [(level["name"], int(level.get("classes_count") or 0)) for level in levels]
        charts.bar_chart("الفصول لكل مرحلة", labels)

    layout.section("السعة المتاحة", "مقارنة المسجّلين بسعة كل فصل")
    for klass in classes:
        capacity = int(klass["capacity"])
        enrolled = int(klass["enrolled"])
        kind = ""
        if capacity and enrolled >= capacity:
            kind = "danger"
        elif capacity and enrolled / capacity >= 0.85:
            kind = "warn"
        charts.progress(f"{klass['name']} — {klass['level_name']}", enrolled, capacity, kind)


def _render_recent_activity() -> None:
    layout.section("آخر العمليات (سجل التدقيق)")
    rows = audit.recent(limit=10)
    components.table(
        ["الوقت", "المستخدم", "العملية", "التفاصيل"],
        [
            [
                row.get("at") or "—",
                row.get("username") or "—",
                row.get("action") or "—",
                row.get("details") or "—",
            ]
            for row in rows
        ],
        empty_message="لا توجد عمليات مسجّلة بعد",
    )
    layout.section("معلومات النظام")
    from core import db

    components.kv_table(
        [
            ("إصدار مخطط قاعدة البيانات", db.schema_version()),
            ("موقع قاعدة البيانات", str(config.db_path())),
        ]
    )
    layout.footer()
