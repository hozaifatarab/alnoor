"""خدمات الطلاب: الإنشاء/التعديل/الحالة مع قواعد الأعمال والتحقق."""
from __future__ import annotations

from datetime import date
from typing import Any

from .. import config
from ..exceptions import BusinessRuleError, NotFoundError, ValidationError
from ..repos import audit
from ..repos import enrollments as enroll_repo
from ..repos import students as repo
from .. import validators as v


def list_students(
    search: str | None = None,
    status: str | None = None,
    class_id: int | None = None,
    year_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return repo.list_students(search, status, class_id, year_id, limit, offset)


def count_students(
    search: str | None = None,
    status: str | None = None,
    class_id: int | None = None,
    year_id: int | None = None,
) -> int:
    return repo.count_students(search, status, class_id, year_id)


def get_student(student_id: int) -> dict[str, Any]:
    student = repo.get(student_id)
    if student is None:
        raise NotFoundError("الطالب غير موجود")
    return student


def generate_student_no(year_name: str | None = None) -> str:
    """توليد رقم طالب جديد (يُعرض في النموذج كقيمة مقترحة)."""
    return repo.next_student_no(year_name or date.today().strftime("%Y"))


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    full_name = v.require_text(payload.get("full_name"), "الاسم", min_len=3, max_len=80)
    national_id = v.validate_national_id(payload.get("national_id"))
    gender = None
    if str(payload.get("gender") or "").strip():
        gender = v.require_choice(payload.get("gender"), "الجنس", config.GENDERS)
    birth_date = v.parse_date(payload.get("birth_date"), "تاريخ الميلاد", required=False)
    if birth_date and birth_date > date.today().isoformat():
        raise ValidationError("تاريخ الميلاد لا يمكن أن يكون في المستقبل")
    return {
        "full_name": full_name,
        "national_id": national_id,
        "gender": gender,
        "birth_date": birth_date,
        "guardian_name": v.optional_text(payload.get("guardian_name"), 80),
        "guardian_phone": v.validate_phone(payload.get("guardian_phone")),
        "address": v.optional_text(payload.get("address"), 160),
        "status": v.require_choice(
            payload.get("status") or "منتظم", "الحالة", config.STUDENT_STATUSES
        ),
        "notes": v.optional_text(payload.get("notes"), 300),
    }


def create_student(
    payload: dict[str, Any],
    *,
    year_name: str | None = None,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    data = _clean_payload(payload)
    student_no = v.normalize_digits(str(payload.get("student_no") or "").strip())
    if not student_no:
        student_no = repo.next_student_no(year_name or date.today().strftime("%Y"))
    if repo.get_by_no(student_no):
        raise BusinessRuleError(f"رقم الطالب «{student_no}» مسجّل مسبقاً")
    student_id = repo.create(
        student_no=student_no,
        full_name=data["full_name"],
        national_id=data["national_id"],
        gender=data["gender"],
        birth_date=data["birth_date"],
        guardian_name=data["guardian_name"],
        guardian_phone=data["guardian_phone"],
        address=data["address"],
        status=data["status"],
        notes=data["notes"],
    )
    audit.log(
        "إضافة طالب",
        entity="students",
        entity_id=student_id,
        details=f"{student_no} - {data['full_name']}",
        user=actor,
        ip=ip,
    )
    return student_id


def update_student(
    student_id: int,
    payload: dict[str, Any],
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    current = get_student(student_id)
    data = _clean_payload(payload)
    repo.update(
        student_id,
        data["full_name"],
        data["national_id"],
        data["gender"],
        data["birth_date"],
        data["guardian_name"],
        data["guardian_phone"],
        data["address"],
        data["status"],
        data["notes"],
    )
    if data["status"] != current["status"]:
        _sync_status_with_enrollments(student_id, data["status"], actor, ip)
    audit.log(
        "تعديل طالب",
        entity="students",
        entity_id=student_id,
        details=f"{current['student_no']} - {data['full_name']}",
        user=actor,
        ip=ip,
    )


def _sync_status_with_enrollments(
    student_id: int, status: str, actor: dict[str, Any] | None, ip: str | None
) -> None:
    """قاعدة أعمال: انسحاب/تخرج الطالب يقفل تسجيله الفعّال تلقائياً."""
    if status not in ("منسحب", "متخرج"):
        return
    enrollment = enroll_repo.active_for_student(student_id)
    if enrollment and enrollment["status"] == "مسجّل":
        enroll_repo.set_status(enrollment["id"], "منسحب")
        audit.log(
            "إغلاق تسجيل تلقائي",
            entity="enrollments",
            entity_id=enrollment["id"],
            details=f"حالة الطالب رقم {student_id} أصبحت «{status}»",
            user=actor,
            ip=ip,
        )


def set_status(
    student_id: int,
    status: str,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    student = get_student(student_id)
    status = v.require_choice(status, "الحالة", config.STUDENT_STATUSES)
    repo.set_status(student_id, status)
    _sync_status_with_enrollments(student_id, status, actor, ip)
    audit.log(
        "تغيير حالة طالب",
        entity="students",
        entity_id=student_id,
        details=f"{student['student_no']} → {status}",
        user=actor,
        ip=ip,
    )


def delete_student(
    student_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    student = get_student(student_id)
    repo.delete(student_id)
    audit.log(
        "حذف طالب",
        entity="students",
        entity_id=student_id,
        details=f"{student['student_no']} - {student['full_name']}",
        user=actor,
        ip=ip,
    )


def stats() -> dict[str, int]:
    return repo.stats()
