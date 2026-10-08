"""مستودع الطلاب."""
from __future__ import annotations

from typing import Any

from .. import db

_STUDENT_SELECT = """
SELECT s.*,
       e.id AS enrollment_id, e.class_id, e.status AS enrollment_status, e.discount,
       c.name AS class_name, l.name AS level_name, y.name AS year_name
  FROM students s
  LEFT JOIN enrollments e ON e.student_id = s.id AND e.status = 'مسجّل'
  LEFT JOIN classes c ON c.id = e.class_id
  LEFT JOIN levels l ON l.id = c.level_id
  LEFT JOIN academic_years y ON y.id = e.year_id
"""


def list_students(
    search: str | None = None,
    status: str | None = None,
    class_id: int | None = None,
    year_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    sql = [_STUDENT_SELECT, "WHERE 1 = 1"]
    params: list[Any] = []
    if search:
        sql.append("AND (s.full_name LIKE ? OR s.student_no LIKE ? OR s.national_id LIKE ?)")
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if status:
        sql.append("AND s.status = ?")
        params.append(status)
    if class_id:
        sql.append("AND e.class_id = ?")
        params.append(class_id)
    if year_id:
        sql.append("AND e.year_id = ?")
        params.append(year_id)
    sql.append("ORDER BY s.full_name LIMIT ? OFFSET ?")
    params += [limit, offset]
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def count_students(
    search: str | None = None,
    status: str | None = None,
    class_id: int | None = None,
    year_id: int | None = None,
) -> int:
    sql = ["SELECT COUNT(DISTINCT s.id) FROM students s"]
    params: list[Any] = []
    if class_id or year_id:
        sql.append("JOIN enrollments e ON e.student_id = s.id AND e.status = 'مسجّل'")
    sql.append("WHERE 1 = 1")
    if search:
        sql.append("AND (s.full_name LIKE ? OR s.student_no LIKE ? OR s.national_id LIKE ?)")
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if status:
        sql.append("AND s.status = ?")
        params.append(status)
    if class_id:
        sql.append("AND e.class_id = ?")
        params.append(class_id)
    if year_id:
        sql.append("AND e.year_id = ?")
        params.append(year_id)
    return int(db.scalar(" ".join(sql), params, 0) or 0)


def get(student_id: int) -> dict[str, Any] | None:
    row = db.query_one(_STUDENT_SELECT + " WHERE s.id = ?", (student_id,))
    if row:
        return dict(row)
    row = db.query_one("SELECT * FROM students WHERE id = ?", (student_id,))
    return dict(row) if row else None


def get_raw(student_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM students WHERE id = ?", (student_id,))
    return dict(row) if row else None


def get_by_no(student_no: str) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM students WHERE student_no = ?", (student_no,))
    return dict(row) if row else None


get_by_student_no = get_by_no



def next_student_no(year_name: str) -> str:
    """توليد رقم طالب متسلسل بالصيغة ``2026-0001``."""
    prefix = (year_name or "").split("/")[0].strip() or "0000"
    last = db.scalar(
        "SELECT student_no FROM students WHERE student_no LIKE ? ORDER BY student_no DESC LIMIT 1",
        (f"{prefix}-%",),
    )
    sequence = 1
    if last:
        tail = str(last).split("-")[-1]
        if tail.isdigit():
            sequence = int(tail) + 1
    return f"{prefix}-{sequence:04d}"


def create(
    student_no: str,
    full_name: str,
    national_id: str | None,
    gender: str | None,
    birth_date: str | None,
    guardian_name: str | None,
    guardian_phone: str | None,
    address: str | None,
    status: str,
    notes: str | None = None,
) -> int:
    return db.execute(
        "INSERT INTO students(student_no, full_name, national_id, gender, birth_date,"
        " guardian_name, guardian_phone, address, status, notes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            student_no,
            full_name,
            national_id,
            gender,
            birth_date,
            guardian_name,
            guardian_phone,
            address,
            status,
            notes,
        ),
    )


def update(
    student_id: int,
    full_name: str,
    national_id: str | None,
    gender: str | None,
    birth_date: str | None,
    guardian_name: str | None,
    guardian_phone: str | None,
    address: str | None,
    status: str,
    notes: str | None,
) -> None:
    db.execute(
        "UPDATE students SET full_name = ?, national_id = ?, gender = ?, birth_date = ?,"
        " guardian_name = ?, guardian_phone = ?, address = ?, status = ?, notes = ? WHERE id = ?",
        (
            full_name,
            national_id,
            gender,
            birth_date,
            guardian_name,
            guardian_phone,
            address,
            status,
            notes,
            student_id,
        ),
    )


def set_status(student_id: int, status: str) -> None:
    db.execute("UPDATE students SET status = ? WHERE id = ?", (status, student_id))


def delete(student_id: int) -> None:
    db.execute("DELETE FROM students WHERE id = ?", (student_id,))


def stats() -> dict[str, int]:
    total = int(db.scalar("SELECT COUNT(*) FROM students", (), 0) or 0)
    by_status = {
        row["status"]: int(row["total"])
        for row in db.query_all("SELECT status, COUNT(*) AS total FROM students GROUP BY status")
    }
    return {"total": total, **by_status}


def options(status: str | None = "منتظم") -> list[dict[str, Any]]:
    sql = "SELECT id, student_no, full_name FROM students"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY full_name"
    return [dict(row) for row in db.query_all(sql, params)]
