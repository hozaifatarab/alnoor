"""مستودع المواد الدراسية."""
from __future__ import annotations

from typing import Any

from .. import db


def list_subjects(level_id: int | None = None, search: str | None = None) -> list[dict[str, Any]]:
    sql = [
        "SELECT s.*, l.name AS level_name,"
        " (SELECT COUNT(*) FROM teaching_assignments ta WHERE ta.subject_id = s.id) AS assignments_count"
        " FROM subjects s LEFT JOIN levels l ON l.id = s.level_id WHERE 1 = 1"
    ]
    params: list[Any] = []
    if level_id:
        sql.append("AND s.level_id = ?")
        params.append(level_id)
    if search:
        sql.append("AND (s.name LIKE ? OR s.code LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    sql.append("ORDER BY l.sort_order, s.name")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def get(subject_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM subjects WHERE id = ?", (subject_id,))
    return dict(row) if row else None


def create(
    name: str, code: str | None, level_id: int | None, weekly_hours: float, max_score: float
) -> int:
    return db.execute(
        "INSERT INTO subjects(name, code, level_id, weekly_hours, max_score) VALUES (?, ?, ?, ?, ?)",
        (name, code, level_id, weekly_hours, max_score),
    )


def update(
    subject_id: int,
    name: str,
    code: str | None,
    level_id: int | None,
    weekly_hours: float,
    max_score: float,
    is_active: int,
) -> None:
    db.execute(
        "UPDATE subjects SET name = ?, code = ?, level_id = ?, weekly_hours = ?, max_score = ?,"
        " is_active = ? WHERE id = ?",
        (name, code, level_id, weekly_hours, max_score, is_active, subject_id),
    )


def delete(subject_id: int) -> None:
    db.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))


def assignments_count(subject_id: int) -> int:
    """عدد الإسنادات التدريسية المرتبطة بالمادة (لحماية الحذف)."""
    return int(
        db.scalar(
            "SELECT COUNT(*) FROM teaching_assignments WHERE subject_id = ?", (subject_id,), 0
        )
        or 0
    )


def options() -> list[dict[str, Any]]:
    """قائمة مبسّطة للمواد الفعّالة (للقوائم المنسدلة)."""
    rows = db.query_all(
        "SELECT id, name, code FROM subjects WHERE is_active = 1 ORDER BY name"
    )
    return [dict(row) for row in rows]
