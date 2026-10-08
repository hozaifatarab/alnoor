"""شاشة سجل التدقيق: كل العمليات الحساسة في النظام."""
from __future__ import annotations

from pywebio.input import input, input_group, select

from core import auth, config
from core.repos import audit
from ui import components, layout

APP = "audit_log"


def audit_log() -> None:
    """عرض سجل التدقيق مع تصفية بسيطة."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="سجل التدقيق")
    with components.error_boundary("سجل التدقيق"):
        filters = input_group(
            "تصفية",
            [
                select(
                    "الوحدة (Entity)",
                    name="entity",
                    options=[
                        {"label": "— الكل —", "value": ""},
                        {"label": "users", "value": "users"},
                        {"label": "students", "value": "students"},
                        {"label": "teachers", "value": "teachers"},
                        {"label": "enrollments", "value": "enrollments"},
                        {"label": "classes", "value": "classes"},
                        {"label": "subjects", "value": "subjects"},
                        {"label": "permissions", "value": "permissions"},
                    ],
                    required=False,
                ),
                input("عدد السجلات", name="limit", value="50", required=False),
            ],
            cancelable=False,
        )
        entity = filters.get("entity") or None
        try:
            limit = max(1, min(int(filters.get("limit") or 50), 500))
        except ValueError:
            limit = 50
        rows = audit.recent(limit=limit, entity=entity)
        layout.section("السجلات", f"إجمالي السجلات: {audit.count()} — المعروض: {len(rows)}")
        components.table(
            ["#", "الوقت", "المستخدم", "العملية", "الوحدة", "المعرّف", "التفاصيل", "IP"],
            [
                [
                    index,
                    row.get("at") or "—",
                    row.get("username") or "—",
                    row.get("action") or "—",
                    row.get("entity") or "—",
                    row.get("entity_id") or "—",
                    row.get("details") or "—",
                    row.get("ip") or "—",
                ]
                for index, row in enumerate(rows, start=1)
            ],
            empty_message="لا توجد سجلات تدقيق",
        )
        layout.section("معلومات النظام")
        components.kv_table(
            [
                ("اسم المؤسسة", config.DEFAULT_INSTITUTION_NAME),
                ("إصدار النظام", "المرحلة 1 — الأساس الأكاديمي"),
                ("موقع قاعدة البيانات", str(config.db_path())),
            ]
        )
        layout.footer()
