"""خدمة التسجيل الموحّد للأشخاص (طالب/معلّم) مع حساب دخول في عملية واحدة.

تُنشئ هذه الخدمة حساب مستخدم + سجل شخص (طالب أو معلّم) داخل **معاملة واحدة**،
فإما أن ينجح الإثنان أو يُلغى الإثنان (لا حسابات بلا أشخاص ولا أشخاص بلا حسابات).
كل العمليات التحققية (اسم المستخدم/كلمة المرور/الاسم) تُنفَّذ هنا لا في الواجهة.
"""
from __future__ import annotations

from typing import Any

from .. import config, db
from ..exceptions import DuplicateError, ValidationError
from ..repos import audit
from ..repos import users as users_repo
from ..repos import students as students_repo
from .. import security, validators as v
from . import students_service, teachers_service, users_service

# أنواع الأشخاص المدعومة في شاشة التسجيل الموحّدة.
PERSON_KINDS = {
    "student": (config.ROLE_STUDENT, "طالب"),
    "teacher": (config.ROLE_TEACHER, "معلّم"),
}


def _clean_kind(kind: Any) -> str:
    text = str(kind or "").strip().lower()
    if text not in PERSON_KINDS:
        raise ValidationError("نوع الشخص يجب أن يكون «طالب» أو «معلّم»")
    return text


def validate_registration(data: dict[str, Any]) -> tuple[str, str] | None:
    """فحوصات نموذج التسجيل قبل الإرسال — تُعيد (اسم الحقل, رسالة الخطأ) أو None.

    تُستدعى من الواجهة كدالة ``validate`` في ``input_group`` فتبقى البيانات
    معبّأة عند الخطأ. القواعد نفسها منطق الأعمال (هنا) لا في الواجهة.
    """
    if str(data.get("kind") or "").strip().lower() not in PERSON_KINDS:
        return ("kind", "اختر النوع: طالب أو معلّم")
    try:
        v.require_text(data.get("full_name"), "الاسم الكامل", min_len=3, max_len=80)
    except ValidationError as exc:
        return ("full_name", str(exc))
    try:
        clean_username = users_service._validate_username(str(data.get("username") or ""))
    except ValidationError as exc:
        return ("username", str(exc))
    password = str(data.get("password") or "")
    if password != str(data.get("password_confirm") or ""):
        return ("password_confirm", "كلمتا المرور غير متطابقتين")
    try:
        security.validate_password_policy(password, clean_username)
    except ValidationError as exc:
        return ("password", str(exc))
    if users_repo.get_by_username(clean_username):
        return ("username", f"اسم المستخدم «{clean_username}» مستخدم مسبقاً")
    return None


def register_person(
    kind: str,
    full_name: str,
    username: str,
    password: str,
    *,
    gender: str | None = None,
    national_id: str | None = None,
    birth_date: str | None = None,
    guardian_name: str | None = None,
    guardian_phone: str | None = None,
    address: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    specialty: str | None = None,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> dict[str, Any]:
    """تسجيل شخص (طالب أو معلّم) مع حساب دخول في معاملة واحدة.

    يُعيد قاموساً فيه معرّفات: ``{"user_id", "person_id", "kind", "username", "role"}``.
    """
    kind = _clean_kind(kind)
    role, _label = PERSON_KINDS[kind]
    full_name = v.require_text(full_name, "الاسم الكامل", min_len=3, max_len=80)
    # التحقق المسبق من اسم المستخدم وكلمة المرور (يرفع رسائل عربية واضحة قبل المعاملة).
    username = users_service._validate_username(username)
    security.validate_password_policy(password, username)
    if users_repo.get_by_username(username):
        raise DuplicateError(f"اسم المستخدم «{username}» مستخدم مسبقاً")

    with db.transaction() as conn:
        # حارس تعارض نهائي داخل المعاملة (لمنافسة محتملة).
        if users_repo.username_taken(username, conn):
            raise DuplicateError(f"اسم المستخدم «{username}» مستخدم مسبقاً")

        user_id = users_service.create_user(
            username=username,
            full_name=full_name,
            role=role,
            password=password,
            must_change=True,  # يُلزم بتغيير كلمة المرور عند أول دخول.
            is_active=True,
            conn=conn,
            actor=actor,
            ip=ip,
        )

        if kind == "student":
            student_no = students_repo.next_student_no(_current_year_prefix())
            payload = {
                "full_name": full_name,
                "gender": gender,
                "national_id": national_id,
                "birth_date": birth_date,
                "guardian_name": guardian_name,
                "guardian_phone": guardian_phone,
                "address": address,
                "status": "منتظم",
            }
            person_id = students_service.create_student(
                payload,
                year_name=_current_year_prefix(),
                user_id=user_id,
                conn=conn,
                actor=actor,
                ip=ip,
            )
            entity = "students"
            action = f"تسجيل طالب مع حساب دخول ({student_no})"
        else:
            person_id = teachers_service.create_teacher(
                full_name=full_name,
                national_id=national_id,
                phone=phone,
                email=email,
                specialty=specialty,
                salary=0,
                user_id=user_id,
                conn=conn,
                actor=actor,
                ip=ip,
            )
            entity = "teachers"
            action = "تسجيل معلّم مع حساب دخول"

        audit.log(
            action,
            entity=entity,
            entity_id=person_id,
            details=f"الحساب: {username} (معرّف المستخدم {user_id})",
            user=actor,
            ip=ip,
            conn=conn,
        )

    return {
        "user_id": user_id,
        "person_id": person_id,
        "kind": kind,
        "username": username,
        "role": role,
    }


def _current_year_prefix() -> str:
    """بادئة السنة الحالية لتوليد رقم الطالب (مثل 2026)."""
    try:
        from . import years_service

        year = years_service.current_year()
        if year and year.get("name"):
            return str(year["name"]).split("/")[0].strip()
    except Exception:  # pragma: no cover - لا يوجد سنة محددة
        pass
    from datetime import date

    return date.today().strftime("%Y")
