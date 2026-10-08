"""مستودع التسجيلات (طالب ↔ فصل) والإسناد التدريسي."""
from __future__ import annotations

from typing import Any

from .. import db

# ---------------- التسجيلات ----------------

def active_for_student(student_id: int, year_id: int | None = None) -> dict[str, Any] | None:
    if year_id:
        row = db.query_one(
            "SELECT * FROM enrollments WHERE student_id = ? AND year_id = ?", (student_id, year_id)
        )
    else:
        row = db.query_one(
            "SELECT * FROM enrollments WHERE student_id = ? AND status = 'مسجّل'"
            " ORDER BY id DESC LIMIT 1",
            (student_id,),
        )
    return dict(row) if row else None


def get(enrollment_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM enrollments WHERE id = ?", (enrollment_id,))
    return dict(row) if row else None


def create(
    student_id: int,
    class_id: int,
    year_id: int,
    term_id: int | None,
    enroll_date: str,
    discount: float = 0.0,
    status: str = "مسجّل",
) -> int:
    return db.execute(
        "INSERT INTO enrollments(student_id, class_id, year_id, term_id, enroll_date,"
        " discount, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (student_id, class_id, year_id, term_id, enroll_date, discount, status),
    )


def change_class(enrollment_id: int, class_id: int, term_id: int | None = None) -> None:
    db.execute(
        "UPDATE enrollments SET class_id = ?, term_id = COALESCE(?, term_id) WHERE id = ?",
        (class_id, term_id, enrollment_id),
    )


def set_status(enrollment_id: int, status: str) -> None:
    db.execute("UPDATE enrollments SET status = ? WHERE id = ?", (status, enrollment_id))


def set_discount(enrollment_id: int, discount: float) -> None:
    db.execute("UPDATE enrollments SET discount = ? WHERE id = ?", (discount, enrollment_id))


def delete(enrollment_id: int) -> None:
    db.execute("DELETE FROM enrollments WHERE id = ?", (enrollment_id,))


def list_enrollments(
    year_id: int | None = None, class_id: int | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    sql = [
        "SELECT e.*, s.full_name, s.student_no, c.name AS class_name, l.name AS level_name,"
        " y.name AS year_name, t.name AS term_name",
        "FROM enrollments e",
        "JOIN students s ON s.id = e.student_id",
        "JOIN classes c ON c.id = e.class_id",
        "JOIN levels l ON l.id = c.level_id",
        "JOIN academic_years y ON y.id = e.year_id",
        "LEFT JOIN terms t ON t.id = e.term_id",
        "WHERE 1 = 1",
    ]
    params: list[Any] = []
    if year_id:
        sql.append("AND e.year_id = ?")
        params.append(year_id)
    if class_id:
        sql.append("AND e.class_id = ?")
        params.append(class_id)
    if status:
        sql.append("AND e.status = ?")
        params.append(status)
    sql.append("ORDER BY c.name, s.full_name")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def count_enrolled(class_id: int) -> int:
    return int(
        db.scalar(
            "SELECT COUNT(*) FROM enrollments WHERE class_id = ? AND status = 'مسجّل'",
            (class_id,),
            0,
        )
        or 0
    )


def distinct_years() -> list[dict[str, Any]]:
    rows = db.query_all(
        "SELECT DISTINCT y.id, y.name FROM academic_years y ORDER BY y.name DESC"
    )
    return [dict(row) for row in rows]


# ---------------- الإسناد التدريسي ----------------

def list_assignments(
    term_id: int | None = None,
    class_id: int | None = None,
    teacher_id: int | None = None,
    year_id: int | None = None,
) -> list[dict[str, Any]]:
    sql = [
        "SELECT ta.*, t.full_name AS teacher_name, s.name AS subject_name, s.code AS subject_code,"
        " c.name AS class_name, tm.name AS term_name, y.name AS year_name",
        "FROM teaching_assignments ta",
        "JOIN teachers t ON t.id = ta.teacher_id",
        "JOIN subjects s ON s.id = ta.subject_id",
        "JOIN classes c ON c.id = ta.class_id",
        "JOIN academic_years y ON y.id = c.year_id",
        "LEFT JOIN terms tm ON tm.id = ta.term_id",
        "WHERE 1 = 1",
    ]
    params: list[Any] = []
    if term_id:
        sql.append("AND (ta.term_id = ? OR ta.term_id IS NULL)")
        params.append(term_id)
    if class_id:
        sql.append("AND ta.class_id = ?")
        params.append(class_id)
    if teacher_id:
        sql.append("AND ta.teacher_id = ?")
        params.append(teacher_id)
    if year_id:
        sql.append("AND c.year_id = ?")
        params.append(year_id)
    sql.append("ORDER BY c.name, s.name")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def get_assignment(assignment_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM teaching_assignments WHERE id = ?", (assignment_id,))
    return dict(row) if row else None


def assignment_exists(teacher_id: int, subject_id: int, class_id: int) -> bool:
    return bool(
        db.scalar(
            "SELECT COUNT(*) FROM teaching_assignments"
            " WHERE teacher_id = ? AND subject_id = ? AND class_id = ?",
            (teacher_id, subject_id, class_id),
            0,
        )
    )


def create_assignment(teacher_id: int, subject_id: int, class_id: int, term_id: int | None) -> int:
    return db.execute(
        "INSERT INTO teaching_assignments(teacher_id, subject_id, class_id, term_id)"
        " VALUES (?, ?, ?, ?)",
        (teacher_id, subject_id, class_id, term_id),
    )


def delete_assignment(assignment_id: int) -> None:
    db.execute("DELETE FROM teaching_assignments WHERE id = ?", (assignment_id,))
