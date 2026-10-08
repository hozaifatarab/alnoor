"""اختبارات التحقق من المدخلات (قيم صحيحة + قيم حدية + قيم شاذة)."""
from __future__ import annotations

import unittest

from core import validators as v
from core.exceptions import ValidationError

from .base import DbTestCase


class TextValidationTests(DbTestCase):
    def test_normalize_arabic_digits(self) -> None:
        self.assertEqual(v.normalize_digits("١٢٣٤"), "1234")

    def test_require_text_trims_and_collapses(self) -> None:
        self.assertEqual(v.require_text("  أحمد   محمد  ", "الاسم"), "أحمد محمد")

    def test_require_text_rejects_empty(self) -> None:
        with self.assertRaises(ValidationError):
            v.require_text("   ", "الاسم")

    def test_require_text_rejects_too_long(self) -> None:
        with self.assertRaises(ValidationError):
            v.require_text("ا" * 200, "الاسم", max_len=80)

    def test_optional_text(self) -> None:
        self.assertIsNone(v.optional_text("   "))
        self.assertEqual(v.optional_text(" ملاحظة "), "ملاحظة")

    def test_require_choice(self) -> None:
        self.assertEqual(v.require_choice("منتظم", "الحالة", ("منتظم", "منسحب")), "منتظم")
        with self.assertRaises(ValidationError):
            v.require_choice("غير معروف", "الحالة", ("منتظم", "منسحب"))


class NumberValidationTests(DbTestCase):
    def test_parse_int_bounds(self) -> None:
        self.assertEqual(v.parse_int("25", "السعة", minimum=1, maximum=200), 25)
        with self.assertRaises(ValidationError):
            v.parse_int("0", "السعة", minimum=1)
        with self.assertRaises(ValidationError):
            v.parse_int("abc", "السعة")
        self.assertEqual(v.parse_int("", "السعة", default=30), 30)

    def test_parse_money(self) -> None:
        self.assertEqual(v.parse_money("1,250.75", "المبلغ"), 1250.75)
        self.assertEqual(v.parse_money("", "المبلغ"), 0.0)
        with self.assertRaises(ValidationError):
            v.parse_money("-5", "المبلغ")

    def test_parse_float_range(self) -> None:
        self.assertEqual(v.parse_float("4.5", "الساعات", minimum=0, maximum=40), 4.5)
        with self.assertRaises(ValidationError):
            v.parse_float("50", "الساعات", maximum=40)


class DateValidationTests(DbTestCase):
    def test_parse_date_formats(self) -> None:
        self.assertEqual(v.parse_date("2026-09-01", "التاريخ"), "2026-09-01")
        self.assertEqual(v.parse_date("01/09/2026", "التاريخ"), "2026-09-01")
        self.assertIsNone(v.parse_date("", "التاريخ", required=False))

    def test_parse_date_invalid(self) -> None:
        with self.assertRaises(ValidationError):
            v.parse_date("32/13/2026", "التاريخ")

    def test_parse_time(self) -> None:
        self.assertEqual(v.parse_time("07:30", "الوقت"), "07:30")
        self.assertEqual(v.parse_time("", "الوقت", default="08:00"), "08:00")
        with self.assertRaises(ValidationError):
            v.parse_time("25:00", "الوقت")

    def test_parse_holidays(self) -> None:
        self.assertEqual(v.parse_holidays("2026-09-05, 2026-09-05 ,2026-10-01"),
                         ["2026-09-05", "2026-10-01"])
        with self.assertRaises(ValidationError):
            v.parse_holidays("ليس تاريخاً")


class IdentityValidationTests(DbTestCase):
    def test_national_id(self) -> None:
        self.assertEqual(v.validate_national_id("1234567890"), "1234567890")
        self.assertIsNone(v.validate_national_id(""))
        for bad in ("123", "abc1234567", "123456789012345"):
            with self.assertRaises(ValidationError):
                v.validate_national_id(bad)

    def test_phone(self) -> None:
        self.assertEqual(v.validate_phone("+966 55-555 5555"), "966555555555")
        self.assertEqual(v.validate_phone("0555555555"), "0555555555")
        with self.assertRaises(ValidationError):
            v.validate_phone("12")

    def test_email(self) -> None:
        self.assertEqual(v.validate_email("User@Example.COM"), "user@example.com")
        self.assertIsNone(v.validate_email(""))
        with self.assertRaises(ValidationError):
            v.validate_email("not-an-email")


if __name__ == "__main__":
    unittest.main()
