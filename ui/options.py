"""مُولّدات خيارات القوائم المنسدلة (لتقليل التكرار في الشاشات)."""
from __future__ import annotations

from typing import Any

from core.services import (
    classes_service,
    levels_service,
    students_service,
    subjects_service,
    teachers_service,
    terms_service,
    years_service,
)

ANY = {"label": "— الكل —", "value": ""}


def _option(label: str, value: Any) -> dict[str, str]:
    return {"label": label, "value": str(value)}


def years(any_label: str | None = None) -> list[dict[str, str]]:
    items = [ANY] if any_label else []
    items += [_option(f"{row['name']}{' (الحالية)' if row['is_current'] else ''}", row["id"])
              for row in years_service.list_years()]
    return items


def terms(year_id: int | None = None, any_label: str | None = None) -> list[dict[str, str]]:
    items = [ANY] if any_label else []
    items += [_option(f"{row['name']} — {row['year_name']}", row["id"])
              for row in terms_service.list_terms(year_id)]
    return items


def levels(any_label: str | None = None) -> list[dict[str, str]]:
    items = [ANY] if any_label else []
    items += [_option(row["name"], row["id"]) for row in levels_service.list_levels()]
    return items


def classes(
    year_id: int | None = None, any_label: str | None = None
) -> list[dict[str, str]]:
    items = [ANY] if any_label else []
    items += [
        _option(f"{row['name']} — {row['level_name']} ({row['enrolled']}/{row['capacity']})", row["id"])
        for row in classes_service.list_classes(year_id)
    ]
    return items


def subjects(any_label: str | None = None) -> list[dict[str, str]]:
    items = [ANY] if any_label else []
    items += [_option(f"{row['name']}{' (' + row['code'] + ')' if row['code'] else ''}", row["id"])
              for row in subjects_service.options()]
    return items


def teachers(any_label: str | None = None, active_only: bool = True) -> list[dict[str, str]]:
    items = [ANY] if any_label else []
    items += [_option(row["full_name"], row["id"]) for row in teachers_service.options(active_only)]
    return items


def students(any_label: str | None = None) -> list[dict[str, str]]:
    items = [ANY] if any_label else []
    items += [_option(f"{row['student_no']} — {row['full_name']}", row["id"])
              for row in students_service.list_students(limit=1000)]
    return items


def roles(any_label: str | None = None) -> list[dict[str, str]]:
    from core import config

    items = [ANY] if any_label else []
    items += [_option(config.role_label(role), role) for role in config.ROLES]
    return items


def choices(values: list[str] | tuple[str, ...], any_label: str | None = None) -> list[dict[str, str]]:
    items = [ANY] if any_label else []
    items += [_option(value, value) for value in values]
    return items
