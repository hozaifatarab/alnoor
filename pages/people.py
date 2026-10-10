"""شاشة التسجيل الموحّد: تسجيل طالب أو معلّم مع حساب دخول في نموذج واحد.

مخصّصة للمدير (صلاحية إدارة المستخدمين). عند الإرسال تُنشأ عملية واحدة
تُنشئ حساب المستخدم + سجل الشخص (طالب/معلّم) معاً — إمّا نجاح الاثنين
أو إلغاؤهما معاً.
"""
from __future__ import annotations

from typing import Any

from pywebio.input import PASSWORD, input, input_group, select
from pywebio.output import put_error, put_scope, use_scope
from pywebio.session import go_app

from core import auth
from core.exceptions import AppError
from core.services import people_service
from ui import components, layout

APP = "people"
_ERROR_SCOPE = "people_errors"


def people() -> None:
    """شاشة تسجيل الطلاب والمعلّمين مع إنشاء حسابات دخول."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="تسجيل الطلاب والمعلّمين")
    with components.error_boundary("تسجيل شخص جديد"):
        _render_hint()
        put_scope(_ERROR_SCOPE)
        _form(user)


def _render_hint() -> None:
    layout.section(
        "تسجيل طالب أو معلّم مع حساب دخول",
        "اختر النوع ثم أدخل الاسم واسم المستخدم وكلمة المرور — يُنشأ الحساب فوراً.",
    )
    layout.alert("يُطبَّق تغيير كلمة المرور إلزامياً عند أول دخول للحساب الجديد.", "info")


def _form(user: dict[str, Any] | None) -> None:
    """النموذج الأساسي (مع تحقق داخل النموذج) ثم البيانات الإختيارية."""
    components.password_toggle_hint()
    while True:
        data = input_group(
            "البيانات الأساسية",
            [
                select(
                    "نوع الشخص *",
                    name="kind",
                    options=[
                        {"label": "طالب", "value": "student"},
                        {"label": "معلّم", "value": "teacher"},
                    ],
                    value="student",
                ),
                input(
                    "الاسم الكامل *",
                    name="full_name",
                    placeholder="مثال: أحمد محمد العلي",
                ),
                input(
                    "اسم المستخدم *",
                    name="username",
                    placeholder="حروف إنجليزية وأرقام بدون مسافات",
                    help_text="يُستخدم لتسجيل الدخول",
                    autocomplete="off",
                ),
                input(
                    "كلمة المرور *",
                    name="password",
                    type=PASSWORD,
                    placeholder="8 أحرف على الأقل تتضمن حرفاً ورقماً",
                    autocomplete="off",
                ),
                input(
                    "تأكيد كلمة المرور *",
                    name="password_confirm",
                    type=PASSWORD,
                    autocomplete="off",
                ),
            ],
            validate=people_service.validate_registration,
            cancelable=True,
        )
        if data is None:  # ألغى المستخدم النموذج
            return

        extra = _extra_fields(data["kind"])
        with use_scope(_ERROR_SCOPE, clear=True):
            try:
                result = people_service.register_person(
                    kind=data["kind"],
                    full_name=data["full_name"],
                    username=data["username"],
                    password=data["password"],
                    actor=user,
                    ip=auth.client_ip(),
                    **extra,
                )
            except AppError as exc:
                put_error(f"⚠ {exc.user_message}")
                continue  # إعادة عرض النموذج للمحاولة مجدداً
        break

    kind_label = "طالب" if result["kind"] == "student" else "معلّم"
    components.toast_ok(
        f"تم تسجيل {kind_label} وإنشاء حساب الدخول «{result['username']}» بنجاح"
    )
    go_app(APP, new_window=False)


def _extra_fields(kind: str) -> dict[str, Any]:
    """حقول إختيارية حسب النوع — الإرسال الفارغ يعني التسجيل بالبيانات الأساسية فقط.

    النموذج غير قابل للإلغاء (كل حقوله اختيارية) حتى لا تُفقد البيانات الأساسية
    المعبّأة في الخطوة السابقة؛ للرجوع استخدم زر الرجوع في المتصفح.
    """
    if kind == "student":
        fields = [
            select(
                "الجنس",
                name="gender",
                options=[
                    {"label": "— —", "value": ""},
                    {"label": "ذكر", "value": "ذكر"},
                    {"label": "أنثى", "value": "أنثى"},
                ],
                value="",
                required=False,
            ),
            input("رقم الهوية", name="national_id", required=False),
            input(
                "تاريخ الميلاد", name="birth_date", required=False, help_text="مثال: 2015-05-10"
            ),
            input("اسم ولي الأمر", name="guardian_name", required=False),
            input("جوال ولي الأمر", name="guardian_phone", required=False),
            input("العنوان", name="address", required=False),
        ]
    else:
        fields = [
            input("رقم الهوية", name="national_id", required=False),
            input("الجوال", name="phone", required=False),
            input("البريد الإلكتروني", name="email", required=False),
            input("التخصص", name="specialty", required=False, placeholder="مثال: رياضيات"),
        ]
    label = "بيانات الطالب (اختيارية)" if kind == "student" else "بيانات المعلّم (اختيارية)"
    return input_group(label, fields, cancelable=False) or {}
