"""اختبارات الطلاب: الترقيم، التحقق، الحالات، والعلاقة مع التسجيل."""
from __future__ import annotations

import re
import unittest

from core import config
from core.exceptions import BusinessRuleError, DuplicateError, NotFoundError, ValidationError
from core.services import enrollments_service, students_service

from .base import DbTestCase


class StudentCrudTests(DbTestCase):
    def test_auto_student_number_format(self) -> None:
        student_id = self.make_student()
        student = students_service.get_student(student_id)
        self.assertRegex(student["student_no"], r"^\d{4}-\d{4}$")

    def test_sequential_student_numbers(self) -> None:
        first = students_service.get_student(self.make_student("طالب أول"))
        second = students_service.get_student(self.make_student("طالب ثانٍ"))
        self.assertEqual(int(second["student_no"].split("-")[1]), int(first["student_no"].split("-")[1]) + 1)

    def test_explicit_number_duplicate_rejected(self) -> None:
        students_service.create_student(
            {"full_name": "طالب أول", "student_no": "2026-0100"}, year_name="2026", actor=self.actor
        )
        with self.assertRaises(BusinessRuleError):
            students_service.create_student(
                {"full_name": "طالب ثانٍ", "student_no": "2026-0100"}, year_name="2026", actor=self.actor
            )

    def test_duplicate_national_id_rejected(self) -> None:
        self.make_student("طالب أول", national_id="1234567890")
        with self.assertRaises(DuplicateError):
            self.make_student("طالب ثانٍ", national_id="1234567890")

    def test_future_birth_date_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.make_student("طالب", birth_date="2999-01-01")

    def test_invalid_gender_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.make_student("طالب", gender="غير محدد")

    def test_short_name_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.make_student("أ")

    def test_invalid_guardian_phone_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.make_student("طالب جديد", guardian_phone="12")

    def test_missing_student_raises_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            students_service.get_student(999)

    def test_update_student(self) -> None:
        student_id = self.make_student("اسم قديم")
        students_service.update_student(
            student_id,
            {"full_name": "اسم جديد", "status": "منتظم", "guardian_name": "ولي الأمر"},
            actor=self.actor,
        )
        student = students_service.get_student(student_id)
        self.assertEqual(student["full_name"], "اسم جديد")
        self.assertEqual(student["guardian_name"], "ولي الأمر")

    def test_delete_student_cascades_enrollment(self) -> None:
        year_id = self.make_year()
        level_id = self.make_level()
        class_id = self.make_class(level_id, year_id)
        student_id = self.make_student()
        enrollments_service.enroll(student_id, class_id, actor=self.actor)
        students_service.delete_student(student_id, actor=self.actor)
        self.assertEqual(enrollments_service.list_enrollments(), [])


class StudentStatusTests(DbTestCase):
    def test_withdraw_closes_enrollment(self) -> None:
        year_id = self.make_year()
        level_id = self.make_level()
        class_id = self.make_class(level_id, year_id)
        student_id = self.make_student()
        enrollments_service.enroll(student_id, class_id, actor=self.actor)
        students_service.set_status(student_id, "منسحب", actor=self.actor)
        enrollments = enrollments_service.list_enrollments()
        self.assertEqual(enrollments[0]["status"], "منسحب")
        self.assertEqual(students_service.get_student(student_id)["status"], "منسحب")

    def test_invalid_status_rejected(self) -> None:
        student_id = self.make_student()
        with self.assertRaises(ValidationError):
            students_service.set_status(student_id, "حالة غير معروفة", actor=self.actor)

    def test_stats_counts_by_status(self) -> None:
        self.make_student("طالب أول")
        second = self.make_student("طالب ثانٍ")
        students_service.set_status(second, "موقوف", actor=self.actor)
        stats = students_service.stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats.get("منتظم"), 1)
        self.assertEqual(stats.get("موقوف"), 1)


class StudentQueryTests(DbTestCase):
    def test_search_and_filters(self) -> None:
        year_id = self.make_year()
        level_id = self.make_level()
        class_id = self.make_class(level_id, year_id)
        enrolled = self.make_student("سالم العتيبي")
        self.make_student("نورة الحربي")
        enrollments_service.enroll(enrolled, class_id, actor=self.actor)

        self.assertEqual(students_service.count_students(search="سالم"), 1)
        self.assertEqual(students_service.count_students(class_id=class_id), 1)
        self.assertEqual(students_service.count_students(status="منتظم", class_id=class_id), 1)
        self.assertEqual(students_service.count_students(search="لا يوجد"), 0)
        rows = students_service.list_students(class_id=class_id)
        self.assertEqual(rows[0]["student_no"], students_service.get_student(enrolled)["student_no"])

    def test_statuses_constant_used(self) -> None:
        self.assertIn("منتظم", config.STUDENT_STATUSES)


if __name__ == "__main__":
    unittest.main()
