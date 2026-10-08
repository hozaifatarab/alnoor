"""مستودع بيانات الحضور والغياب وعمليات المسح."""
from __future__ import annotations

from typing import Any

from .. import db


def record_scan_log(
    raw_payload: str,
    result: str,
    student_id: int | None = None,
    class_id: int | None = None,
    scan_date: str = "",
    scan_time: str = "",
    message: str = "",
    ip_address: str | None = None,
    recorded_by: int | None = None,
) -> int:
    return db.execute(
        "INSERT INTO attendance_scans(raw_payload, student_id, class_id, scan_date, scan_time, result, message, ip_address, recorded_by)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (raw_payload, student_id, class_id, scan_date, scan_time, result, message, ip_address, recorded_by),
    )


def get_scan_logs(limit: int = 50, class_id: int | None = None, scan_date: str | None = None) -> list[dict[str, Any]]:
    sql = [
        "SELECT s.*, st.full_name AS student_name, st.student_no, c.name AS class_name",
        "FROM attendance_scans s",
        "LEFT JOIN students st ON st.id = s.student_id",
        "LEFT JOIN classes c ON c.id = s.class_id",
        "WHERE 1=1",
    ]
    params: list[Any] = []
    if class_id:
        sql.append("AND s.class_id = ?")
        params.append(class_id)
    if scan_date:
        sql.append("AND s.scan_date = ?")
        params.append(scan_date)
    sql.append("ORDER BY s.id DESC LIMIT ?")
    params.append(limit)
    return [dict(r) for r in db.query_all(" ".join(sql), params)]


def get_attendance_record(student_id: int, class_id: int, date: str) -> dict[str, Any] | None:
    row = db.query_one(
        "SELECT * FROM attendance WHERE student_id = ? AND class_id = ? AND date = ?",
        (student_id, class_id, date),
    )
    return dict(row) if row else None


def save_attendance(
    student_id: int,
    class_id: int,
    date: str,
    status: str,
    term_id: int | None = None,
    scan_time: str | None = None,
    delay_minutes: int = 0,
    source: str = "qr",
    excuse_reason: str | None = None,
    notes: str | None = None,
    recorded_by: int | None = None,
) -> int:
    existing = get_attendance_record(student_id, class_id, date)
    if existing:
        db.execute(
            "UPDATE attendance SET status = ?, scan_time = ?, delay_minutes = ?, source = ?,"
            " excuse_reason = ?, notes = ?, recorded_by = ?, updated_at = datetime('now', 'localtime')"
            " WHERE id = ?",
            (status, scan_time, delay_minutes, source, excuse_reason, notes, recorded_by, existing["id"]),
        )
        return existing["id"]
    return db.execute(
        "INSERT INTO attendance(student_id, class_id, term_id, date, status, scan_time, delay_minutes, source, excuse_reason, notes, recorded_by)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (student_id, class_id, term_id, date, status, scan_time, delay_minutes, source, excuse_reason, notes, recorded_by),
    )


def list_class_attendance_for_date(class_id: int, date: str) -> list[dict[str, Any]]:
    """قائمة حضور جميع طلاب الفصل لتاريخ معين (تشمل غير المسجلين كـ 'غير مسجل')."""
    sql = """
    SELECT s.id AS student_id, s.student_no, s.full_name, s.gender, s.status AS student_status,
           a.id AS attendance_id, a.status AS attendance_status, a.scan_time, a.delay_minutes,
           a.source, a.excuse_reason, a.notes, a.created_at AS recorded_at
      FROM enrollments e
      JOIN students s ON s.id = e.student_id
      LEFT JOIN attendance a ON a.student_id = s.id AND a.class_id = e.class_id AND a.date = ?
     WHERE e.class_id = ? AND e.status = 'مسجّل'
     ORDER BY s.full_name
    """
    return [dict(r) for r in db.query_all(sql, (date, class_id))]


def class_attendance_summary(class_id: int, date: str) -> dict[str, int]:
    """إحصائية سريعة لحضور الفصل لتاريخ محدد."""
    rows = list_class_attendance_for_date(class_id, date)
    total = len(rows)
    present = sum(1 for r in rows if r.get("attendance_status") == "حاضر")
    late = sum(1 for r in rows if r.get("attendance_status") == "متأخر")
    excused = sum(1 for r in rows if r.get("attendance_status") == "بعذر")
    absent = sum(1 for r in rows if r.get("attendance_status") == "غائب")
    unrecorded = sum(1 for r in rows if not r.get("attendance_status"))
    return {
        "total": total,
        "present": present,
        "late": late,
        "excused": excused,
        "absent": absent,
        "unrecorded": unrecorded,
    }


def student_attendance_history(student_id: int, limit: int = 100) -> list[dict[str, Any]]:
    sql = """
    SELECT a.*, c.name AS class_name
      FROM attendance a
      JOIN classes c ON c.id = a.class_id
     WHERE a.student_id = ?
     ORDER BY a.date DESC, a.scan_time DESC
     LIMIT ?
    """
    return [dict(r) for r in db.query_all(sql, (student_id, limit))]
