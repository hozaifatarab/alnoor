"""شاشة البطاقة المخصصة: استمارة بيانات يدوية → توليد بطاقة QR فوري داخل الموقع.

نافذة خاصة مستقلة عن بطاقات الفصول: يُدخل المستخدم (أو المدير) بيانات
محددة في استمارة (الاسم، الرقم الأكاديمي، الفصل/القسم، الحالة) فيولّد
النظام بطاقة QR موقّعة بنفس محرك التوقيع القائم، فتكون قابلة للمسح
من كاميرا تسجيل الحضور، مع طباعة وتنزيل PNG.
"""
from __future__ import annotations

from pywebio.input import input, select
from pywebio.output import put_buttons, put_html
from pywebio.session import download, go_app

from core import auth, config, qr
from core.exceptions import ValidationError
from core.repos import settings as settings_repo
from core.services import years_service
from ui import components, layout, options

APP = "id_cards"
STATUS_OPTIONS = ("منتظم", "موقوف", "مسجّل", "منقول")


def id_cards() -> None:
    """استمارة بيانات → بطاقة QR — للمدير فقط."""
    user = auth.current_user()
    auth.require(config.PERM_STUDENT_CARDS, user)
    layout.page_header(user, active=APP, subtitle="بطاقة مخصصة (QR) — للمدير فقط")

    with components.error_boundary("البطاقة المخصصة"):
        auth.require(config.PERM_STUDENT_CARDS)
        while True:
            data = _entry_form()
            if data is None:
                return
            _render_result(data)


def _entry_form() -> dict | None:
    """استمارة إدخال البيانات المحددة للبطاقة."""
    layout.section(
        "بيانات البطاقة",
        "املأ الاستمارة ثم اضغط «توليد البطاقة» لعرضها فوراً داخل الصفحة",
    )
    class_options = [{"label": "— بدون فصل (بطاقة عامة) —", "value": ""}]
    class_options.extend(options.classes())
    return components.form_modal(
        "استمارة بيانات البطاقة",
        [
            input("الاسم الكامل *", name="full_name", required=True, placeholder="مثال: محمد أحمد"),
            input(
                "الرقم الأكاديمي *",
                name="student_no",
                required=True,
                placeholder="مثال: STD-2026-0001",
                help_text="حروف لاتينية كبيرة وأرقام وشرطات فقط",
            ),
            select("الفصل / القسم", name="class_name", options=class_options, required=False),
            select("الحالة", name="status", options=[{"label": s, "value": s} for s in STATUS_OPTIONS], value="منتظم"),
            select(
                "حجم العرض",
                name="scale",
                options=[
                    {"label": "عادي (مناسب للشاشة)", "value": "4"},
                    {"label": "كبير (مناسب للطباعة)", "value": "6"},
                ],
                value="4",
            ),
        ],
        help_text="الحقول المعلّمة بـ * إلزامية — البطاقة المولّدة موقّعة وقابلة للمسح من الكاميرا",
        cancelable=True,
    )


def _render_result(data: dict) -> None:
    """التحقق من البيانات ثم عرض البطاقة المولّدة مع إجراءاتها."""
    try:
        full_name = _clean_text(data.get("full_name"), "الاسم الكامل", 2, 80)
        student_no = _clean_student_no(data.get("student_no"))
        class_name = str(data.get("class_name") or "").strip()
        status = str(data.get("status") or "منتظم").strip()
        scale = int(data.get("scale") or 4)
    except ValidationError as exc:
        layout.alert(str(exc), "error")
        return
    institution = settings_repo.institution_name()
    year_name = years_service.current_year_name()
    badge = qr.generate_student_badge_html(
        {"student_no": student_no, "full_name": full_name, "status": status},
        class_name,
        institution,
        year_name,
    ).replace('scale="4"', f'scale="{scale}"')
    layout.section("البطاقة المولّدة", "امسحها من الكاميرا للتحقق الفوري من التوقيع")
    put_html(f'<div style="text-align:center">{badge}</div>')
    put_buttons(
        [
            {"label": "🖨 طباعة", "value": "print", "color": "primary"},
            {"label": "⬇ تنزيل PNG", "value": "download", "color": "secondary"},
            {"label": "↺ بطاقة جديدة", "value": "again", "color": "secondary"},
            {"label": "العودة للوحة المعلومات", "value": "home", "color": "secondary"},
        ],
        onclick=lambda value: _handle(value, full_name, student_no, class_name, status, year_name),
        small=True,
    )
    layout.footer()


def _handle(value: str, full_name: str, student_no: str, class_name: str, status: str, year_name: str) -> None:
    if value == "print":
        from pywebio.session import run_js

        components.toast_ok("افتح نافذة الطباعة من المتصفح (Ctrl+P)")
        run_js("window.print()")
    elif value == "download":
        payload = qr.make_payload(student_no, year_name)
        download(f"qr-{student_no}.png", qr.generate_qr_png_bytes(payload, scale=10))
        components.toast_ok("تم تجهيز ملف الرمز للتنزيل")
    elif value == "again":
        go_app(APP, new_window=False)
    elif value == "home":
        go_app("dashboard", new_window=False)


def _clean_text(value: object, field: str, min_len: int = 2, max_len: int = 80) -> str:
    from core import validators

    text = validators.require_text(value, field, min_len=min_len, max_len=max_len)
    return text


def _clean_student_no(value: object) -> str:
    from core import validators

    raw = validators.normalize_digits(str(value or "")).strip().upper()
    if len(raw) < 3 or len(raw) > 24:
        raise ValidationError("الرقم الأكاديمي من 3 إلى 24 حرفاً")
    if any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in raw):
        raise ValidationError("الرقم الأكاديمي: حروف لاتينية وأرقام وشرطات فقط")
    return raw
