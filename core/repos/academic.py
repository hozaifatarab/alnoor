"""مستودع البنية الأكاديمية: السنوات الدراسية، الفصول (الفترات)، المراحل."""
from __future__ import annotations

from typing import Any

from .. import db

# ---------------- السنوات الدراسية ----------------

def list_years() -> list[dict[str, Any]]:
    rows = db.query_all("SELECT * FROM academic_years ORDER BY is_current DESC, name DESC")
    return [dict(row) for row in rows]


def get_year(year_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM academic_years WHERE id = ?", (year_id,))
    return dict(row) if row else None


def create_year(name: str, start_date: str | None, end_date: str | None, is_current: int = 0) -> int:
    return db.execute(
        "INSERT INTO academic_years(name, start_date, end_date, is_current) VALUES (?, ?, ?, ?)",
        (name, start_date, end_date, 1 if is_current else 0),
    )


def update_year(year_id: int, name: str, start_date: str | None, end_date: str | None) -> None:
    db.execute(
        "UPDATE academic_years SET name = ?, start_date = ?, end_date = ? WHERE id = ?",
        (name, start_date, end_date, year_id),
    )


def set_current_year(year_id: int) -> None:
    db.execute("UPDATE academic_years SET is_current = 0")
    db.execute("UPDATE academic_years SET is_current = 1 WHERE id = ?", (year_id,))


def current_year() -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM academic_years WHERE is_current = 1 LIMIT 1")
    return dict(row) if row else None


def delete_year(year_id: int) -> None:
    db.execute("DELETE FROM academic_years WHERE id = ?", (year_id,))


def year_has_data(year_id: int) -> bool:
    return bool(
        db.scalar("SELECT COUNT(*) FROM enrollments WHERE year_id = ?", (year_id,), 0)
        or db.scalar("SELECT COUNT(*) FROM classes WHERE year_id = ?", (year_id,), 0)
    )


# ---------------- الفصول الدراسية (فترات السنة) ----------------

def list_terms(year_id: int | None = None) -> list[dict[str, Any]]:
    if year_id:
        rows = db.query_all(
            "SELECT t.*, y.name AS year_name FROM terms t"
            " JOIN academic_years y ON y.id = t.year_id"
            " WHERE t.year_id = ? ORDER BY t.is_current DESC, t.start_date",
            (year_id,),
        )
    else:
        rows = db.query_all(
            "SELECT t.*, y.name AS year_name FROM terms t"
            " JOIN academic_years y ON y.id = t.year_id"
            " ORDER BY y.name DESC, t.start_date"
        )
    return [dict(row) for row in rows]


def get_term(term_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM terms WHERE id = ?", (term_id,))
    return dict(row) if row else None


def create_term(
    year_id: int, name: str, start_date: str | None, end_date: str | None, is_current: int = 0
) -> int:
    return db.execute(
        "INSERT INTO terms(year_id, name, start_date, end_date, is_current) VALUES (?, ?, ?, ?, ?)",
        (year_id, name, start_date, end_date, 1 if is_current else 0),
    )


def update_term(term_id: int, name: str, start_date: str | None, end_date: str | None) -> None:
    db.execute(
        "UPDATE terms SET name = ?, start_date = ?, end_date = ? WHERE id = ?",
        (name, start_date, end_date, term_id),
    )


def set_current_term(term_id: int, year_id: int) -> None:
    db.execute("UPDATE terms SET is_current = 0 WHERE year_id = ?", (year_id,))
    db.execute("UPDATE terms SET is_current = 1 WHERE id = ?", (term_id,))


def current_term(year_id: int | None = None) -> dict[str, Any] | None:
    if year_id:
        row = db.query_one("SELECT * FROM terms WHERE year_id = ? AND is_current = 1 LIMIT 1", (year_id,))
        if row:
            return dict(row)
        # إذا لم يوجد محدد كحالي، نأخذ أول فصل في السنة
        row = db.query_one("SELECT * FROM terms WHERE year_id = ? ORDER BY id ASC LIMIT 1", (year_id,))
        return dict(row) if row else None
    row = db.query_one("SELECT * FROM terms WHERE is_current = 1 LIMIT 1")
    return dict(row) if row else None


get_current_term = current_term



def delete_term(term_id: int) -> None:
    db.execute("DELETE FROM terms WHERE id = ?", (term_id,))


# ---------------- المراحل ----------------

def list_levels() -> list[dict[str, Any]]:
    rows = db.query_all(
        "SELECT l.*, (SELECT COUNT(*) FROM classes c WHERE c.level_id = l.id) AS classes_count,"
        " (SELECT COUNT(*) FROM subjects s WHERE s.level_id = l.id) AS subjects_count"
        " FROM levels l ORDER BY l.sort_order, l.name"
    )
    return [dict(row) for row in rows]


def get_level(level_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM levels WHERE id = ?", (level_id,))
    return dict(row) if row else None


def next_level_order() -> int:
    return int(db.scalar("SELECT COALESCE(MAX(sort_order), 0) + 10 FROM levels", (), 10) or 10)


def create_level(name: str, sort_order: int, notes: str | None = None) -> int:
    return db.execute(
        "INSERT INTO levels(name, sort_order, notes) VALUES (?, ?, ?)", (name, sort_order, notes)
    )


def update_level(level_id: int, name: str, sort_order: int, notes: str | None) -> None:
    db.execute(
        "UPDATE levels SET name = ?, sort_order = ?, notes = ? WHERE id = ?",
        (name, sort_order, notes, level_id),
    )


def delete_level(level_id: int) -> None:
    db.execute("DELETE FROM levels WHERE id = ?", (level_id,))
