"""شاشة الإعدادات: بيانات المؤسسة، السنة/الفصل الحالي، إعدادات الحضور، سجل التدقيق."""
from __future__ import annotations

from pywebio.input import input, input_group, select
from pywebio.output import put_buttons
from pywebio.session import go_app

from core import auth, config, security
from core.repos import settings as repo
from core.services import terms_service, years_service
from ui import components, layout

APP = "settings"


def settings() -> None:
    """شاشة إعدادات النظام."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="الإعدادات")
    with components.error_boundary("الإعدادات"):
        current = repo.all_settings()
        _general_form(current)
        _academic_context(current)
        _advanced_form(current)
        _render_audit()
        layout.footer()


def _general_form(current: dict[str, str]) -> None:
    layout.section("بيانات المؤسسة", "تظهر في الترويسة والطباعة والتقارير")
    data = input_group(
        "",
        [
            input("اسم المؤسسة *", name="institution_name", value=current["institution_name"], required=True),
            input("رمز العملة", name="currency", value=current["currency"], required=False),
            input("الهاتف", name="phone", value=current["phone"], required=False),
            input("العنوان", name="address", value=current["address"], required=False),
            select(
                "لون الواجهة (الثيم)",
                name="theme",
                options=[
                    {"label": "minty (أخضر فاتح)", "value": "minty"},
                    {"label": "yeti (رمادي أزرق)", "value": "yeti"},
                    {"label": "dark (داكن)", "value": "dark"},
                    {"label": "sketchy (يدوي)", "value": "sketchy"},
                ],
                value=current["theme"] if current["theme"] in ("minty", "yeti", "dark", "sketchy") else "minty",
                required=False,
            ),
        ],
        cancelable=False,
    )
    with components.error_boundary("حفظ بيانات المؤسسة"):
        repo.set_many(data)
        components.toast_ok("تم حفظ بيانات المؤسسة (يُطبَّق لون الواجهة بعد إعادة التشغيل)")
        go_app(APP, new_window=False)


def _academic_context(current: dict[str, str]) -> None:
    year = years_service.current_year()
    term = terms_service.current_term()
    layout.section("السنة والفصل الحاليان", "يُستخدمان افتراضياً في التسجيل والحضور والدرجات")
    components.kv_table(
        [
            ("السنة الحالية", year["name"] if year else "— غير محددة —"),
            ("الفصل الحالي", term["name"] if term else "— غير محدد —"),
            ("بداية السنة", (year or {}).get("start_date") or "—"),
            ("نهاية السنة", (year or {}).get("end_date") or "—"),
        ]
    )
    put_buttons(
        [
            {"label": "إدارة البنية الأكاديمية", "value": "academic", "color": "secondary"},
        ],
        onclick=lambda value: go_app(value, new_window=False),
        small=True,
    )


def _advanced_form(current: dict[str, str]) -> None:
    layout.section(
        "إعدادات الحضور",
        "تُطبَّق عند تسجيل الحضور بـ QR والإدخال اليدوي",
    )
    data = input_group(
        "",
        [
            input(
                "دقائق التأخير بعد بداية الحصة",
                name="late_after_minutes",
                value=current["late_after_minutes"],
                required=False,
            ),
            input("وقت بداية الحصة الافتراضي", name="default_period_start", value=current["default_period_start"], required=False),
            input("وقت إغلاق اليوم الدراسي", name="day_close_time", value=current["day_close_time"], required=False),
            input(
                "حد الإنذار بعدد أيام الغياب",
                name="absence_alert_threshold",
                value=current["absence_alert_threshold"],
                required=False,
            ),
            input(
                "أيام العطلة (تواريخ بصيغة 2026-09-05 مفصولة بفواصل)",
                name="holidays",
                value=current["holidays"],
                required=False,
            ),
        ],
        cancelable=False,
    )
    with components.error_boundary("حفظ إعدادات الحضور"):
        repo.set_many(
            {
                "late_after_minutes": data["late_after_minutes"],
                "default_period_start": data["default_period_start"],
                "day_close_time": data["day_close_time"],
                "absence_alert_threshold": data["absence_alert_threshold"],
                "holidays": data["holidays"],
            }
        )
        components.toast_ok("تم حفظ إعدادات الحضور")
        go_app(APP, new_window=False)


def _render_audit() -> None:
    from core.repos import audit

    layout.section("الأمان وسجل التدقيق", "كل عملية حساسة تُقيَّد تلقائياً")
    components.kv_table(
        [
            ("عدد سجلات التدقيق", audit.count()),
            ("مفتاح توقيع بطاقات QR", "مُعرَّف" if repo.get("qr_secret") else "غير مُعرَّف بعد"),
            ("أقصى محاولات دخول", config.MAX_LOGIN_ATTEMPTS),
            ("مدة قفل الحساب (دقيقة)", config.LOCK_MINUTES),
            ("الحد الأدنى لكلمة المرور", config.MIN_PASSWORD_LENGTH),
        ]
    )
    put_buttons(
        [
            {"label": "🔐 توليد/تدوير مفتاح توقيع QR", "value": "rotate", "color": "warn"},
            {"label": "📜 سجل التدقيق الكامل", "value": "audit_log", "color": "secondary"},
        ],
        onclick=_audit_actions,
        small=True,
    )


def _audit_actions(value: str) -> None:
    if value == "audit_log":
        go_app("audit_log", new_window=False)
        return
    if not components.confirm(
        "تدوير المفتاح سيُبطل صلاحية بطاقات QR المطبوعة حالياً (تحتاج إعادة طباعة). متابعة؟",
        "تدوير المفتاح",
        "إلغاء",
    ):
        return
    with components.error_boundary("تدوير مفتاح QR"):
        repo.set_value("qr_secret", security.new_secret(32))
        components.toast_ok("تم تدوير مفتاح التوقيع")
        go_app(APP, new_window=False)
