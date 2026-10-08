"""خدمات المراحل الدراسية."""
from __future__ import annotations

from typing import Any

from ..exceptions import BusinessRuleError, NotFoundError
from ..repos import academic as repo
from ..repos import audit
from .. import validators as v


def list_levels() -> list[dict[str, Any]]:
    return repo.list_levels()


def get_level(level_id: int) -> dict[str, Any]:
    level = repo.get_level(level_id)
    if level is None:
        raise NotFoundError("المرحلة غير موجودة")
    return level


def create_level(
    name: str,
    sort_order: Any = None,
    notes: str | None = None,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    name = v.require_text(name, "اسم المرحلة", min_len=2, max_len=40)
    order = v.parse_int(sort_order, "الترتيب", minimum=0, default=repo.next_level_order())
    level_id = repo.create_level(name, order, v.optional_text(notes, 200))
    audit.log("إضافة مرحلة", entity="levels", entity_id=level_id, details=name, user=actor, ip=ip)
    return level_id


def update_level(
    level_id: int,
    name: str,
    sort_order: Any = 10,
    notes: str | None = None,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    get_level(level_id)
    name = v.require_text(name, "اسم المرحلة", min_len=2, max_len=40)
    order = v.parse_int(sort_order, "الترتيب", minimum=0, default=10)
    repo.update_level(level_id, name, order, v.optional_text(notes, 200))
    audit.log("تعديل مرحلة", entity="levels", entity_id=level_id, details=name, user=actor, ip=ip)


def delete_level(
    level_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    level = get_level(level_id)
    if int(level.get("classes_count") or 0) > 0:
        raise BusinessRuleError("لا يمكن حذف مرحلة تحتوي على فصول")
    repo.delete_level(level_id)
    audit.log(
        "حذف مرحلة", entity="levels", entity_id=level_id, details=level["name"], user=actor, ip=ip
    )
