"""اختبارات محرك تسجيل الحضور بـ QR: التحقق، التكرار، التأخير، والإغلاق التلقائي."""
from __future__ import annotations

import unittest

from core import qr
from core.exceptions import NotFoundError, ValidationError
from core.repos import attendance as attendance_repo
from core.services import attendance_service, classes_service, enrollments_service
from tests.base import DbTestCase


class AttendanceQrTests(DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.year_id = self.make_year("2026/2027")
        self.term_id = self.make_term(self.year_id, "الفصل الأول")
        self.level_id = self.make_level("متوسط")
        self.class_id = self.make_class(self.level_id, self.year_id, "أول متوسط أ")

        self.std1_id = self.make_student("أحمد العتيبي", student_no="STD-001")
        self.std2_id = self.make_student("سالم القحطاني", student_no="STD-002")
        self.std_inactive_id = self.make_student("فهد موقوف", student_no="STD-003", status="موقوف")

        enrollments_service.enroll(self.std1_id, self.class_id, actor=self.actor)
        enrollments_service.enroll(self.std2_id, self.class_id, actor=self.actor)

    def test_successful_qr_scan(self) -> None:
        payload = qr.make_payload("STD-001", "2026")
        res = attendance_service.process_qr_scan(
            raw_payload=payload,
            class_id=self.class_id,
            date="2026-10-01",
            period_start="23:59",  # أي مسح قبله يعتبر حاضراً بدون تأخير
            actor=self.actor,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "حاضر")
        record = attendance_repo.get_attendance_record(self.std1_id, self.class_id, "2026-10-01")
        self.assertIsNotNone(record)
        self.assertEqual(record["status"], "حاضر")

    def test_duplicate_scan_same_day_rejected(self) -> None:
        payload = qr.make_payload("STD-001", "2026")
        res1 = attendance_service.process_qr_scan(payload, self.class_id, date="2026-10-01", actor=self.actor)
        self.assertTrue(res1["success"])

        res2 = attendance_service.process_qr_scan(payload, self.class_id, date="2026-10-01", actor=self.actor)
        self.assertFalse(res2["success"])
        self.assertEqual(res2["status"], "duplicate")

    def test_inactive_student_scan_rejected(self) -> None:
        payload = qr.make_payload("STD-003", "2026")
        res = attendance_service.process_qr_scan(payload, self.class_id, date="2026-10-01", actor=self.actor)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "inactive")

    def test_not_enrolled_student_scan_rejected(self) -> None:
        other_class = self.make_class(self.level_id, self.year_id, "فصل آخر")
        payload = qr.make_payload("STD-001", "2026")
        res = attendance_service.process_qr_scan(payload, other_class, date="2026-10-01", actor=self.actor)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "not_enrolled")

    def test_invalid_signature_qr_rejected(self) -> None:
        res = attendance_service.process_qr_scan("STD|2026|STD-001|FAKESIG123", self.class_id, actor=self.actor)
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "invalid_signature")

    def test_unsigned_student_number_rejected_by_camera_path(self) -> None:
        result = attendance_service.process_qr_scan(
            "STD-001", self.class_id, date="2026-10-02", actor=self.actor
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "invalid_signature")
        self.assertIsNone(
            attendance_repo.get_attendance_record(self.std1_id, self.class_id, "2026-10-02")
        )

    def test_unsigned_student_number_allowed_only_on_manual_usb_path(self) -> None:
        result = attendance_service.process_qr_scan(
            "STD-001",
            self.class_id,
            date="2026-10-02",
            actor=self.actor,
            allow_unsigned_student_no=True,
        )

        self.assertTrue(result["success"])
        record = attendance_repo.get_attendance_record(self.std1_id, self.class_id, "2026-10-02")
        self.assertEqual(record["source"], "manual")

    def test_unsigned_student_number_rejected_by_camera_path(self) -> None:
        result = attendance_service.process_qr_scan(
            "STD-001", self.class_id, date="2026-10-02", actor=self.actor
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "invalid_signature")
        self.assertIsNone(
            attendance_repo.get_attendance_record(self.std1_id, self.class_id, "2026-10-02")
        )

    def test_unsigned_student_number_allowed_only_on_manual_usb_path(self) -> None:
        result = attendance_service.process_qr_scan(
            "STD-001",
            self.class_id,
            date="2026-10-02",
            actor=self.actor,
            allow_unsigned_student_no=True,
        )

        self.assertTrue(result["success"])
        record = attendance_repo.get_attendance_record(self.std1_id, self.class_id, "2026-10-02")
        self.assertEqual(record["source"], "manual")

    def test_manual_attendance_and_excuse(self) -> None:
        with self.assertRaises(ValidationError):
            attendance_service.record_manual(self.std1_id, self.class_id, "2026-10-02", "بعذر", excuse_reason="", actor=self.actor)

        att_id = attendance_service.record_manual(
            self.std1_id, self.class_id, "2026-10-02", "بعذر", excuse_reason="تقرير طبي مصدق", actor=self.actor
        )
        record = attendance_repo.get_attendance_record(self.std1_id, self.class_id, "2026-10-02")
        self.assertEqual(record["status"], "بعذر")
        self.assertEqual(record["excuse_reason"], "تقرير طبي مصدق")

    def test_bulk_mark_present_and_close_day(self) -> None:
        # تحضير جماعي
        marked = attendance_service.bulk_mark_present(self.class_id, "2026-10-03", actor=self.actor)
        self.assertEqual(marked, 2)
        summary = attendance_repo.class_attendance_summary(self.class_id, "2026-10-03")
        self.assertEqual(summary["present"], 2)
        self.assertEqual(summary["unrecorded"], 0)

        # يوم جديد: مسح طالب واحد ثم إغلاق اليوم للبقية
        payload = qr.make_payload("STD-001", "2026")
        attendance_service.process_qr_scan(payload, self.class_id, date="2026-10-04", period_start="23:59", actor=self.actor)
        closed_absent = attendance_service.close_day_attendance(self.class_id, "2026-10-04", actor=self.actor)
        self.assertEqual(closed_absent, 1)

        summary2 = attendance_repo.class_attendance_summary(self.class_id, "2026-10-04")
        self.assertEqual(summary2["present"], 1)
        self.assertEqual(summary2["absent"], 1)
        self.assertEqual(summary2["unrecorded"], 0)


if __name__ == "__main__":
    unittest.main()
