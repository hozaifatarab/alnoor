"""اختبارات التسجيل الموحّد: حساب دخول + سجل شخص (طالب/معلّم) في معاملة واحدة."""
from __future__ import annotations

import unittest

from core import auth, config
from core.exceptions import DuplicateError, ValidationError
from core.repos import audit
from core.repos import students as students_repo
from core.repos import teachers as teachers_repo
from core.repos import users as users_repo
from core.services import people_service, teachers_service, users_service

from .base import DbTestCase

VALID_PASSWORD = "Learn#2026"


class RegisterStudentTests(DbTestCase):
    def _register(self, **extra: object) -> dict:
        payload = {
            "kind": "student",
            "full_name": "أحمد محمد العلي",
            "username": "ahmed.s",
            "password": VALID_PASSWORD,
            "actor": self.actor,
            "ip": "127.0.0.1",
        }
        payload.update(extra)
        return people_service.register_person(**payload)  # type: ignore[arg-type]

    def test_register_student_creates_user_and_student_atomically(self) -> None:
        result = self._register(gender="ذكر", guardian_phone="0555555555")
        self.assertEqual(result["kind"], "student")
        self.assertEqual(result["role"], config.ROLE_STUDENT)
        self.assertEqual(result["username"], "ahmed.s")

        user = users_service.get_user(result["user_id"])
        self.assertEqual(user["role"], config.ROLE_STUDENT)
        self.assertEqual(user["must_change_password"], 1)
        self.assertTrue(user["is_active"])

        student = students_repo.get(result["person_id"])
        self.assertIsNotNone(student)
        self.assertEqual(student["user_id"], result["user_id"])
        self.assertEqual(student["status"], "منتظم")
        self.assertTrue(student["student_no"])

    def test_student_can_login_with_created_credentials(self) -> None:
        result = self._register()
        logged = users_service.authenticate("ahmed.s", VALID_PASSWORD)
        self.assertEqual(logged["id"], result["user_id"])

    def test_student_role_lands_on_my_account(self) -> None:
        """الطالب لا يملك لوحة معلومات — شاشته الأولى هي حسابه."""
        user = {"id": 1, "username": "ahmed.s", "role": config.ROLE_STUDENT}
        self.assertEqual(auth.home_app_for(user), "my_account")
        self.assertTrue(config.can(config.ROLE_STUDENT, config.PERM_SELF))
        self.assertFalse(config.can(config.ROLE_STUDENT, config.PERM_DASHBOARD))

    def test_student_no_is_generated_when_missing(self) -> None:
        result = self._register()
        student = students_repo.get(result["person_id"])
        self.assertRegex(student["student_no"], r"^\d{4}-\d{4}$")

    def test_student_username_is_lowercased(self) -> None:
        result = self._register(username="Ahmed.S")
        self.assertEqual(result["username"], "ahmed.s")
        self.assertIsNotNone(users_repo.get_by_username("ahmed.s"))


class RegisterTeacherTests(DbTestCase):

    def test_register_teacher_creates_user_and_teacher_atomically(self) -> None:
        result = people_service.register_person(
            kind="teacher",
            full_name="خالد العتيبي",
            username="khaled.t",
            password=VALID_PASSWORD,
            phone="0555555555",
            specialty="رياضيات",
            actor=self.actor,
        )
        self.assertEqual(result["kind"], "teacher")
        self.assertEqual(result["role"], config.ROLE_TEACHER)

        user = users_service.get_user(result["user_id"])
        self.assertEqual(user["role"], config.ROLE_TEACHER)
        self.assertEqual(user["must_change_password"], 1)

        teacher = teachers_repo.get(result["person_id"])
        self.assertIsNotNone(teacher)
        self.assertEqual(teacher["user_id"], result["user_id"])
        self.assertEqual(teacher["specialty"], "رياضيات")

    def test_teacher_can_login_with_created_credentials(self) -> None:
        people_service.register_person(
            kind="teacher",
            full_name="خالد العتيبي",
            username="khaled.t",
            password=VALID_PASSWORD,
            actor=self.actor,
        )
        logged = users_service.authenticate("khaled.t", VALID_PASSWORD)
        self.assertEqual(logged["role"], config.ROLE_TEACHER)


