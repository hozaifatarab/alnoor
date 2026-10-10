"""خدمات المعلمين + الإسناد التدريسي."""
from __future__ import annotations

from typing import Any

from ..exceptions import BusinessRuleError, DuplicateError, NotFoundError
from ..repos import audit
from ..repos import enrollments as assign_repo
from ..repos import teachers as repo
from . import classes_service, subjects_service
from .. import validators as v


def list_teachers(search: str | None = None, active_only: bool = False) -> list[dict[str, Any]]:
    return repo.list_teachers(search, active_only)


def get_teacher(teacher_id: int) -> dict[str, Any]:
    teacher = repo.get(teacher_id)
    if teacher is None:
        raise NotFoundError("المعلم غير موجود")
    return teacher


def get_by_user_id(user_id: int) -> dict[str, Any] | None:
    return repo.get_by_user_id(user_id)


def options(active_only: bool = True) -> list[dict[str, Any]]:
    return repo.options(active_only)


def _clean(
    full_name: Any,
    national_id: Any,
    phone: Any,
    email: Any,
    hire_date: Any,
    specialty: Any,
    salary: Any,
) -> dict[str, Any]:
    return {
        "full_name": v.require_text(full_name, "الاسم", min_len=3, max_len=80),
        "national_id": v.validate_national_id(national_id),
        "phone": v.validate_phone(phone),
        "email": v.validate_email(email),
        "hire_date": v.parse_date(hire_date, "تاريخ التعيين", required=False),
        "specialty": v.optional_text(specialty, 60),
        "salary": v.parse_money(salary, "الراتب"),
    }


def create_teacher(
    full_name: Any,
    national_id: Any = None,
    phone: Any = None,
    email: Any = None,
    hire_date: Any = None,
    specialty: Any = None,
    salary: Any = 0,
    *,
    user_id: int | None = None,
    conn: Any = None,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    data = _clean(full_name, national_id, phone, email, hire_date, specialty, salary)
    teacher_id = repo.create(
        data["full_name"],
        data["national_id"],
        data["phone"],
        data["email"],
        data["hire_date"],
        data["specialty"],
        data["salary"],
        user_id,
        conn,
    )
    audit.log(
        "إضافة معلم",
        entity="teachers",
        entity_id=teacher_id,
        details=data["full_name"],
        user=actor,
        ip=ip,
        conn=conn,
    )
    return teacher_id


def update_teacher(
    teacher_id: int,
    full_name: Any,
    national_id: Any = None,
    phone: Any = None,
    email: Any = None,
    hire_date: Any = None,
    specialty: Any = None,
    salary: Any = 0,
    is_active: bool = True,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    current = get_teacher(teacher_id)
    data = _clean(full_name, national_id, phone, email, hire_date, specialty, salary)
    repo.update(
        teacher_id,
        data["full_name"],
        data["national_id"],
        data["phone"],
        data["email"],
        data["hire_date"],
        data["specialty"],
        data["salary"],
        1 if is_active else 0,
    )
    audit.log(
        "تعديل معلم",
        entity="teachers",
        entity_id=teacher_id,
        details=f"{current['full_name']} → {data['full_name']}",
        user=actor,
        ip=ip,
    )


def link_account(
    teacher_id: int,
    user_id: int | None,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    teacher = get_teacher(teacher_id)
    if user_id is not None:
        existing = repo.get_by_user_id(user_id)
        if existing and int(existing["id"]) != int(teacher_id):
            raise DuplicateError("حساب الدخول مرتبط بمعلم آخر")
    repo.set_user_link(teacher_id, user_id)
    audit.log(
        "ربط حساب دخول بمعلم",
        entity="teachers",
        entity_id=teacher_id,
        details=f"{teacher['full_name']} ↔ user={user_id}",
        user=actor,
        ip=ip,
    )


def delete_teacher(
    teacher_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    teacher = get_teacher(teacher_id)
    if int(teacher.get("assignments_count") or 0) > 0:
        raise BusinessRuleError("لا يمكن حذف معلم لديه إسناد تدريسي، احذف الإسناد أولاً")
    repo.delete(teacher_id)
    audit.log(
        "حذف معلم",
        entity="teachers",
        entity_id=teacher_id,
        details=teacher["full_name"],
        user=actor,
        ip=ip,
    )


def stats() -> dict[str, int]:
    total = len(repo.list_teachers())
    active = repo.count_active()
    return {"total": total, "active": active, "inactive": total - active}


# ---------------- الإسناد التدريسي ----------------

def list_assignments(
    term_id: int | None = None,
    class_id: int | None = None,
    teacher_id: int | None = None,
    year_id: int | None = None,
) -> list[dict[str, Any]]:
    return assign_repo.list_assignments(term_id, class_id, teacher_id, year_id)


def create_assignment(
    teacher_id: Any,
    subject_id: Any,
    class_id: Any,
    term_id: Any = None,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    teacher_id = v.parse_int(teacher_id, "المعلم", minimum=1)
    subject_id = v.parse_int(subject_id, "المادة", minimum=1)
    class_id = v.parse_int(class_id, "الفصل", minimum=1)
    term_value = (
        v.parse_int(term_id, "الفصل الدراسي", minimum=1) if str(term_id or "").strip() else None
    )
    get_teacher(teacher_id)
    subjects_service.get_subject(subject_id)
    classes_service.get_class(class_id)
    if assign_repo.assignment_exists(teacher_id, subject_id, class_id):
        raise DuplicateError("هذا الإسناد مسجّل مسبقاً (المعلم + المادة + الفصل)")
    assignment_id = assign_repo.create_assignment(teacher_id, subject_id, class_id, term_value)
    audit.log(
        "إسناد تدريسي",
        entity="teaching_assignments",
        entity_id=assignment_id,
        details=f"معلم {teacher_id} / مادة {subject_id} / فصل {class_id}",
        user=actor,
        ip=ip,
    )
    return assignment_id


def delete_assignment(
    assignment_id: Any, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    assignment = assign_repo.get_assignment(v.parse_int(assignment_id, "الإسناد", minimum=1))
    if assignment is None:
        raise NotFoundError("الإسناد غير موجود")
    assign_repo.delete_assignment(int(assignment["id"]))
    audit.log(
        "حذف إسناد",
        entity="teaching_assignments",
        entity_id=assignment["id"],
        details=f"معلم {assignment['teacher_id']} / مادة {assignment['subject_id']}",
        user=actor,
        ip=ip,
    )
