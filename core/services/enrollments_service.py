"""خدمات التسجيل (طالب ↔ فصل) والإسناد التدريسي."""
from __future__ import annotations

from datetime import date
from typing import Any

from ..exceptions import BusinessRuleError, DuplicateError, NotFoundError
from ..repos import audit
from ..repos import enrollments as repo
from ..repos import students as students_repo
from ..services import classes_service, terms_service, years_service
from .. import validators as v


def list_enrollments(
    year_id: int | None = None, class_id: int | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    return repo.list_enrollments(year_id, class_id, status)


def get_enrollment(enrollment_id: int) -> dict[str, Any]:
    enrollment = repo.get(enrollment_id)
    if enrollment is None:
        raise NotFoundError("التسجيل غير موجود")
    return enrollment


def resolve_year(year_id: Any = None) -> dict[str, Any]:
    """تحديد السنة الدراسية: المُدخلة، أو الحالية، أو أحدث سنة معرّفة."""
    if str(year_id or "").strip():
        return years_service.get_year(v.parse_int(year_id, "السنة الدراسية", minimum=1))
    current = years_service.current_year()
    if current:
        return current
    years = years_service.list_years()
    if not years:
        raise BusinessRuleError("لا توجد سنة دراسية معرّفة، أضف سنة دراسية أولاً")
    return years[0]


def enroll(
    student_id: Any,
    class_id: Any,
    year_id: Any = None,
    term_id: Any = None,
    discount: Any = 0,
    enroll_date: Any = None,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    """تسجيل طالب في فصل مع كل قواعد التحقق (الحالة، السنة، السعة، التكرار، التاريخ)."""
    student_id = v.parse_int(student_id, "الطالب", minimum=1)
    class_id = v.parse_int(class_id, "الفصل", minimum=1)
    student = students_repo.get_raw(student_id)
    if student is None:
        raise NotFoundError("الطالب غير موجود")
    if student["status"] != "منتظم":
        raise BusinessRuleError(
            f"لا يمكن تسجيل طالب حالته «{student['status']}» — يجب أن تكون الحالة «منتظم»"
        )
    year = resolve_year(year_id)
    classes_service.validate_year_alignment(class_id, int(year["id"]))
    existing = repo.active_for_student(student_id, int(year["id"]))
    if existing and existing["status"] == "مسجّل":
        raise DuplicateError(
            f"الطالب مسجّل مسبقاً في هذه السنة (الفصل رقم {existing['class_id']})"
        )
    classes_service.ensure_capacity(class_id)
    term_value: int | None = None
    if str(term_id or "").strip():
        term = terms_service.get_term(v.parse_int(term_id, "الفصل الدراسي", minimum=1))
        if int(term["year_id"]) != int(year["id"]):
            raise BusinessRuleError("الفصل الدراسي المختار لا يتبع السنة الدراسية المحددة")
        term_value = int(term["id"])
    else:
        active_term = terms_service.current_term()
        if active_term and int(active_term["year_id"]) == int(year["id"]):
            term_value = int(active_term["id"])
    date_value = (
        v.parse_date(enroll_date, "تاريخ التسجيل", required=False) or date.today().isoformat()
    )
    discount_value = v.parse_money(discount, "الخصم")
    if existing:  # تسجيل سابق منسحب → يُعاد تنشيطه بدل إنشاء سجل جديد
        repo.change_class(int(existing["id"]), class_id, term_value)
        repo.set_discount(int(existing["id"]), discount_value)
        repo.set_status(int(existing["id"]), "مسجّل")
        audit.log(
            "إعادة تنشيط تسجيل",
            entity="enrollments",
            entity_id=existing["id"],
            details=f"الطالب {student['student_no']} → الفصل رقم {class_id}",
            user=actor,
            ip=ip,
        )
        return int(existing["id"])

    enrollment_id = repo.create(
        student_id=student_id,
        class_id=class_id,
        year_id=int(year["id"]),
        term_id=term_value,
        enroll_date=date_value,
        discount=discount_value,
    )
    audit.log(
        "تسجيل طالب",
        entity="enrollments",
        entity_id=enrollment_id,
        details=f"{student['student_no']} → الفصل رقم {class_id} ({year['name']})",
        user=actor,
        ip=ip,
    )
    return enrollment_id


def change_class(
    enrollment_id: Any,
    class_id: Any,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    enrollment = get_enrollment(v.parse_int(enrollment_id, "التسجيل", minimum=1))
    target_class_id = v.parse_int(class_id, "الفصل", minimum=1)
    if int(enrollment["class_id"]) == target_class_id:
        raise BusinessRuleError("الطالب مسجّل في هذا الفصل بالفعل")
    classes_service.validate_year_alignment(target_class_id, int(enrollment["year_id"]))
    classes_service.ensure_capacity(target_class_id)
    repo.change_class(int(enrollment["id"]), target_class_id)
    audit.log(
        "نقل طالب بين الفصول",
        entity="enrollments",
        entity_id=enrollment["id"],
        details=f"{enrollment['class_id']} → {target_class_id}",
        user=actor,
        ip=ip,
    )


def set_discount(
    enrollment_id: Any,
    discount: Any,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    enrollment = get_enrollment(v.parse_int(enrollment_id, "التسجيل", minimum=1))
    value = v.parse_money(discount, "الخصم")
    repo.set_discount(int(enrollment["id"]), value)
    audit.log(
        "تعديل خصم",
        entity="enrollments",
        entity_id=enrollment["id"],
        details=f"{enrollment['discount']} → {value}",
        user=actor,
        ip=ip,
    )


def withdraw(
    enrollment_id: Any, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    enrollment = get_enrollment(v.parse_int(enrollment_id, "التسجيل", minimum=1))
    if enrollment["status"] == "منسحب":
        raise BusinessRuleError("التسجيل منسحب مسبقاً")
    repo.set_status(int(enrollment["id"]), "منسحب")
    audit.log(
        "إلغاء تسجيل",
        entity="enrollments",
        entity_id=enrollment["id"],
        details=f"الطالب رقم {enrollment['student_id']}",
        user=actor,
        ip=ip,
    )


def delete_enrollment(
    enrollment_id: Any, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    enrollment = get_enrollment(v.parse_int(enrollment_id, "التسجيل", minimum=1))
    repo.delete(int(enrollment["id"]))
    audit.log(
        "حذف تسجيل",
        entity="enrollments",
        entity_id=enrollment["id"],
        details=f"الطالب رقم {enrollment['student_id']}",
        user=actor,
        ip=ip,
    )


def roster(class_id: Any) -> list[dict[str, Any]]:
    return classes_service.roster(v.parse_int(class_id, "الفصل", minimum=1))


def summary(year_id: int | None = None) -> list[dict[str, Any]]:
    """توزيع الطلاب على الفصول مع السعة المتاحة."""
    return classes_service.list_classes(year_id)


def student_history(student_id: Any) -> list[dict[str, Any]]:
    """سجل تسجيلات الطالب عبر السنوات."""
    target = v.parse_int(student_id, "الطالب", minimum=1)
    rows = [row for row in repo.list_enrollments() if int(row["student_id"]) == target]
    return sorted(rows, key=lambda row: (row["year_name"], row["class_name"]), reverse=True)
