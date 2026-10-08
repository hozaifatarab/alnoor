"""اختبارات البنية الأكاديمية: السنوات، الفصول الدراسية، المراحل، الفصول، المواد."""
from __future__ import annotations

import unittest

from core.exceptions import BusinessRuleError, DuplicateError, NotFoundError, ValidationError
from core.repos import settings as settings_repo
from core.services import levels_service, terms_service, years_service

from .base import DbTestCase


class YearTests(DbTestCase):
    def test_create_current_year_syncs_settings(self) -> None:
        year_id = self.make_year("2026/2027", make_current=True)
        self.assertTrue(years_service.get_year(year_id)["is_current"])
        self.assertEqual(settings_repo.current_year_id(), year_id)

    def test_only_one_current_year(self) -> None:
        first = self.make_year("2025/2026")
        second = self.make_year("2026/2027")
        self.assertEqual(years_service.get_year(first)["is_current"], 0)
        self.assertEqual(years_service.get_year(second)["is_current"], 1)
        self.assertEqual(years_service.current_year()["id"], second)

    def test_invalid_date_range(self) -> None:
        with self.assertRaises(ValidationError):
            years_service.create_year("2026/2027", "2027-06-30", "2026-09-01", True, actor=self.actor)

    def test_duplicate_year_name(self) -> None:
        self.make_year("2026/2027")
        with self.assertRaises(DuplicateError):
            self.make_year("2026/2027")

    def test_delete_year_with_data_blocked(self) -> None:
        year_id = self.make_year()
        level_id = self.make_level()
        self.make_class(level_id, year_id)
        with self.assertRaises(BusinessRuleError):
            years_service.delete_year(year_id, actor=self.actor)

    def test_missing_year_raises_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            years_service.get_year(12345)


class TermTests(DbTestCase):
    def test_current_term_syncs_settings(self) -> None:
        year_id = self.make_year()
        term_id = self.make_term(year_id)
        self.assertTrue(terms_service.get_term(term_id)["is_current"])
        self.assertEqual(settings_repo.current_term_id(), term_id)

    def test_term_dates_outside_year_rejected(self) -> None:
        year_id = self.make_year()
        with self.assertRaises(ValidationError):
            terms_service.create_term(
                year_id, "الفصل الصيفي", "2028-01-01", "2028-02-01", False, actor=self.actor
            )

    def test_only_one_current_term_per_year(self) -> None:
        year_id = self.make_year()
        first = self.make_term(year_id, "الفصل الأول")
        second = self.make_term(year_id, "الفصل الثاني")
        self.assertEqual(terms_service.get_term(first)["is_current"], 0)
        self.assertEqual(terms_service.get_term(second)["is_current"], 1)


class LevelTests(DbTestCase):
    def test_level_delete_blocked_when_has_classes(self) -> None:
        year_id = self.make_year()
        level_id = self.make_level()
        self.make_class(level_id, year_id)
        with self.assertRaises(BusinessRuleError):
            levels_service.delete_level(level_id, actor=self.actor)

class ClassTests(DbTestCase):
    def test_capacity_must_be_positive(self) -> None:
        year_id = self.make_year()
        level_id = self.make_level()
        with self.assertRaises(ValidationError):
            self.make_class(level_id, year_id, capacity=0)

    def test_duplicate_class_name_in_year(self) -> None:
        year_id = self.make_year()
        level_id = self.make_level()
        self.make_class(level_id, year_id, "أ")
        with self.assertRaises(DuplicateError):
            self.make_class(level_id, year_id, "أ")

    def test_capacity_shrink_below_enrolled_blocked(self) -> None:
        from core.services import classes_service, enrollments_service

        year_id = self.make_year()
        level_id = self.make_level()
        class_id = self.make_class(level_id, year_id, capacity=3)
        enrollments_service.enroll(self.make_student("طالب أول"), class_id, actor=self.actor)
        enrollments_service.enroll(self.make_student("طالب ثانٍ"), class_id, actor=self.actor)
        with self.assertRaises(BusinessRuleError):
            classes_service.update_class(
                class_id, "أ", level_id, year_id, 1, None, None, actor=self.actor
            )

    def test_delete_class_with_students_blocked(self) -> None:
        from core.services import classes_service, enrollments_service

        year_id = self.make_year()
        level_id = self.make_level()
        class_id = self.make_class(level_id, year_id)
        enrollments_service.enroll(self.make_student(), class_id, actor=self.actor)
        with self.assertRaises(BusinessRuleError):
            classes_service.delete_class(class_id, actor=self.actor)

    def test_capacity_info(self) -> None:
        from core.services import classes_service, enrollments_service

        year_id = self.make_year()
        level_id = self.make_level()
        class_id = self.make_class(level_id, year_id, capacity=2)
        self.assertEqual(classes_service.capacity_info(class_id)["available"], 2)
        enrollments_service.enroll(self.make_student("طالب"), class_id, actor=self.actor)
        info = classes_service.capacity_info(class_id)
        self.assertEqual((info["enrolled"], info["available"]), (1, 1))

    def test_roster_returns_enrolled_students(self) -> None:
        from core.services import classes_service, enrollments_service

        year_id = self.make_year()
        level_id = self.make_level()
        class_id = self.make_class(level_id, year_id)
        enrollments_service.enroll(self.make_student("سالم"), class_id, actor=self.actor)
        roster = classes_service.roster(class_id)
        self.assertEqual(len(roster), 1)
        self.assertEqual(roster[0]["full_name"], "سالم")


class SubjectTests(DbTestCase):
    def test_create_and_validate_subject(self) -> None:
        from core.services import subjects_service

        level_id = self.make_level()
        subject_id = self.make_subject("لغتي", level_id)
        self.assertEqual(subjects_service.get_subject(subject_id)["max_score"], 100)
        with self.assertRaises(ValidationError):
            subjects_service.create_subject("مادة", None, None, 4, 0, actor=self.actor)

    def test_subject_used_in_assignment_cannot_be_deleted(self) -> None:
        from core.services import subjects_service, teachers_service

        year_id = self.make_year()
        level_id = self.make_level()
        class_id = self.make_class(level_id, year_id)
        subject_id = self.make_subject("علوم", level_id)
        teacher_id = self.make_teacher()
        teachers_service.create_assignment(teacher_id, subject_id, class_id, actor=self.actor)
        with self.assertRaises(BusinessRuleError):
            subjects_service.delete_subject(subject_id, actor=self.actor)


if __name__ == "__main__":
    unittest.main()
