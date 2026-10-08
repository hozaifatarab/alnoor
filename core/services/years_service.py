"""خدمات السنوات الدراسية."""
from __future__ import annotations

from typing import Any

from ..exceptions import BusinessRuleError, NotFoundError, ValidationError
from ..repos import academic as repo
from ..repos import audit
from ..repos import settings as settings_repo
from .. import validators as v


def list_years() -> list[dict[str, Any]]:
    return repo.list_years()


def get_year(year_id: int) -> dict[str, Any]:
    year = repo.get_year(year_id)
    if year is None:
        raise NotFoundError("السنة الدراسية غير موجودة")
    return year


def current_year() -> dict[str, Any] | None:
    return repo.current_year()


def current_year_name() -> str:
    year = repo.current_year()
    return year["name"] if year else ""


def create_year(
    name: str,
    start_date: str | None = None,
    end_date: str | None = None,
    make_current: bool = False,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    name = v.require_text(name, "اسم السنة الدراسية", min_len=4, max_len=40)
    start = v.parse_date(start_date, "تاريخ البداية", required=False)
    end = v.parse_date(end_date, "تاريخ النهاية", required=False)
    if start and end and start > end:
        raise ValidationError("تاريخ بداية السنة يجب أن يسبق تاريخ نهايتها")
    year_id = repo.create_year(name, start, end, 1 if make_current else 0)
    if make_current:
        _activate_year(year_id)
    audit.log(
        "إضافة سنة دراسية",
        entity="academic_years",
        entity_id=year_id,
        details=name,
        user=actor,
        ip=ip,
    )
    return year_id


def update_year(
    year_id: int,
    name: str,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    get_year(year_id)
    name = v.require_text(name, "اسم السنة الدراسية", min_len=4, max_len=40)
    start = v.parse_date(start_date, "تاريخ البداية", required=False)
    end = v.parse_date(end_date, "تاريخ النهاية", required=False)
    if start and end and start > end:
        raise ValidationError("تاريخ بداية السنة يجب أن يسبق تاريخ نهايتها")
    repo.update_year(year_id, name, start, end)
    audit.log(
        "تعديل سنة دراسية",
        entity="academic_years",
        entity_id=year_id,
        details=name,
        user=actor,
        ip=ip,
    )


def set_current_year(
    year_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    year = get_year(year_id)
    _activate_year(year_id)
    audit.log(
        "تعيين السنة الحالية",
        entity="academic_years",
        entity_id=year_id,
        details=year["name"],
        user=actor,
        ip=ip,
    )


def _activate_year(year_id: int) -> None:
    """قاعدة أعمال: سنة حالية واحدة فقط، وتُزامن مع إعدادات النظام."""
    repo.set_current_year(year_id)
    settings_repo.set_value("current_year_id", year_id)
    current_term = repo.current_term()
    if current_term and int(current_term["year_id"]) != int(year_id):
        settings_repo.set_value("current_term_id", "")


def delete_year(
    year_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    year = get_year(year_id)
    if repo.year_has_data(year_id):
        raise BusinessRuleError("لا يمكن حذف سنة دراسية مرتبطة بفصول أو تسجيلات")
    repo.delete_year(year_id)
    if settings_repo.current_year_id() == year_id:
        settings_repo.set_value("current_year_id", "")
    audit.log(
        "حذف سنة دراسية",
        entity="academic_years",
        entity_id=year_id,
        details=year["name"],
        user=actor,
        ip=ip,
    )
