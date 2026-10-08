"""خدمات الفصول (الصفوف): الإنشاء والتعديل مع قاعدة السعة."""
from __future__ import annotations

from typing import Any

from ..exceptions import BusinessRuleError, NotFoundError, ValidationError
from ..repos import audit
from ..repos import classes as repo
from .. import validators as v

MAX_CAPACITY = 200


def list_classes(
    year_id: int | None = None, level_id: int | None = None, search: str | None = None
) -> list[dict[str, Any]]:
    return repo.list_classes(year_id, level_id, search)


def get_class(class_id: int) -> dict[str, Any]:
    klass = repo.get(class_id)
    if klass is None:
        raise NotFoundError("الفصل غير موجود")
    return klass


def capacity_info(class_id: int) -> dict[str, int]:
    return repo.capacity_info(class_id)


def roster(class_id: int) -> list[dict[str, Any]]:
    get_class(class_id)
    return repo.students_in_class(class_id)


def for_teacher(teacher_id: int, year_id: int | None = None) -> list[dict[str, Any]]:
    return repo.list_for_teacher(teacher_id, year_id)


def _clean(
    name: str,
    level_id: Any,
    year_id: Any,
    capacity: Any,
    room: Any,
    homeroom_teacher_id: Any,
) -> dict[str, Any]:
    return {
        "name": v.require_text(name, "اسم الفصل", min_len=1, max_len=40),
        "level_id": v.parse_int(level_id, "المرحلة", minimum=1),
        "year_id": v.parse_int(year_id, "السنة الدراسية", minimum=1),
        "capacity": v.parse_int(capacity, "السعة", minimum=1, maximum=MAX_CAPACITY, default=30),
        "room": v.optional_text(room, 20),
        "homeroom_teacher_id": (
            v.parse_int(homeroom_teacher_id, "مشرف الفصل", minimum=1)
            if str(homeroom_teacher_id or "").strip()
            else None
        ),
    }


def create_class(
    name: str,
    level_id: Any,
    year_id: Any,
    capacity: Any = 30,
    room: Any = None,
    homeroom_teacher_id: Any = None,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    data = _clean(name, level_id, year_id, capacity, room, homeroom_teacher_id)
    class_id = repo.create(
        data["name"],
        data["level_id"],
        data["year_id"],
        data["capacity"],
        data["room"],
        data["homeroom_teacher_id"],
    )
    audit.log(
        "إضافة فصل",
        entity="classes",
        entity_id=class_id,
        details=f"{data['name']} (سعة {data['capacity']})",
        user=actor,
        ip=ip,
    )
    return class_id


def update_class(
    class_id: int,
    name: str,
    level_id: Any,
    year_id: Any,
    capacity: Any,
    room: Any = None,
    homeroom_teacher_id: Any = None,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    current = get_class(class_id)
    data = _clean(name, level_id, year_id, capacity, room, homeroom_teacher_id)
    enrolled = repo.capacity_info(class_id)["enrolled"]
    if data["capacity"] < enrolled:
        raise BusinessRuleError(
            f"السعة الجديدة ({data['capacity']}) أقل من عدد الطلاب المسجّلين ({enrolled})"
        )
    repo.update(
        class_id,
        data["name"],
        data["level_id"],
        data["year_id"],
        data["capacity"],
        data["room"],
        data["homeroom_teacher_id"],
    )
    audit.log(
        "تعديل فصل",
        entity="classes",
        entity_id=class_id,
        details=f"{current['name']} → {data['name']} (سعة {data['capacity']})",
        user=actor,
        ip=ip,
    )


def delete_class(
    class_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    klass = get_class(class_id)
    info = repo.capacity_info(class_id)
    if info["enrolled"] > 0:
        raise BusinessRuleError(
            f"لا يمكن حذف الفصل لوجود {info['enrolled']} طالباً مسجّلاً فيه"
        )
    repo.delete(class_id)
    audit.log("حذف فصل", entity="classes", entity_id=class_id, details=klass["name"], user=actor, ip=ip)


def ensure_capacity(class_id: int, extra: int = 1) -> None:
    """تحقق من توفّر مقاعد قبل التسجيل (تُستدعى من خدمة التسجيل)."""
    info = repo.capacity_info(class_id)
    if info["enrolled"] + extra > info["capacity"]:
        klass = get_class(class_id)
        raise BusinessRuleError(
            f"سعة الفصل «{klass['name']}» ممتلئة ({info['enrolled']}/{info['capacity']})"
        )


def validate_year_alignment(class_id: int, year_id: int) -> None:
    klass = get_class(class_id)
    if int(klass["year_id"]) != int(year_id):
        raise ValidationError("الفصل المختار لا يتبع السنة الدراسية المحددة")
