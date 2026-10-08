"""شاشة البنية الأكاديمية: السنوات الدراسية، الفصول (الفترات)، المراحل."""
from __future__ import annotations

from pywebio.input import input, select
from pywebio.output import put_buttons
from pywebio.pin import pin, put_select
from pywebio.session import go_app

from core import auth
from core.services import levels_service, terms_service, years_service
from ui import components, layout, options

APP = "academic"


def academic() -> None:
    """شاشة إدارة البنية الأكاديمية."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="البنية الأكاديمية")
    with components.error_boundary("البنية الأكاديمية"):
        _years_section()
        _terms_section()
        _levels_section()
        layout.footer()


# ---------------- السنوات الدراسية ----------------

def _years_section() -> None:
    layout.section("السنوات الدراسية", "يجب تحديد سنة حالية واحدة ليعمل التسجيل والحضور")
    rows = years_service.list_years()
    components.table(
        ["السنة", "من", "إلى", "الحالة"],
        [
            [
                row["name"],
                row.get("start_date") or "—",
                row.get("end_date") or "—",
                components.chip("الحالية", "ok") if row["is_current"] else components.chip("سابقة", "muted"),
            ]
            for row in rows
        ],
        empty_message="لا توجد سنوات دراسية — ابدأ بإضافة سنة",
    )
    if rows:
        put_select(
            "year_pick",
            options=[{"label": row["name"], "value": str(row["id"])} for row in rows],
            label="السنة الدراسية",
        )
    put_buttons(
        [
            {"label": "➕ سنة جديدة", "value": "add", "color": "primary"},
            {"label": "✓ تعيين كحالية", "value": "current", "color": "secondary"},
            {"label": "✎ تعديل", "value": "edit", "color": "secondary"},
            {"label": "🗑 حذف", "value": "delete", "color": "danger"},
        ],
        onclick=_handle_year,
        small=True,
    )


def _handle_year(value: str) -> None:
    if value == "add":
        data = components.form_modal(
            "إضافة سنة دراسية",
            [
                input("اسم السنة (مثال: 2026/2027) *", name="name", required=True),
                input("تاريخ البداية", name="start_date", placeholder="2026-09-01", required=False),
                input("تاريخ النهاية", name="end_date", placeholder="2027-06-30", required=False),
                select(
                    "تعيينها كسنة حالية؟",
                    name="make_current",
                    options=[
                        {"label": "نعم", "value": "1"},
                        {"label": "لا", "value": "0"},
                    ],
                    value="1",
                    required=False,
                ),
            ],
        )
        if not data:
            return
        with components.error_boundary("إضافة سنة"):
            years_service.create_year(
                data["name"],
                data["start_date"],
                data["end_date"],
                make_current=data.get("make_current") == "1",
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تمت إضافة السنة الدراسية")
            go_app(APP, new_window=False)
        return

    picked = pin["year_pick"]
    if not picked:
        components.toast_error("اختر السنة الدراسية أولاً")
        return
    year_id = int(picked)
    if value == "current":
        with components.error_boundary("تعيين السنة الحالية"):
            years_service.set_current_year(year_id, actor=auth.current_user(), ip=auth.client_ip())
            components.toast_ok("تم تعيين السنة كحالية")
            go_app(APP, new_window=False)
    elif value == "edit":
        year = years_service.get_year(year_id)
        data = components.form_modal(
            f"تعديل السنة: {year['name']}",
            [
                input("اسم السنة *", name="name", value=year["name"], required=True),
                input("تاريخ البداية", name="start_date", value=year.get("start_date") or "", required=False),
                input("تاريخ النهاية", name="end_date", value=year.get("end_date") or "", required=False),
            ],
        )
        if not data:
            return
        with components.error_boundary("تعديل سنة"):
            years_service.update_year(
                year_id,
                data["name"],
                data["start_date"],
                data["end_date"],
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تم حفظ التعديلات")
            go_app(APP, new_window=False)
    elif value == "delete":
        year = years_service.get_year(year_id)
        if not components.confirm(f"حذف السنة «{year['name']}»؟", "حذف", "إلغاء"):
            return
        with components.error_boundary("حذف سنة"):
            years_service.delete_year(year_id, actor=auth.current_user(), ip=auth.client_ip())
            components.toast_ok("تم حذف السنة")
            go_app(APP, new_window=False)


# ---------------- الفصول الدراسية (الفترات) ----------------

def _terms_section() -> None:
    layout.section("الفصول الدراسية", "فصل دراسي واحد فقط يكون «حالياً» في كل سنة")
    rows = terms_service.list_terms()
    components.table(
        ["الفصل", "السنة", "من", "إلى", "الحالة"],
        [
            [
                row["name"],
                row["year_name"],
                row.get("start_date") or "—",
                row.get("end_date") or "—",
                components.chip("الحالي", "ok") if row["is_current"] else components.chip("—", "muted"),
            ]
            for row in rows
        ],
        empty_message="لا توجد فصول دراسية",
    )
    if rows:
        put_select(
            "term_pick",
            options=[
                {"label": f"{row['name']} — {row['year_name']}", "value": str(row["id"])}
                for row in rows
            ],
            label="الفصل الدراسي",
        )
    put_buttons(
        [
            {"label": "➕ فصل دراسي", "value": "add", "color": "primary"},
            {"label": "✓ تعيين كحالي", "value": "current", "color": "secondary"},
            {"label": "✎ تعديل", "value": "edit", "color": "secondary"},
            {"label": "🗑 حذف", "value": "delete", "color": "danger"},
        ],
        onclick=_handle_term,
        small=True,
    )


def _handle_term(value: str) -> None:
    if value == "add":
        data = components.form_modal(
            "إضافة فصل دراسي",
            [
                select("السنة الدراسية *", name="year_id", options=options.years(), required=True),
                input("اسم الفصل (مثال: الفصل الأول) *", name="name", required=True),
                input("تاريخ البداية", name="start_date", required=False),
                input("تاريخ النهاية", name="end_date", required=False),
                select(
                    "تعيينه كحالي؟",
                    name="make_current",
                    options=[{"label": "نعم", "value": "1"}, {"label": "لا", "value": "0"}],
                    value="1",
                    required=False,
                ),
            ],
        )
        if not data:
            return
        with components.error_boundary("إضافة فصل دراسي"):
            terms_service.create_term(
                data["year_id"],
                data["name"],
                data["start_date"],
                data["end_date"],
                make_current=data.get("make_current") == "1",
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تمت إضافة الفصل الدراسي")
            go_app(APP, new_window=False)
        return

    picked = pin["term_pick"]
    if not picked:
        components.toast_error("اختر الفصل الدراسي أولاً")
        return
    term_id = int(picked)
    if value == "current":
        with components.error_boundary("تعيين الفصل الحالي"):
            terms_service.set_current_term(term_id, actor=auth.current_user(), ip=auth.client_ip())
            components.toast_ok("تم تعيين الفصل كحالي")
            go_app(APP, new_window=False)
    elif value == "edit":
        term = terms_service.get_term(term_id)
        data = components.form_modal(
            f"تعديل الفصل: {term['name']}",
            [
                input("اسم الفصل *", name="name", value=term["name"], required=True),
                input("تاريخ البداية", name="start_date", value=term.get("start_date") or "", required=False),
                input("تاريخ النهاية", name="end_date", value=term.get("end_date") or "", required=False),
            ],
        )
        if not data:
            return
        with components.error_boundary("تعديل فصل دراسي"):
            terms_service.update_term(
                term_id,
                data["name"],
                data["start_date"],
                data["end_date"],
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تم حفظ التعديلات")
            go_app(APP, new_window=False)
    elif value == "delete":
        term = terms_service.get_term(term_id)
        if not components.confirm(f"حذف الفصل «{term['name']}»؟", "حذف", "إلغاء"):
            return
        with components.error_boundary("حذف فصل دراسي"):
            terms_service.delete_term(term_id, actor=auth.current_user(), ip=auth.client_ip())
            components.toast_ok("تم حذف الفصل")
            go_app(APP, new_window=False)


# ---------------- المراحل ----------------

def _levels_section() -> None:
    layout.section("المراحل", "مثال: الابتدائي / المتوسط / الثانوي")
    rows = levels_service.list_levels()
    components.table(
        ["المرحلة", "الترتيب", "عدد الفصول", "عدد المواد", "ملاحظات"],
        [
            [
                row["name"],
                row["sort_order"],
                row.get("classes_count") or 0,
                row.get("subjects_count") or 0,
                row.get("notes") or "—",
            ]
            for row in rows
        ],
        empty_message="لا توجد مراحل — أضف مرحلة أولاً",
    )
    if rows:
        put_select(
            "level_pick",
            options=[{"label": row["name"], "value": str(row["id"])} for row in rows],
            label="المرحلة",
        )
    put_buttons(
        [
            {"label": "➕ مرحلة", "value": "add", "color": "primary"},
            {"label": "✎ تعديل", "value": "edit", "color": "secondary"},
            {"label": "🗑 حذف", "value": "delete", "color": "danger"},
        ],
        onclick=_handle_level,
        small=True,
    )


def _handle_level(value: str) -> None:
    if value == "add":
        data = components.form_modal(
            "إضافة مرحلة",
            [
                input("اسم المرحلة *", name="name", required=True),
                input("الترتيب (رقم)", name="sort_order", required=False),
                input("ملاحظات", name="notes", required=False),
            ],
        )
        if not data:
            return
        with components.error_boundary("إضافة مرحلة"):
            levels_service.create_level(
                data["name"],
                data.get("sort_order"),
                data.get("notes"),
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تمت إضافة المرحلة")
            go_app(APP, new_window=False)
        return

    picked = pin["level_pick"]
    if not picked:
        components.toast_error("اختر المرحلة أولاً")
        return
    level_id = int(picked)
    if value == "edit":
        level = levels_service.get_level(level_id)
        data = components.form_modal(
            f"تعديل المرحلة: {level['name']}",
            [
                input("اسم المرحلة *", name="name", value=level["name"], required=True),
                input("الترتيب", name="sort_order", value=str(level["sort_order"]), required=False),
                input("ملاحظات", name="notes", value=level.get("notes") or "", required=False),
            ],
        )
        if not data:
            return
        with components.error_boundary("تعديل مرحلة"):
            levels_service.update_level(
                level_id,
                data["name"],
                data.get("sort_order"),
                data.get("notes"),
                actor=auth.current_user(),
                ip=auth.client_ip(),
            )
            components.toast_ok("تم حفظ التعديلات")
            go_app(APP, new_window=False)
    elif value == "delete":
        level = levels_service.get_level(level_id)
        if not components.confirm(f"حذف المرحلة «{level['name']}»؟", "حذف", "إلغاء"):
            return
        with components.error_boundary("حذف مرحلة"):
            levels_service.delete_level(level_id, actor=auth.current_user(), ip=auth.client_ip())
            components.toast_ok("تم حذف المرحلة")
            go_app(APP, new_window=False)
