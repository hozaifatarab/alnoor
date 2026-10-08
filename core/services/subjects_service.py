"""خدمات المواد الدراسية."""
from __future__ import annotations

from typing import Any

from ..exceptions import NotFoundError
from ..repos import audit
from ..repos import subjects as repo
from .. import validators as v


def list_subjects(level_id: int | None = None, search: str | None = None) -> list[dict[str, Any]]:
    return repo.list_subjects(level_id, search)


def get_subject(subject_id: int) -> dict[str, Any]:
    subject = repo.get(subject_id)
    if subject is None:
        raise NotFoundError("المادة غير موجودة")
    return subject


def options() -> list[dict[str, Any]]:
    return repo.options()


def create_subject(
    name: str,
    code: str | None = None,
    level_id: Any = None,
    weekly_hours: Any = 0,
    max_score: Any = 100,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    data = _clean(name, code, level_id, weekly_hours, max_score)
    subject_id = repo.create(
        data["name"], data["code"], data["level_id"], data["weekly_hours"], data["max_score"]
    )
    audit.log(
        "إضافة مادة", entity="subjects", entity_id=subject_id, details=data["name"], user=actor, ip=ip
    )
    return subject_id


def update_subject(
    subject_id: int,
    name: str,
    code: str | None = None,
    level_id: Any = None,
    weekly_hours: Any = 0,
    max_score: Any = 100,
    is_active: bool = True,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    get_subject(subject_id)
    data = _clean(name, code, level_id, weekly_hours, max_score)
    repo.update(
        subject_id,
        data["name"],
        data["code"],
        data["level_id"],
        data["weekly_hours"],
        data["max_score"],
        1 if is_active else 0,
    )
    audit.log(
        "تعديل مادة", entity="subjects", entity_id=subject_id, details=data["name"], user=actor, ip=ip
    )


def delete_subject(
    subject_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    subject = get_subject(subject_id)
    if repo.assignments_count(subject_id) > 0:
        from ..exceptions import BusinessRuleError

        raise BusinessRuleError("لا يمكن حذف المادة لارتباطها بإسناد تدريسي")
    repo.delete(subject_id)
    audit.log(
        "حذف مادة", entity="subjects", entity_id=subject_id, details=subject["name"], user=actor, ip=ip
    )


def _clean(
    name: str, code: str | None, level_id: Any, weekly_hours: Any, max_score: Any
) -> dict[str, Any]:
    level_value: int | None = None
    if str(level_id or "").strip():
        level_value = v.parse_int(level_id, "المرحلة", minimum=1)
    return {
        "name": v.require_text(name, "اسم المادة", min_len=2, max_len=60),
        "code": v.optional_text(code, 20),
        "level_id": level_value,
        "weekly_hours": v.parse_float(weekly_hours, "الساعات الأسبوعية", minimum=0, maximum=40),
        "max_score": v.parse_float(max_score, "الدرجة العظمى", minimum=1, maximum=1000, default=100),
    }
