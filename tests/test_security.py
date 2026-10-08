"""اختبارات الأمان: تشفير كلمات المرور، السياسة، التوقيع."""
from __future__ import annotations

import unittest

from core import security
from core.exceptions import ValidationError

from .base import DbTestCase


class PasswordTests(DbTestCase):
    def test_hash_and_verify(self) -> None:
        password_hash, salt = security.hash_password("Str0ngPass")
        self.assertTrue(security.verify_password("Str0ngPass", password_hash, salt))
        self.assertFalse(security.verify_password("WrongPass1", password_hash, salt))

    def test_salt_is_random_per_user(self) -> None:
        first_hash, first_salt = security.hash_password("SamePass123")
        second_hash, second_salt = security.hash_password("SamePass123")
        self.assertNotEqual(first_salt, second_salt)
        self.assertNotEqual(first_hash, second_hash)

    def test_tampered_hash_rejected(self) -> None:
        password_hash, salt = security.hash_password("Str0ngPass")
        self.assertFalse(security.verify_password("Str0ngPass", password_hash[:-2] + "00", salt))

    def test_invalid_salt_returns_false(self) -> None:
        password_hash, _salt = security.hash_password("Str0ngPass")
        self.assertFalse(security.verify_password("Str0ngPass", password_hash, "zzzz"))

    def test_password_policy(self) -> None:
        with self.assertRaises(ValidationError):
            security.validate_password_policy("short1")
        with self.assertRaises(ValidationError):
            security.validate_password_policy("onlylettershere")
        with self.assertRaises(ValidationError):
            security.validate_password_policy("1234567890")
        with self.assertRaises(ValidationError):
            security.validate_password_policy("Admin@1234", username="admin")
        security.validate_password_policy("Valid@1234", username="admin")


class SigningTests(DbTestCase):
    def test_hmac_sign_verify(self) -> None:
        secret = security.new_secret(16)
        signature = security.hmac_sign("STD|2026|0001", secret)
        self.assertTrue(security.hmac_verify("STD|2026|0001", signature, secret))
        self.assertFalse(security.hmac_verify("STD|2026|0002", signature, secret))
        self.assertFalse(security.hmac_verify("STD|2026|0001", signature, security.new_secret(16)))

    def test_signature_length(self) -> None:
        secret = security.new_secret(16)
        self.assertEqual(len(security.hmac_sign("payload", secret, 10)), 10)
        self.assertEqual(len(security.hmac_sign("payload", secret, 16)), 16)


if __name__ == "__main__":
    unittest.main()
