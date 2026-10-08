"""خدمة الحضور والغياب: التحقق من التوقيع، السياسات، التسجيل التلقائي، والإغلاق."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from core import qr
from core.exceptions import NotFoundError, ValidationError
from core.repos import academic as academic_repo
from core.repos import attendance as attendance_repo
from core.repos import audit
from core.repos import classes as classes_repo
from core.repos import students as students_repo



def _current_time_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _calculate_delay(scan_time_str: str, period_start_str: str) -> int:
    try:
        t_scan = datetime.strptime(scan_time_str, "%H:%M:%S").time()
        t_start = datetime.strptime(period_start_str, "%H:%M").time()
    except Exception:
        return 0
    scan_mins = t_scan.hour * 60 + t_scan.minute
    start_mins = t_start.hour * 60 + t_start.minute
    return max(0, scan_mins - start_mins)


def process_qr_scan(
    raw_payload: str,
    class_id: int,
    date: str | None = None,
    period_start: str = "07:30",
    late_threshold_minutes: int = 15,
    ip_address: str | None = None,
    actor: dict[str, Any] | None = None,
    allow_unsigned_student_no: bool = False,
) -> dict[str, Any]:
    scan_date = date or _today_str()
    scan_time = _current_time_str()
    user_id = actor.get("id") if actor else None

    is_valid, student_no, reason = qr.verify_payload(
        raw_payload, allow_unsigned_student_no=allow_unsigned_student_no
    )
    if not is_valid:
        attendance_repo.record_scan_log(
            raw_payload, "invalid_signature", None, class_id, scan_date, scan_time, reason, ip_address, user_id
        )
        return {"success": False, "status": "invalid_signature", "message": f"رمز غير صالح: {reason}"}

    student = students_repo.get_by_student_no(student_no)
    if not student:
        attendance_repo.record_scan_log(
            raw_payload, "not_found", None, class_id, scan_date, scan_time, f"الطالب {student_no} غير موجود", ip_address, user_id
        )
        return {"success": False, "status": "not_found", "message": f"الرقم الأكاديمي ({student_no}) غير مسجل في النظام"}

    student_id = int(student["id"])

    if student["status"] != "منتظم":
        attendance_repo.record_scan_log(
            raw_payload, "inactive", student_id, class_id, scan_date, scan_time, f"حالة الطالب: {student['status']}", ip_address, user_id
        )
        return {"success": False, "status": "inactive", "message": f"قيد الطالب غير منتظم (الحالة: {student['status']})"}

    enrolled = classes_repo.students_in_class(class_id)
    if not any(s["id"] == student_id for s in enrolled):
        attendance_repo.record_scan_log(
            raw_payload, "not_enrolled", student_id, class_id, scan_date, scan_time, "الطالب غير مسجل في الفصل", ip_address, user_id
        )
        return {"success": False, "status": "not_enrolled", "message": f"الطالب {student['full_name']} ليس مسجلاً في هذا الفصل!"}

    existing = attendance_repo.get_attendance_record(student_id, class_id, scan_date)
    if existing:
        attendance_repo.record_scan_log(
            raw_payload, "duplicate", student_id, class_id, scan_date, scan_time, "مسجل مسبقاً", ip_address, user_id
        )
        return {
            "success": False,
            "status": "duplicate",
            "message": f"تم تسجيل الطالب {student['full_name']} مسبقاً لهذا اليوم ({existing['status']})",
            "student": student,
        }

    delay = _calculate_delay(scan_time, period_start)
    status = "متأخر" if delay > late_threshold_minutes else "حاضر"

    klass = classes_repo.get(class_id)
    term_row = academic_repo.get_current_term(klass["year_id"]) if klass else None
    term_id = term_row["id"] if term_row else None

    att_id = attendance_repo.save_attendance(
        student_id=student_id,
        class_id=class_id,
        date=scan_date,
        status=status,
        term_id=term_id,
        scan_time=scan_time,
        delay_minutes=delay,
        source=(
            "manual"
            if allow_unsigned_student_no and not raw_payload.strip().startswith(f"{qr.PAYLOAD_PREFIX}|")
            else "qr"
        ),
        recorded_by=user_id,
    )

    attendance_repo.record_scan_log(
        raw_payload, "success", student_id, class_id, scan_date, scan_time, f"تسجيل بنجاح: {status}", ip_address, user_id
    )
    return {
        "success": True,
        "status": status,
        "delay_minutes": delay,
        "scan_time": scan_time,
        "student": student,
        "attendance_id": att_id,
        "message": f"تم تسجيل {student['full_name']} ({status}) بنجاح",
    }


def record_manual(
    student_id: int,
    class_id: int,
    date: str,
    status: str,
    excuse_reason: str | None = None,
    notes: str | None = None,
    actor: dict[str, Any] | None = None,
) -> int:
    """تسجيل يدوي من قبل المعلم أو الإدارة."""
    if status not in ("حاضر", "متأخر", "غائب", "بعذر"):
        raise ValidationError("حالة الحضور غير صالحة")
    if status == "بعذر" and not (excuse_reason and excuse_reason.strip()):
        raise ValidationError("يجب توضيح سبب العذر عند اختيار حالة (بعذر)")

    klass = classes_repo.get(class_id)
    if not klass:
        raise NotFoundError("الفصل غير موجود")

    term_row = academic_repo.get_current_term(klass["year_id"]) if klass else None
    term_id = term_row["id"] if term_row else None
    user_id = actor.get("id") if actor else None

    att_id = attendance_repo.save_attendance(
        student_id=student_id,
        class_id=class_id,
        date=date,
        status=status,
        term_id=term_id,
        scan_time=_current_time_str(),
        delay_minutes=0,
        source="manual",
        excuse_reason=excuse_reason,
        notes=notes,
        recorded_by=user_id,
    )
    audit.log(
        "تسجيل يدوي",
        entity="attendance",
        entity_id=att_id,
        details=f"تسجيل يدوي لطالب {student_id} في الفصل {class_id} كـ {status}",
        user=actor,
    )
    return att_id


def bulk_mark_present(class_id: int, date: str, actor: dict[str, Any] | None = None) -> int:
    """تحضير جميع طلاب الفصل كـ 'حاضر' للطلاب الذين لم يُسجَّلوا بعد."""
    students = classes_repo.students_in_class(class_id)
    klass = classes_repo.get(class_id)
    term_row = academic_repo.get_current_term(klass["year_id"]) if klass else None
    term_id = term_row["id"] if term_row else None
    user_id = actor.get("id") if actor else None

    count = 0
    now_time = _current_time_str()
    for s in students:
        existing = attendance_repo.get_attendance_record(s["id"], class_id, date)
        if not existing:
            attendance_repo.save_attendance(
                student_id=s["id"],
                class_id=class_id,
                date=date,
                status="حاضر",
                term_id=term_id,
                scan_time=now_time,
                delay_minutes=0,
                source="bulk",
                recorded_by=user_id,
            )
            count += 1
    return count


def close_day_attendance(class_id: int, date: str, actor: dict[str, Any] | None = None) -> int:
    """إغلاق اليوم: تحويل كل طالب لم يُسجل حضوره إلى 'غائب' تلقائياً."""
    students = classes_repo.students_in_class(class_id)
    klass = classes_repo.get(class_id)
    term_row = academic_repo.get_current_term(klass["year_id"]) if klass else None
    term_id = term_row["id"] if term_row else None
    user_id = actor.get("id") if actor else None

    marked_absent = 0
    for s in students:
        existing = attendance_repo.get_attendance_record(s["id"], class_id, date)
        if not existing:
            attendance_repo.save_attendance(
                student_id=s["id"],
                class_id=class_id,
                date=date,
                status="غائب",
                term_id=term_id,
                scan_time=None,
                delay_minutes=0,
                source="auto_absent",
                recorded_by=user_id,
            )
            marked_absent += 1
    return marked_absent

