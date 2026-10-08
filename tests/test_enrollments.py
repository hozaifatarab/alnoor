"""اختبارات التسجيل: السعة، التكرار، النقل، الحالات، وإعادة التنشيط."""
from __future__ import annotations

import unittest

from core.exceptions import (
    BusinessRuleError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)
from core.services import classes_service, enrollments_service, terms_service, years_service

from .base import DbTestCase


class EnrollTests(DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.year_id = self.make_year()
        self.level_id = self.make_level()
        self.class_id = self.make_class(self.level_id, self.year_id, capacity=2)

    def test_enroll_success(self) -> None:
        student_id = self.make_student()
        enrollment_id = enrollments_service.enroll(student_id, self.class_id, actor=self.actor)
        roster = classes_service.roster(self.class_id)
        self.assertEqual(len(roster), 1)
        self.assertEqual(classes_service.capacity_info(self.class_id)["available"], 1)
        self.assertEqual(enrollments_service.get_enrollment(enrollment_id)["status"], "مسجّل")

    def test_duplicate_active_enrollment_rejected(self) -> None:
        student_id = self.make_student()
        enrollments_service.enroll(student_id, self.class_id, actor=self.actor)
        with self.assertRaises(DuplicateError):
            enrollments_service.enroll(student_id, self.class_id, actor=self.actor)

    def test_capacity_limit_enforced(self) -> None:
        enrollments_service.enroll(self.make_student("طالب 1"), self.class_id, actor=self.actor)
        enrollments_service.enroll(self.make_student("طالب 2"), self.class_id, actor=self.actor)
        with self.assertRaises(BusinessRuleError):
            enrollments_service.enroll(self.make_student("طالب 3"), self.class_id, actor=self.actor)

    def test_non_active_student_rejected(self) -> None:
        student_id = self.make_student("طالب موقوف", status="موقوف")
        with self.assertRaises(BusinessRuleError):
            enrollments_service.enroll(student_id, self.class_id, actor=self.actor)

    def test_year_mismatch_rejected(self) -> None:
        other_year = years_service.create_year("2027/2028", None, None, False, actor=self.actor)
        student_id = self.make_student()
        with self.assertRaises(ValidationError):
            enrollments_service.enroll(student_id, self.class_id, year_id=other_year, actor=self.actor)

    def test_term_from_other_year_rejected(self) -> None:
        other_year = years_service.create_year("2027/2028", None, None, False, actor=self.actor)
        other_term = terms_service.create_term(other_year, "فصل آخر", None, None, False, actor=self.actor)
        student_id = self.make_student()
        with self.assertRaises(BusinessRuleError):
            enrollments_service.enroll(student_id, self.class_id, term_id=other_term, actor=self.actor)

    def test_default_term_is_current_year_term(self) -> None:
        term_id = self.make_term(self.year_id, "الفصل الأول")
        student_id = self.make_student()
        enrollment_id = enrollments_service.enroll(student_id, self.class_id, actor=self.actor)
        self.assertEqual(enrollments_service.get_enrollment(enrollment_id)["term_id"], term_id)

    def test_missing_student_and_class(self) -> None:
        with self.assertRaises(NotFoundError):
            enrollments_service.enroll(999, self.class_id, actor=self.actor)
        with self.assertRaises(NotFoundError):
            classes_service.get_class(999)


class TransferAndWithdrawTests(DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.year_id = self.make_year()
        self.level_id = self.make_level()
        self.class_a = self.make_class(self.level_id, self.year_id, "أ", capacity=1)
        self.class_b = self.make_class(self.level_id, self.year_id, "ب", capacity=2)

    def test_change_class(self) -> None:
        enrollment_id = enrollments_service.enroll(
            self.make_student(), self.class_a, actor=self.actor
        )
        enrollments_service.change_class(enrollment_id, self.class_b, actor=self.actor)
        self.assertEqual(enrollments_service.get_enrollment(enrollment_id)["class_id"], self.class_b)
        self.assertEqual(len(classes_service.roster(self.class_b)), 1)

    def test_change_to_same_class_rejected(self) -> None:
        enrollment_id = enrollments_service.enroll(
            self.make_student(), self.class_a, actor=self.actor
        )
        with self.assertRaises(BusinessRuleError):
            enrollments_service.change_class(enrollment_id, self.class_a, actor=self.actor)

    def test_change_to_full_class_rejected(self) -> None:
        enrollments_service.enroll(self.make_student("طالب أول"), self.class_b, actor=self.actor)
        enrollments_service.enroll(self.make_student("طالب ثانٍ"), self.class_b, actor=self.actor)
        other = enrollments_service.enroll(self.make_student("طالب ثالث"), self.class_a, actor=self.actor)
        with self.assertRaises(BusinessRuleError):
            enrollments_service.change_class(other, self.class_b, actor=self.actor)
        self.assertEqual(enrollments_service.get_enrollment(other)["class_id"], self.class_a)

    def test_withdraw_then_reactivate_reuses_record(self) -> None:
        student_id = self.make_student()
        first = enrollments_service.enroll(student_id, self.class_a, actor=self.actor)
        enrollments_service.withdraw(first, actor=self.actor)
        self.assertEqual(enrollments_service.get_enrollment(first)["status"], "منسحب")

        again = enrollments_service.enroll(student_id, self.class_b, actor=self.actor)
        self.assertEqual(again, first, "يجب إعادة تنشيط نفس السجل بدل إنشاء سجل جديد")
        record = enrollments_service.get_enrollment(first)
        self.assertEqual((record["status"], record["class_id"]), ("مسجّل", self.class_b))
        self.assertEqual(len(enrollments_service.list_enrollments()), 1)

    def test_withdraw_twice_rejected(self) -> None:
        enrollment_id = enrollments_service.enroll(
            self.make_student(), self.class_a, actor=self.actor
        )
        enrollments_service.withdraw(enrollment_id, actor=self.actor)
        with self.assertRaises(BusinessRuleError):
            enrollments_service.withdraw(enrollment_id, actor=self.actor)

    def test_discount_validation_and_update(self) -> None:
        enrollment_id = enrollments_service.enroll(
            self.make_student(), self.class_a, actor=self.actor
        )
        enrollments_service.set_discount(enrollment_id, 150.5, actor=self.actor)
        self.assertEqual(enrollments_service.get_enrollment(enrollment_id)["discount"], 150.5)
        with self.assertRaises(ValidationError):
            enrollments_service.set_discount(enrollment_id, -10, actor=self.actor)

    def test_student_history(self) -> None:
        student_id = self.make_student()
        enrollments_service.enroll(student_id, self.class_a, actor=self.actor)
        history = enrollments_service.student_history(student_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["class_name"], "أ")

    def test_delete_enrollment(self) -> None:
        enrollment_id = enrollments_service.enroll(
            self.make_student(), self.class_a, actor=self.actor
        )
        enrollments_service.delete_enrollment(enrollment_id, actor=self.actor)
        self.assertEqual(enrollments_service.list_enrollments(), [])


if __name__ == "__main__":
    unittest.main()
