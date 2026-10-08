"""خدمات الفصول الدراسية (فترات السنة)."""
from __future__ import annotations

from typing import Any

from ..exceptions import NotFoundError, ValidationError
from ..repos import academic as repo
from ..repos import audit
from ..repos import settings as settings_repo
from ..services import years_service
from .. import validators as v


def list_terms(year_id: int | None = None) -> list[dict[str, Any]]:
    return repo.list_terms(year_id)


def get_term(term_id: int) -> dict[str, Any]:
    term = repo.get_term(term_id)
    if term is None:
        raise NotFoundError("الفصل الدراسي غير موجود")
    return term


def current_term() -> dict[str, Any] | None:
    return repo.current_term()


def current_term_name() -> str:
    term = repo.current_term()
    return term["name"] if term else ""


def _validate_dates_within_year(
    year: dict[str, Any], start: str | None, end: str | None
) -> None:
    if start and end and start > end:
        raise ValidationError("تاريخ بداية الفصل يجب أن يسبق تاريخ نهايته")
    for bound, label in ((start, "البداية"), (end, "النهاية")):
        if not bound:
            continue
        if year.get("start_date") and bound < year["start_date"]:
            raise ValidationError(f"تاريخ {label} خارج نطاق السنة الدراسية")
        if year.get("end_date") and bound > year["end_date"]:
            raise ValidationError(f"تاريخ {label} خارج نطاق السنة الدراسية")


def create_term(
    year_id: int,
    name: str,
    start_date: str | None = None,
    end_date: str | None = None,
    make_current: bool = False,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    year = years_service.get_year(year_id)
    name = v.require_text(name, "اسم الفصل الدراسي", min_len=3, max_len=40)
    start = v.parse_date(start_date, "تاريخ البداية", required=False)
    end = v.parse_date(end_date, "تاريخ النهاية", required=False)
    _validate_dates_within_year(year, start, end)
    term_id = repo.create_term(year_id, name, start, end, 1 if make_current else 0)
    if make_current:
        _activate_term(term_id, year_id)
    audit.log(
        "إضافة فصل دراسي",
        entity="terms",
        entity_id=term_id,
        details=f"{year['name']} / {name}",
        user=actor,
        ip=ip,
    )
    return term_id


def update_term(
    term_id: int,
    name: str,
    start_date: str | None = None,
    end_date: str | None = None,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    term = get_term(term_id)
    year = years_service.get_year(int(term["year_id"]))
    name = v.require_text(name, "اسم الفصل الدراسي", min_len=3, max_len=40)
    start = v.parse_date(start_date, "تاريخ البداية", required=False)
    end = v.parse_date(end_date, "تاريخ النهاية", required=False)
    _validate_dates_within_year(year, start, end)
    repo.update_term(term_id, name, start, end)
    audit.log(
        "تعديل فصل دراسي", entity="terms", entity_id=term_id, details=name, user=actor, ip=ip
    )


def set_current_term(
    term_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    term = get_term(term_id)
    _activate_term(term_id, int(term["year_id"]))
    audit.log(
        "تعيين الفصل الحالي",
        entity="terms",
        entity_id=term_id,
        details=term["name"],
        user=actor,
        ip=ip,
    )


def _activate_term(term_id: int, year_id: int) -> None:
    """قاعدة أعمال: فصل حالي واحد لكل سنة، وتُزامن مع إعدادات النظام."""
    repo.set_current_term(term_id, year_id)
    settings_repo.set_value("current_term_id", term_id)


def delete_term(
    term_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    term = get_term(term_id)
    repo.delete_term(term_id)
    if settings_repo.current_term_id() == term_id:
        settings_repo.set_value("current_term_id", "")
    audit.log(
        "حذف فصل دراسي", entity="terms", entity_id=term_id, details=term["name"], user=actor, ip=ip
    )
