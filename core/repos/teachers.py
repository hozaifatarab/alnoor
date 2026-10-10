"""مستودع المعلمين."""
from __future__ import annotations

from typing import Any

from .. import db

_TEACHER_SELECT = """
SELECT t.*, u.username AS account_username,
       (SELECT COUNT(*) FROM teaching_assignments ta WHERE ta.teacher_id = t.id) AS assignments_count,
       (SELECT COUNT(*) FROM classes c WHERE c.homeroom_teacher_id = t.id) AS homeroom_count
  FROM teachers t
  LEFT JOIN users u ON u.id = t.user_id
"""


def list_teachers(
    search: str | None = None, active_only: bool = False, specialty: str | None = None
) -> list[dict[str, Any]]:
    sql = [_TEACHER_SELECT, "WHERE 1 = 1"]
    params: list[Any] = []
    if search:
        sql.append("AND (t.full_name LIKE ? OR t.national_id LIKE ? OR t.phone LIKE ?)")
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if active_only:
        sql.append("AND t.is_active = 1")
    if specialty:
        sql.append("AND t.specialty = ?")
        params.append(specialty)
    sql.append("ORDER BY t.is_active DESC, t.full_name")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def get(teacher_id: int) -> dict[str, Any] | None:
    row = db.query_one(_TEACHER_SELECT + " WHERE t.id = ?", (teacher_id,))
    return dict(row) if row else None


def get_by_user_id(user_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM teachers WHERE user_id = ?", (user_id,))
    return dict(row) if row else None


def create(
    full_name: str,
    national_id: str | None,
    phone: str | None,
    email: str | None,
    hire_date: str | None,
    specialty: str | None,
    salary: float,
    user_id: int | None = None,
    conn: Any = None,
) -> int:
    sql = (
        "INSERT INTO teachers(full_name, national_id, phone, email, hire_date, specialty, salary, user_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    params = (full_name, national_id, phone, email, hire_date, specialty, salary, user_id)
    if conn is not None:
        return int(conn.execute(sql, params).lastrowid or 0)
    return db.execute(sql, params)


def update(
    teacher_id: int,
    full_name: str,
    national_id: str | None,
    phone: str | None,
    email: str | None,
    hire_date: str | None,
    specialty: str | None,
    salary: float,
    is_active: int,
) -> None:
    db.execute(
        "UPDATE teachers SET full_name = ?, national_id = ?, phone = ?, email = ?, hire_date = ?,"
        " specialty = ?, salary = ?, is_active = ? WHERE id = ?",
        (full_name, national_id, phone, email, hire_date, specialty, salary, is_active, teacher_id),
    )


def set_user_link(teacher_id: int, user_id: int | None) -> None:
    db.execute("UPDATE teachers SET user_id = ? WHERE id = ?", (user_id, teacher_id))


def delete(teacher_id: int) -> None:
    db.execute("DELETE FROM teachers WHERE id = ?", (teacher_id,))


def options(active_only: bool = True) -> list[dict[str, Any]]:
    sql = "SELECT id, full_name FROM teachers"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY full_name"
    return [dict(row) for row in db.query_all(sql)]


def count_active() -> int:
    return int(db.scalar("SELECT COUNT(*) FROM teachers WHERE is_active = 1", (), 0) or 0)
