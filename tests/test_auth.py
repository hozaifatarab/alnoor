"""اختبارات المصادقة وسياسات الحسابات والصلاحيات."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core import auth, config
from core.exceptions import AuthError, LockedError
from core.repos import audit
from core.services import users_service

from .base import DbTestCase


class AuthenticateTests(DbTestCase):
    def test_successful_login(self) -> None:
        user_id = self.admin_user()
        user = users_service.authenticate("admin", "Manager#2026", ip="127.0.0.1")
        self.assertEqual(user["id"], user_id)
        self.assertIsNotNone(user["last_login"])
        self.assertEqual(user["failed_attempts"], 0)

    def test_username_is_case_insensitive(self) -> None:
        self.admin_user()
        self.assertEqual(users_service.authenticate("ADMIN", "Manager#2026")["username"], "admin")

    def test_wrong_password_raises_auth_error(self) -> None:
        self.admin_user()
        with self.assertRaises(AuthError):
            users_service.authenticate("admin", "Wrong@1234")

    def test_unknown_user_raises_auth_error(self) -> None:
        with self.assertRaises(AuthError):
            users_service.authenticate("nobody", "Manager#2026")

    def test_lock_after_max_attempts(self) -> None:
        self.admin_user()
        for _ in range(config.MAX_LOGIN_ATTEMPTS - 1):
            with self.assertRaises(AuthError):
                users_service.authenticate("admin", "Wrong@1234")
        with self.assertRaises(LockedError):
            users_service.authenticate("admin", "Wrong@1234")
        # كلمة المرور الصحيحة مرفوضة أيضاً أثناء القفل
        with self.assertRaises(LockedError):
            users_service.authenticate("admin", "Manager#2026")

    def test_inactive_user_rejected(self) -> None:
        self.admin_user()
        operator = self.admin_user("operator", "Desk#2026")
        users_service.update_user(operator, "مشرف", "staff", False, actor=self.actor)
        with self.assertRaises(AuthError):
            users_service.authenticate("operator", "Desk#2026")

    def test_failed_attempts_are_audited(self) -> None:
        self.admin_user()
        with self.assertRaises(AuthError):
            users_service.authenticate("admin", "Wrong@1234")
        self.assertTrue(any(row["action"] == "فشل تسجيل دخول" for row in audit.recent(20)))


class CredentialCleaningTests(DbTestCase):
    """تطهير بيانات الدخول من المسافات والأحرف الخفية والأرقام العربية."""

    def test_clean_strips_invisible_and_spaces(self) -> None:
        cleaned, had_hidden, had_arabic = auth._clean_credential("  \u200fManager#2026\u200e\u00a0 ")
        self.assertEqual(cleaned, "Manager#2026")
        self.assertTrue(had_hidden)
        self.assertFalse(had_arabic)

    def test_clean_converts_arabic_indic_digits(self) -> None:
        cleaned, _, had_arabic = auth._clean_credential("Desk\u0662\u0660\u0662\u0666")
        self.assertEqual(cleaned, "Desk2026")
        self.assertTrue(had_arabic)
        cleaned_fa, _, _ = auth._clean_credential("Pass\u06f1\u06f2")
        self.assertEqual(cleaned_fa, "Pass12")

    def test_login_applies_cleaning_before_authenticate(self) -> None:
        """auth.login يطبّق التطهير قبل التحقق (لصق فيه علامات RTL)."""
        self.admin_user()
        with patch("core.auth.users_service.authenticate") as mock_auth, patch(
            "core.auth._write_auth_cookie"
        ), patch("core.auth._session_local"):
            mock_auth.return_value = {
                "id": 1,
                "username": "admin",
                "password_hash": "x",
                "password_salt": "y",
            }
            auth.login(" admin\u200f ", "\u200eManager#2026")
        mock_auth.assert_called_once_with("admin", "Manager#2026", ip=mock_auth.call_args.kwargs["ip"])


class SessionTokenTests(DbTestCase):
    def test_current_user_restores_signed_cookie_in_new_session(self) -> None:
        user_id = self.admin_user()
        user = users_service.get_user(user_id)
        token = auth._make_session_token(user)
        local = type("SessionLocal", (), {"user_id": None, "username": None})()

        with patch.object(auth, "_session_local", return_value=local), patch.object(
            auth, "_request_auth_cookie", return_value=token
        ):
            restored = auth.current_user()

        self.assertEqual(restored["id"], user_id)
        self.assertEqual(local.user_id, user_id)

    def test_password_change_invalidates_existing_session_token(self) -> None:
        user_id = self.admin_user()
        token = auth._make_session_token(users_service.get_user(user_id))

        users_service.change_password(user_id, "NewPass#2026")

        self.assertIsNone(auth._user_from_session_token(token))


class UserManagementTests(DbTestCase):
    def test_create_user_validations(self) -> None:
        from core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            users_service.create_user("ab", "اسم", "staff", "Valid@1234", actor=self.actor)
        with self.assertRaises(ValidationError):
            users_service.create_user("bad name", "اسم كامل", "staff", "Valid@1234", actor=self.actor)
        with self.assertRaises(ValidationError):
            users_service.create_user("user1", "اسم كامل", "wrong-role", "Valid@1234", actor=self.actor)
        with self.assertRaises(ValidationError):
            users_service.create_user("user1", "اسم كامل", "staff", "weakpass", actor=self.actor)

    def test_duplicate_username_rejected(self) -> None:
        from core.exceptions import DuplicateError

        self.admin_user()
        with self.assertRaises(DuplicateError):
            self.admin_user()

    def test_new_user_must_change_password(self) -> None:
        self.admin_user()
        uid = users_service.create_user("staff1", "موظف", "staff", "Staff@1234", actor=self.actor)
        self.assertEqual(users_service.get_user(uid)["must_change_password"], 1)

    def test_last_admin_protection(self) -> None:
        from core.exceptions import BusinessRuleError

        admin_id = self.admin_user()
        with self.assertRaises(BusinessRuleError):
            users_service.update_user(admin_id, "المدير", "staff", True, actor=self.actor)
        with self.assertRaises(BusinessRuleError):
            users_service.update_user(admin_id, "المدير", "admin", False, actor=self.actor)
        with self.assertRaises(BusinessRuleError):
            users_service.delete_user(admin_id, actor=self.actor)

    def test_second_admin_allows_demotion(self) -> None:
        first = self.admin_user()
        self.admin_user("admin2", "Manager#2222")
        users_service.update_user(first, "المدير الأول", "staff", True, actor=self.actor)
        self.assertEqual(users_service.get_user(first)["role"], "staff")

    def test_cannot_delete_self(self) -> None:
        from core.exceptions import BusinessRuleError

        admin_id = self.admin_user()
        second = self.admin_user("admin2", "Manager#2222")
        actor = {"id": second, "username": "admin2", "role": "admin"}
        with self.assertRaises(BusinessRuleError):
            users_service.delete_user(second, actor=actor)
        users_service.delete_user(admin_id, actor=actor)

    def test_change_own_password_requires_current(self) -> None:
        admin_id = self.admin_user()
        with self.assertRaises(AuthError):
            users_service.change_own_password(admin_id, "WrongOld@1", "NewPass@123")
        users_service.change_own_password(admin_id, "Manager#2026", "NewPass@123")
        self.assertTrue(users_service.verify_own_password(admin_id, "NewPass@123"))

    def test_password_change_clears_lock(self) -> None:
        admin_id = self.admin_user()
        for _ in range(config.MAX_LOGIN_ATTEMPTS):
            with self.assertRaises((AuthError, LockedError)):
                users_service.authenticate("admin", "Wrong@1234")
        users_service.change_password(admin_id, "Reset@1234", actor=self.actor)
        self.assertEqual(users_service.authenticate("admin", "Reset@1234")["id"], admin_id)


class PermissionMatrixTests(DbTestCase):
    def test_role_permissions(self) -> None:
        self.assertTrue(config.can(config.ROLE_ADMIN, config.PERM_USERS))
        self.assertFalse(config.can(config.ROLE_TEACHER, config.PERM_USERS))
        self.assertTrue(config.can(config.ROLE_STAFF, config.PERM_STUDENTS))
        self.assertFalse(config.can(config.ROLE_STAFF, config.PERM_FINANCE))
        self.assertTrue(config.can(config.ROLE_ACCOUNTANT, config.PERM_FINANCE))
        self.assertFalse(config.can(None, config.PERM_DASHBOARD))
        self.assertEqual(len(config.PERMISSION_MATRIX[config.ROLE_ADMIN]), len(config.ALL_PERMISSIONS))
        self.assertFalse(config.can(config.ROLE_VIEWER, config.PERM_SETTINGS))


if __name__ == "__main__":
    unittest.main()
