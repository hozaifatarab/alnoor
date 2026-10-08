"""اختبارات المعلمين والإسناد التدريسي."""
from __future__ import annotations

import unittest

from core.exceptions import BusinessRuleError, DuplicateError, NotFoundError, ValidationError
from core.services import subjects_service, teachers_service

from .base import DbTestCase


class TeacherTests(DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.year_id = self.make_year()
        self.level_id = self.make_level()
        self.class_id = self.make_class(self.level_id, self.year_id)

    def test_create_teacher_and_stats(self) -> None:
        self.make_teacher("خالد العلي")
        stats = teachers_service.stats()
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["active"], 1)

    def test_invalid_email_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            teachers_service.create_teacher(
                "معلم جديد", None, "0555555555", "not-an-email", None, None, 0, actor=self.actor
            )

    def test_invalid_salary_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            teachers_service.create_teacher(
                "معلم جديد", None, None, None, None, None, -50, actor=self.actor
            )

    def test_short_name_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            teachers_service.create_teacher("أ", None, None, None, None, None, 0, actor=self.actor)

    def test_update_teacher(self) -> None:
        teacher_id = self.make_teacher()
        teachers_service.update_teacher(
            teacher_id, "خالد العلي المطيري", None, "0555555555", None, None, "فيزياء", 6000, True,
            actor=self.actor,
        )
        teacher = teachers_service.get_teacher(teacher_id)
        self.assertEqual(teacher["specialty"], "فيزياء")
        self.assertEqual(teacher["full_name"], "خالد العلي المطيري")

    def test_missing_teacher_raises_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            teachers_service.get_teacher(55)

    def test_link_account_conflict(self) -> None:
        first = self.make_teacher("معلم أول")
        second = self.make_teacher("معلم ثانٍ")
        user_id = self.admin_user()
        teachers_service.link_account(first, user_id, actor=self.actor)
        with self.assertRaises(DuplicateError):
            teachers_service.link_account(second, user_id, actor=self.actor)


class AssignmentTests(DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.year_id = self.make_year()
        self.level_id = self.make_level()
        self.class_id = self.make_class(self.level_id, self.year_id)
        self.subject_id = self.make_subject("رياضيات", self.level_id)
        self.teacher_id = self.make_teacher()

    def test_create_assignment(self) -> None:
        assignment_id = teachers_service.create_assignment(
            self.teacher_id, self.subject_id, self.class_id, actor=self.actor
        )
        rows = teachers_service.list_assignments()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], assignment_id)
        self.assertEqual(rows[0]["teacher_name"], "خالد العلي")

    def test_duplicate_assignment_rejected(self) -> None:
        teachers_service.create_assignment(
            self.teacher_id, self.subject_id, self.class_id, actor=self.actor
        )
        with self.assertRaises(DuplicateError):
            teachers_service.create_assignment(
                self.teacher_id, self.subject_id, self.class_id, actor=self.actor
            )

    def test_assignment_with_missing_entities(self) -> None:
        with self.assertRaises(NotFoundError):
            teachers_service.create_assignment(999, self.subject_id, self.class_id, actor=self.actor)
        with self.assertRaises(NotFoundError):
            teachers_service.create_assignment(self.teacher_id, 999, self.class_id, actor=self.actor)

    def test_teacher_with_assignment_cannot_be_deleted(self) -> None:
        teachers_service.create_assignment(
            self.teacher_id, self.subject_id, self.class_id, actor=self.actor
        )
        with self.assertRaises(BusinessRuleError):
            teachers_service.delete_teacher(self.teacher_id, actor=self.actor)

    def test_delete_assignment_then_teacher(self) -> None:
        assignment_id = teachers_service.create_assignment(
            self.teacher_id, self.subject_id, self.class_id, actor=self.actor
        )
        teachers_service.delete_assignment(assignment_id, actor=self.actor)
        self.assertEqual(teachers_service.list_assignments(), [])
        teachers_service.delete_teacher(self.teacher_id, actor=self.actor)
        self.assertEqual(teachers_service.list_teachers(), [])

    def test_missing_assignment_delete(self) -> None:
        with self.assertRaises(NotFoundError):
            teachers_service.delete_assignment(777, actor=self.actor)

    def test_subject_options_only_active(self) -> None:
        inactive = subjects_service.create_subject("مادة موقوفة", None, None, 2, 50, actor=self.actor)
        subjects_service.update_subject(
            inactive, "مادة موقوفة", None, None, 2, 50, False, actor=self.actor
        )
        names = [row["name"] for row in subjects_service.options()]
        self.assertIn("رياضيات", names)
        self.assertNotIn("مادة موقوفة", names)


if __name__ == "__main__":
    unittest.main()
