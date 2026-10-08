"""مستودع التقييمات والاختبارات والدرجات."""
from __future__ import annotations

from typing import Any

from .. import db


def create_assessment(
    name: str,
    subject_id: int,
    class_id: int,
    term_id: int,
    max_score: float,
    weight: float = 100.0,
    assessment_date: str | None = None,
    created_by: int | None = None,
) -> int:
    return db.execute(
        "INSERT INTO assessments(name, subject_id, class_id, term_id, max_score, weight, assessment_date, created_by)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, subject_id, class_id, term_id, max_score, weight, assessment_date, created_by),
    )


def list_assessments(class_id: int | None = None, subject_id: int | None = None, term_id: int | None = None) -> list[dict[str, Any]]:
    sql = [
        "SELECT a.*, s.name AS subject_name, c.name AS class_name, t.name AS term_name,",
        " (SELECT COUNT(*) FROM grades g WHERE g.assessment_id = a.id) AS graded_count",
        "FROM assessments a",
        "JOIN subjects s ON s.id = a.subject_id",
        "JOIN classes c ON c.id = a.class_id",
        "JOIN terms t ON t.id = a.term_id",
        "WHERE 1=1",
    ]
    params: list[Any] = []
    if class_id:
        sql.append("AND a.class_id = ?")
        params.append(class_id)
    if subject_id:
        sql.append("AND a.subject_id = ?")
        params.append(subject_id)
    if term_id:
        sql.append("AND a.term_id = ?")
        params.append(term_id)
    sql.append("ORDER BY a.id DESC")
    return [dict(r) for r in db.query_all(" ".join(sql), params)]


def get_assessment(assessment_id: int) -> dict[str, Any] | None:
    row = db.query_one(
        "SELECT a.*, s.name AS subject_name, c.name AS class_name, t.name AS term_name"
        " FROM assessments a"
        " JOIN subjects s ON s.id = a.subject_id"
        " JOIN classes c ON c.id = a.class_id"
        " JOIN terms t ON t.id = a.term_id"
        " WHERE a.id = ?",
        (assessment_id,),
    )
    return dict(row) if row else None


def delete_assessment(assessment_id: int) -> None:
    db.execute("DELETE FROM assessments WHERE id = ?", (assessment_id,))


def save_grade(assessment_id: int, student_id: int, score: float, notes: str | None = None, recorded_by: int | None = None) -> int:
    existing = db.query_one("SELECT id FROM grades WHERE assessment_id = ? AND student_id = ?", (assessment_id, student_id))
    if existing:
        db.execute(
            "UPDATE grades SET score = ?, notes = ?, recorded_by = ?, recorded_at = datetime('now', 'localtime') WHERE id = ?",
            (score, notes, recorded_by, existing["id"]),
        )
        return existing["id"]
    return db.execute(
        "INSERT INTO grades(assessment_id, student_id, score, notes, recorded_by) VALUES (?, ?, ?, ?, ?)",
        (assessment_id, student_id, score, notes, recorded_by),
    )


def list_assessment_grades(assessment_id: int, class_id: int) -> list[dict[str, Any]]:
    sql = """
    SELECT s.id AS student_id, s.student_no, s.full_name,
           g.id AS grade_id, g.score, g.notes, g.recorded_at
      FROM enrollments e
      JOIN students s ON s.id = e.student_id
      LEFT JOIN grades g ON g.student_id = s.id AND g.assessment_id = ?
     WHERE e.class_id = ? AND e.status = 'مسجّل'
     ORDER BY s.full_name
    """
    return [dict(r) for r in db.query_all(sql, (assessment_id, class_id))]


def student_subject_grades(student_id: int, subject_id: int | None = None, term_id: int | None = None) -> list[dict[str, Any]]:
    sql = [
        "SELECT g.score, g.notes, g.recorded_at, a.name AS assessment_name, a.max_score, a.weight,",
        " s.name AS subject_name, t.name AS term_name",
        "FROM grades g",
        "JOIN assessments a ON a.id = g.assessment_id",
        "JOIN subjects s ON s.id = a.subject_id",
        "JOIN terms t ON t.id = a.term_id",
        "WHERE g.student_id = ?",
    ]
    params: list[Any] = [student_id]
    if subject_id:
        sql.append("AND a.subject_id = ?")
        params.append(subject_id)
    if term_id:
        sql.append("AND a.term_id = ?")
        params.append(term_id)
    sql.append("ORDER BY a.term_id, s.name, a.id")
    return [dict(r) for r in db.query_all(" ".join(sql), params)]
