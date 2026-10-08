"""مستودع الفصول (الصفوف) وطلاب كل فصل."""
from __future__ import annotations

from typing import Any

from .. import db

_CLASS_SELECT = """
SELECT c.*, l.name AS level_name, y.name AS year_name,
       t.full_name AS homeroom_teacher_name,
       (SELECT COUNT(*) FROM enrollments e
         WHERE e.class_id = c.id AND e.status = 'مسجّل') AS enrolled
  FROM classes c
  JOIN levels l ON l.id = c.level_id
  JOIN academic_years y ON y.id = c.year_id
  LEFT JOIN teachers t ON t.id = c.homeroom_teacher_id
"""


def list_classes(
    year_id: int | None = None, level_id: int | None = None, search: str | None = None
) -> list[dict[str, Any]]:
    sql = [_CLASS_SELECT, "WHERE 1 = 1"]
    params: list[Any] = []
    if year_id:
        sql.append("AND c.year_id = ?")
        params.append(year_id)
    if level_id:
        sql.append("AND c.level_id = ?")
        params.append(level_id)
    if search:
        sql.append("AND c.name LIKE ?")
        params.append(f"%{search}%")
    sql.append("ORDER BY y.name DESC, l.sort_order, c.name")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def get(class_id: int) -> dict[str, Any] | None:
    row = db.query_one(_CLASS_SELECT + " WHERE c.id = ?", (class_id,))
    return dict(row) if row else None


def get_by_name_and_year(name: str, year_id: int) -> dict[str, Any] | None:
    row = db.query_one(_CLASS_SELECT + " WHERE c.name = ? AND c.year_id = ?", (name, year_id))
    return dict(row) if row else None



def create(
    name: str,
    level_id: int,
    year_id: int,
    capacity: int,
    room: str | None = None,
    homeroom_teacher_id: int | None = None,
) -> int:
    return db.execute(
        "INSERT INTO classes(name, level_id, year_id, capacity, room, homeroom_teacher_id)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (name, level_id, year_id, capacity, room, homeroom_teacher_id),
    )


def update(
    class_id: int,
    name: str,
    level_id: int,
    year_id: int,
    capacity: int,
    room: str | None,
    homeroom_teacher_id: int | None,
) -> None:
    db.execute(
        "UPDATE classes SET name = ?, level_id = ?, year_id = ?, capacity = ?, room = ?,"
        " homeroom_teacher_id = ? WHERE id = ?",
        (name, level_id, year_id, capacity, room, homeroom_teacher_id, class_id),
    )


def delete(class_id: int) -> None:
    db.execute("DELETE FROM classes WHERE id = ?", (class_id,))


def capacity_info(class_id: int) -> dict[str, int]:
    """معلومات السعة: الإجمالي، المسجّلون، المتاح."""
    row = db.query_one(
        "SELECT c.capacity,"
        " (SELECT COUNT(*) FROM enrollments e WHERE e.class_id = c.id AND e.status = 'مسجّل') AS enrolled"
        " FROM classes c WHERE c.id = ?",
        (class_id,),
    )
    if row is None:
        return {"capacity": 0, "enrolled": 0, "available": 0}
    capacity = int(row["capacity"])
    enrolled = int(row["enrolled"])
    return {"capacity": capacity, "enrolled": enrolled, "available": max(capacity - enrolled, 0)}


def students_in_class(class_id: int, year_id: int | None = None) -> list[dict[str, Any]]:
    sql = [
        "SELECT s.id, s.student_no, s.full_name, s.gender, s.status AS student_status,"
        " e.id AS enrollment_id, e.status AS enrollment_status, e.discount, e.enroll_date,"
        " c.id AS class_id, c.name AS class_name",
        "FROM enrollments e",
        "JOIN students s ON s.id = e.student_id",
        "JOIN classes c ON c.id = e.class_id",
        "WHERE e.class_id = ? AND e.status = 'مسجّل'",
    ]
    params: list[Any] = [class_id]
    if year_id:
        sql.append("AND e.year_id = ?")
        params.append(year_id)
    sql.append("ORDER BY s.full_name")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def list_for_teacher(teacher_id: int, year_id: int | None = None) -> list[dict[str, Any]]:
    """الفصول المرتبطة بمعلّم عبر الإسناد أو الإشراف."""
    sql = [
        _CLASS_SELECT,
        "WHERE (c.homeroom_teacher_id = ?"
        "   OR EXISTS (SELECT 1 FROM teaching_assignments ta"
        "               WHERE ta.class_id = c.id AND ta.teacher_id = ?))",
    ]
    params: list[Any] = [teacher_id, teacher_id]
    if year_id:
        sql.append("AND c.year_id = ?")
        params.append(year_id)
    sql.append("ORDER BY c.name")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def is_teacher_of_class(teacher_id: int, class_id: int) -> bool:
    return bool(
        db.scalar(
            "SELECT COUNT(*) FROM classes c WHERE c.id = ? AND c.homeroom_teacher_id = ?",
            (class_id, teacher_id),
            0,
        )
        or db.scalar(
            "SELECT COUNT(*) FROM teaching_assignments WHERE class_id = ? AND teacher_id = ?",
            (class_id, teacher_id),
            0,
        )
    )


def total_enrolled(year_id: int | None = None) -> int:
    if year_id:
        return int(
            db.scalar(
                "SELECT COUNT(*) FROM enrollments WHERE status = 'مسجّل' AND year_id = ?",
                (year_id,),
                0,
            )
            or 0
        )
    return int(db.scalar("SELECT COUNT(*) FROM enrollments WHERE status = 'مسجّل'", (), 0) or 0)