class RegistrationValidationTests(DbTestCase):

    def _register(self, **extra: object) -> dict:
        payload = {
            "kind": "student",
            "full_name": "طالب جديد",
            "username": "new.user",
            "password": VALID_PASSWORD,
            "actor": self.actor,
        }
        payload.update(extra)
        return people_service.register_person(**payload)  # type: ignore[arg-type]

    def test_unknown_kind_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._register(kind="employee")
        self.assertEqual(users_service.stats()["total"], 0)

    def test_short_name_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._register(full_name="أ")
        self.assertEqual(users_service.stats()["total"], 0)

    def test_invalid_username_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._register(username="اسم عربي")
        with self.assertRaises(ValidationError):
            self._register(username="ab")  # أقصر من 3 أحرف
        self.assertEqual(users_service.stats()["total"], 0)

    def test_weak_password_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._register(password="12345678")  # بلا حرف
        with self.assertRaises(ValidationError):
            self._register(password="short1")  # أقصر من 8 أحرف
        self.assertEqual(users_service.stats()["total"], 0)

    def test_password_cannot_contain_username(self) -> None:
        with self.assertRaises(ValidationError):
            self._register(username="sara2026", password="sara2026x")
        self.assertEqual(users_service.stats()["total"], 0)

    def test_duplicate_username_rejected(self) -> None:
        self._register()
        users_before = users_service.stats()["total"]
        with self.assertRaises(DuplicateError):
            self._register(kind="teacher", username="NEW.USER", full_name="معلم آخر")
        # لم يُنشأ حساب ثانٍ (غير حسّاس لحالة الأحرف)
        self.assertEqual(users_service.stats()["total"], users_before)

    def test_audit_trail_written_on_success(self) -> None:
        people_service.register_person(
            kind="student",
            full_name="طالب مدقق",
            username="audit.s",
            password=VALID_PASSWORD,
            actor=self.actor,
            ip="10.0.0.1",
        )
        actions = [row["action"] for row in audit.recent(20)]
        self.assertTrue(any("حساب دخول" in action for action in actions))
        entry = next(row for row in audit.recent(20) if "حساب دخول" in row["action"])
        self.assertEqual(entry["username"], self.actor["username"])


class FormValidationTests(DbTestCase):
    """validate_registration تُعيد (حقل, رسالة) بدل رمي استثناء — ليبقى النموذج مفتوحاً."""

    def _data(self, **extra: object) -> dict:
        payload = {
            "kind": "student",
            "full_name": "سارة الحربي",
            "username": "sara.h",
            "password": VALID_PASSWORD,
            "password_confirm": VALID_PASSWORD,
        }
        payload.update(extra)
        return payload

    def test_valid_data_returns_none(self) -> None:
        self.assertIsNone(people_service.validate_registration(self._data()))

    def test_password_mismatch_maps_to_confirm_field(self) -> None:
        field, message = people_service.validate_registration(
            self._data(password_confirm="Different#1")
        )
        self.assertEqual(field, "password_confirm")
        self.assertIn("غير متطابقتين", message)

    def test_weak_password_maps_to_password_field(self) -> None:
        data = self._data(password="12345678", password_confirm="12345678")
        field, _message = people_service.validate_registration(data)
        self.assertEqual(field, "password")

    def test_bad_username_maps_to_username_field(self) -> None:
        field, _message = people_service.validate_registration(self._data(username="أحمد"))
        self.assertEqual(field, "username")

    def test_short_name_maps_to_full_name_field(self) -> None:
        field, _message = people_service.validate_registration(self._data(full_name="أ"))
        self.assertEqual(field, "full_name")

    def test_unknown_kind_maps_to_kind_field(self) -> None:
        field, _message = people_service.validate_registration(self._data(kind="visitor"))
        self.assertEqual(field, "kind")

    def test_duplicate_username_maps_to_username_field(self) -> None:
        people_service.register_person(
            kind="student",
            full_name="طالب أول",
            username="taken.name",
            password=VALID_PASSWORD,
            actor=self.actor,
        )
        field, message = people_service.validate_registration(
            self._data(username="TAKEN.NAME")  # غير حساس لحالة الأحرف
        )
        self.assertEqual(field, "username")
        self.assertIn("مستخدم مسبقاً", message)


class HomeAndNavTests(DbTestCase):
    def test_student_home_is_my_account(self) -> None:
        people_service.register_person(
            kind="student",
            full_name="طالب بوابة",
            username="portal.s",
            password=VALID_PASSWORD,
            actor=self.actor,
        )
        logged = users_service.authenticate("portal.s", VALID_PASSWORD)
        self.assertEqual(auth.home_app_for(logged), "my_account")

    def test_people_route_requires_users_permission(self) -> None:
        from app import ROUTES

        self.assertEqual(ROUTES["people"][1], config.PERM_USERS)

    def test_people_nav_visible_only_to_admin(self) -> None:
        from ui import layout

        admin_apps = {item[0] for item in layout.nav_items_for({"role": config.ROLE_ADMIN})}
        staff_apps = {item[0] for item in layout.nav_items_for({"role": config.ROLE_STAFF})}
        self.assertIn("people", admin_apps)
        self.assertNotIn("people", staff_apps)


class Migration0006Tests(DbTestCase):
    def test_student_role_allowed_and_links_preserved(self) -> None:
        """هجرة 0006: قيد CHECK يقبل «طالب» وروابط الأبناء محفوظة بعد إعادة البناء."""
        from core import db

        admin = self.admin_user()
        teacher_id = self.make_teacher("معلم مرتبط")
        teachers_service.link_account(teacher_id, admin, actor=self.actor)

        # إعادة تطبيق الهجرة على قاعدة قائمة (كما يحدث عند ترقية نسخة قديمة):
        # يجب ألا تتكرر وألا تُمس الروابط.
        self.assertEqual(db.init_db(), [], "لا يجب تطبيق الهجرات مرتين")

        teacher = teachers_repo.get(teacher_id)
        self.assertEqual(teacher["user_id"], admin)

        uid = users_service.create_user(
            "student.one", "طالب جديد", config.ROLE_STUDENT, "Pass#2026", actor=self.actor
        )
        self.assertEqual(users_service.get_user(uid)["role"], config.ROLE_STUDENT)


if __name__ == "__main__":
    unittest.main()