"""شاشة تسجيل الحضور بـ QR: كاميرا + إدخال يدوي + تحضير جماعي + إغلاق اليوم."""
from __future__ import annotations

from typing import Any

from pywebio.input import input, input_group, select
from pywebio.output import put_buttons, put_html, put_scope, use_scope
from pywebio.session import go_app

from core import auth, db
from core.repos import attendance as attendance_repo
from core.repos import settings as settings_repo
from core.services import attendance_service, classes_service
from ui import components, layout, options, scanner

APP = "attendance_scan"


def attendance_scan() -> None:
    """شاشة المسح الرئيسية (المسار الأساسي: بطاقات الطالب)."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="تسجيل الحضور بـ QR")

    with components.error_boundary("تسجيل الحضور"):
        setup = _render_setup()
        class_id = setup["class_id"]
        date = setup["date"]
        period_start = setup["period_start"]
        late_minutes = setup["late_minutes"]

        _render_summary(class_id, date)
        put_scope("scan_feed")

        layout.section("تسجيل المسح", "كاميرا، أو رفع صورة QR، أو الإدخال اليدوي/قارئ الباركود")
        scanner.render_camera_area()
        put_buttons(
            [
                {"label": "▶ تشغيل الكاميرا والمسح المستمر", "value": "start", "color": "primary"},
                {"label": "📤 رفع صورة QR بدل الكاميرا", "value": "upload", "color": "secondary"},
                {"label": "■ إيقاف", "value": "stop", "color": "secondary"},
                {"label": "✔ الكل حاضر", "value": "bulk", "color": "secondary"},
                {"label": "🔒 إغلاق اليوم (البقية غائب)", "value": "close", "color": "danger"},
            ],
            onclick=lambda value: _handle_action(
                value, class_id, date, period_start, late_minutes
            ),
            small=True,
        )
        scanner.render_manual_entry(
            lambda code: _process_code(
                code, class_id, date, period_start, late_minutes, allow_unsigned_student_no=True
            )
        )
        layout.footer()


def _render_setup() -> dict[str, Any]:
    """اختيار الفصل والتاريخ وبداية الحصة (كل شيء في نموذج واحد)."""
    class_options = options.classes()
    if not class_options:
        layout.alert("لا توجد فصول معرّفة. أضف الفصول أولاً من شاشة «الفصول».", "warn")
        go_app("classes", new_window=False)
        return {"class_id": 0, "date": "", "period_start": "07:30", "late_minutes": 15}

    today = db.scalar("SELECT date('now','localtime')")
    data = input_group(
        "بيانات الجلسة",
        [
            select("الفصل *", name="class_id", options=class_options, required=True),
            input(
                "تاريخ اليوم",
                name="date",
                value=today,
                required=True,
                help_text="بصيغة YYYY-MM-DD (افتراضياً اليوم)",
            ),
            input(
                "بداية الحصة",
                name="period_start",
                value=settings_repo.get("default_period_start", "07:30"),
                required=False,
            ),
            input(
                "دقائق التأخير المسموحة",
                name="late_minutes",
                value=settings_repo.get("late_after_minutes", "15"),
                required=False,
            ),
        ],
        cancelable=False,
    )
    try:
        late_minutes = int(str(data.get("late_minutes") or "15"))
    except ValueError:
        late_minutes = 15
    return {
        "class_id": int(data["class_id"]),
        "date": str(data["date"]).strip(),
        "period_start": str(data.get("period_start") or "07:30").strip(),
        "late_minutes": late_minutes,
    }


def _render_summary(class_id: int, date: str) -> None:
    """بطاقة ملخص حضور اليوم + سجل عمليات المسح."""
    summary = attendance_repo.class_attendance_summary(class_id, date)
    klass = classes_service.get_class(class_id)
    layout.kpi_cards(
        [
            {"label": "إجمالي الطلاب", "value": summary["total"], "hint": klass["name"] if klass else ""},
            {"label": "حاضر", "value": summary["present"]},
            {"label": "متأخر", "value": summary["late"], "kind": "warn" if summary["late"] else ""},
            {"label": "غائب", "value": summary["absent"], "kind": "danger" if summary["absent"] else ""},
            {"label": "لم يُسجَّل بعد", "value": summary["unrecorded"]},
        ]
    )
    _render_scan_log(class_id, date)


def _render_scan_log(class_id: int, date: str) -> None:
    """آخر عمليات المسح لهذا الفصل/اليوم."""
    logs = attendance_repo.get_scan_logs(limit=12, class_id=class_id, scan_date=date)
    layout.section("سجل عمليات المسح", "يُحدَّث تلقائياً بعد كل قراءة")
    components.table(
        ["الوقت", "الطالب", "النتيجة", "ملاحظة"],
        [
            [
                row.get("scan_time") or "—",
                row.get("student_name") or (row.get("raw_payload") or "")[:20],
                _result_chip(row.get("result")),
                row.get("message") or "—",
            ]
            for row in logs
        ],
        empty_message="لا توجد عمليات مسح بعد",
    )


def _result_chip(result: str | None) -> str:
    mapping = {
        "success": ("مسجّل", "ok"),
        "duplicate": ("مكرر", "warn"),
        "invalid_signature": ("توقيع غير صالح", "bad"),
        "not_enrolled": ("غير مسجّل بالفصل", "bad"),
        "inactive": ("قيد غير منتظم", "warn"),
        "not_found": ("غير موجود", "bad"),
    }
    label, kind = mapping.get(result or "", (result or "—", "muted"))
    return components.chip(label, kind)


def _handle_action(
    value: str, class_id: int, date: str, period_start: str, late_minutes: int
) -> None:
    """أزرار التحكم: تشغيل/إيقاف الكاميرا، الكل حاضر، إغلاق اليوم."""
    if value == "stop":
        scanner.stop_scanner()
        components.toast_ok("تم إيقاف المسح")
        return
    if value == "upload":
        _run_upload_loop(class_id, date, period_start, late_minutes)
        return
    if value == "bulk":
        with components.error_boundary("تحضير جماعي"):
            count = attendance_service.bulk_mark_present(class_id, date, actor=auth.current_user())
            components.toast_ok(f"تم تحضير {count} طالباً (لمن لم يُسجَّل بعد)")
            go_app(APP, new_window=False)
        return
    if value == "close":
        if not components.confirm(
            "سيتم وضع «غائب» لكل طالب لم يُسجَّل حضوره اليوم. متابعة؟", "إغلاق اليوم", "إلغاء"
        ):
            return
        with components.error_boundary("إغلاق اليوم"):
            count = attendance_service.close_day_attendance(class_id, date, actor=auth.current_user())
            components.toast_ok(f"تم إغلاق اليوم — {count} طالباً سُجّل كغائب")
            go_app(APP, new_window=False)
        return
    if value == "start":
        _run_scan_loop(class_id, date, period_start, late_minutes)


def _run_upload_loop(class_id: int, date: str, period_start: str, late_minutes: int) -> None:
    """حلقة رفع الصور: نفس قناة الكاميرا لكن بدون getUserMedia (تعمل على أي اتصال).

    تُرفع صورة البطاقة من الجهاز (تصوير مسبق بالهاتف مثلاً)، تُفكّ داخل
    المتصفح عبر jsQR، ثم تُمرَّر لمعالجة المسح العادية مع التحقق من التوقيع.
    """
    scanner.stop_scanner()
    scanner.render_upload_area()
    scanner.bind_upload_reader()
    components.toast_ok("اختر صورة بطاقة الطالب — ستُقرأ وتُسجَّل فوراً، وكرر لكل طالب")

    while True:
        code = scanner.wait_for_code(timeout_ms=60000)
        if code is None or code == "__TICK__":
            if scanner.scanner_stopped():
                components.toast_ok("انتهى وضع رفع الصور")
                return
            continue
        if scanner.scanner_stopped():
            return
        _process_code(code, class_id, date, period_start, late_minutes)


def _run_scan_loop(class_id: int, date: str, period_start: str, late_minutes: int) -> None:
    """حلقة المسح: تعتمد على Promise في المتصفح مع نبضة إيقاف كل 15 ثانية."""
    scanner.start_scanner()
    components.toast_ok("جارٍ تشغيل الكاميرا… ابدأ بعرض البطاقات")

    while True:
        code = scanner.wait_for_code(timeout_ms=15000)
        if code is None or code == "__TICK__":
            error = scanner.camera_error()
            if error:
                layout.alert(error, "warn")
                scanner.render_manual_entry(
                    lambda value: _process_code(
                        value, class_id, date, period_start, late_minutes, allow_unsigned_student_no=True
                    )
                )
                return
            if scanner.scanner_stopped():
                components.toast_ok("تم إيقاف المسح")
                return
            continue
        if scanner.scanner_stopped():
            return
        _process_code(code, class_id, date, period_start, late_minutes)
        scanner.resume_scanner()


def _process_code(
    code: str,
    class_id: int,
    date: str,
    period_start: str,
    late_minutes: int,
    *,
    allow_unsigned_student_no: bool = False,
) -> None:
    """معالجة قراءة واحدة وعرض النتيجة فوراً بجانب الكاميرا."""
    if not code:
        return
    result = attendance_service.process_qr_scan(
        raw_payload=code,
        class_id=class_id,
        date=date,
        period_start=period_start or "07:30",
        late_threshold_minutes=late_minutes,
        ip_address=auth.client_ip(),
        actor=auth.current_user(),
        allow_unsigned_student_no=allow_unsigned_student_no,
    )
    ok = bool(result.get("success"))
    with use_scope("scan_feed", clear=False):
        scanner.render_feedback(str(result.get("message", "")), ok)
        if ok:
            student = result.get("student") or {}
            put_html(
                f'<div class="inst-card" style="padding:8px 12px">'
                f'<b>{layout.escape_html(student.get("full_name", ""))}</b> — '
                f'{layout.escape_html(student.get("student_no", ""))} — '
                f'{components.chip(str(result.get("status", "")), "ok")} '
                f'<span class="section-hint">الساعة {layout.escape_html(result.get("scan_time", ""))}</span>'
                "</div>"
            )

