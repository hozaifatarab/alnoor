"""شاشة بطاقات الطلاب بـ QR: عرض، طباعة، وتنزيل طبقة كاملة لفصل."""
from __future__ import annotations

from pywebio.input import input_group, select
from pywebio.output import put_buttons, put_html
from pywebio.session import go_app

from core import auth, config, qr
from core.repos import settings as settings_repo
from core.services import classes_service, enrollments_service, years_service
from ui import components, layout, options

APP = "student_cards"


def student_cards() -> None:
    """توليد بطاقات QR للطلاب — للمدير فقط (مُقيَّدة بالمسار + فحص دفاعي هنا)."""
    user = auth.current_user()
    auth.require(config.PERM_STUDENT_CARDS, user)
    layout.page_header(user, active=APP, subtitle="بطاقات الطلاب (QR) — للمدير فقط")

    with components.error_boundary("بطاقات الطلاب"):
        auth.require(config.PERM_STUDENT_CARDS)
        class_options = options.classes()
        if not class_options:
            layout.alert("لا توجد فصول معرّفة بعد.", "warn")
            go_app("classes", new_window=False)
            return

        data = input_group(
            "اختيار الفصل",
            [
                select("الفصل *", name="class_id", options=class_options, required=True),
                select(
                    "حجم العرض",
                    name="scale",
                    options=[
                        {"label": "عادي (مناسب للشاشة)", "value": "4"},
                        {"label": "كبير (مناسب للطباعة)", "value": "6"},
                    ],
                    required=False,
                ),
            ],
            cancelable=False,
        )
        class_id = int(data["class_id"])
        scale = int(data.get("scale") or 4)
        _render_cards(class_id, scale)

        put_buttons(
            [
                {"label": "🖨 طباعة البطاقات", "value": "print", "color": "primary"},
                {"label": "⬇ تنزيل رمز طالب واحد (PNG)", "value": "download", "color": "secondary"},
            ],
            onclick=lambda value: _handle(value, class_id, scale),
            small=True,
        )
        layout.footer()


def _render_cards(class_id: int, scale: int = 4) -> None:
    klass = classes_service.get_class(class_id)
    students = enrollments_service.roster(class_id)
    institution = settings_repo.institution_name()
    year_name = (klass["year_name"] if klass else "") or years_service.current_year_name()

    layout.section(
        f"بطاقات {klass['name'] if klass else ''}",
        f"{len(students)} بطاقة — تعمل البطاقات كبديل معتمد للتحضير عند تعذّر الكاميرا",
    )
    if not students:
        layout.alert("لا يوجد طلاب مسجّلون في هذا الفصل.", "warn")
        return

    html = ['<div style="display:flex;flex-wrap:wrap;justify-content:center">']
    for student in students:
        html.append(
            qr.generate_student_badge_html(
                {
                    "student_no": student["student_no"],
                    "full_name": student["full_name"],
                    "status": student.get("student_status") or "منتظم",
                },
                klass["name"] if klass else "",
                institution,
                year_name,
            ).replace('scale="4"', f'scale="{scale}"')
        )
    html.append("</div>")
    put_html("".join(html))


def _handle(value: str, class_id: int, scale: int) -> None:
    if value == "print":
        from pywebio.session import run_js

        components.toast_ok("افتح نافذة الطباعة من المتصفح (Ctrl+P)")
        run_js("window.print()")
        return
    if value == "download":
        _download_single(class_id)


def _download_single(class_id: int) -> None:
    students = enrollments_service.roster(class_id)
    if not students:
        components.toast_error("لا يوجد طلاب في هذا الفصل")
        return
    data = components.form_modal(
        "تنزيل رمز QR لطالب",
        [
            select(
                "الطالب *",
                name="student_id",
                options=[
                    {"label": f"{s['student_no']} — {s['full_name']}", "value": str(s["id"])}
                    for s in students
                ],
                required=True,
            )
        ],
    )
    if not data:
        return
    student_id = int(data["student_id"])
    student = next(s for s in students if int(s["id"]) == student_id)
    year_name = years_service.current_year_name()
    payload = qr.make_payload(student["student_no"], year_name)
    png = qr.generate_qr_png_bytes(payload, scale=10)
    from pywebio.session import download

    download(f"qr-{student['student_no']}.png", png)
    components.toast_ok("تم تجهيز ملف الرمز للتنزيل")
