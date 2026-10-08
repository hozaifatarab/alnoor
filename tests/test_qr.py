"""اختبارات محرك QR: التوليد، التحقق من التوقيع، وتزوير الحمولة."""
from __future__ import annotations

import unittest

from core import qr
from core.exceptions import ValidationError
from tests.base import DbTestCase


class QrEngineTests(DbTestCase):
    def test_make_and_verify_valid_payload(self) -> None:
        payload = qr.make_payload("STD-1001", "2026")
        self.assertTrue(payload.startswith("STD|2026|STD-1001|"))
        self.assertEqual(len(payload.rsplit("|", 1)[1]), qr.SIGNATURE_LENGTH)
        is_valid, student_no, reason = qr.verify_payload(payload)
        self.assertTrue(is_valid)
        self.assertEqual(student_no, "STD-1001")

    def test_legacy_short_signature_is_rejected(self) -> None:
        from core import security

        base = "STD|2026|STD-1001"
        signature = security.hmac_sign(base, qr.get_qr_secret(), length=10)

        is_valid, student_no, _reason = qr.verify_payload(f"{base}|{signature}")

        self.assertFalse(is_valid)
        self.assertEqual(student_no, "STD-1001")

    def test_tampered_payload_rejected(self) -> None:
        payload = qr.make_payload("STD-1001", "2026")
        tampered = payload[:-2] + "XX"
        is_valid, student_no, reason = qr.verify_payload(tampered)
        self.assertFalse(is_valid)
        self.assertIn("غير صالح", reason)

    def test_plain_student_number_accepted_for_usb_scanner(self) -> None:
        is_valid, student_no, reason = qr.verify_payload(
            "STD-2026-0001", allow_unsigned_student_no=True
        )
        self.assertTrue(is_valid)
        self.assertEqual(student_no, "STD-2026-0001")
        self.assertIn("مباشر", reason)

    def test_plain_student_number_rejected_as_camera_qr(self) -> None:
        is_valid, student_no, _reason = qr.verify_payload("STD-2026-0001")

        self.assertFalse(is_valid)
        self.assertEqual(student_no, "")

    def test_empty_or_invalid_payload(self) -> None:
        is_valid, _, _ = qr.verify_payload("")
        self.assertFalse(is_valid)
        is_valid, _, _ = qr.verify_payload("a")
        self.assertFalse(is_valid)

    def test_generate_svg_and_png(self) -> None:
        payload = qr.make_payload("STD-9999", "2026")
        svg = qr.generate_qr_svg(payload)
        self.assertIn("<svg", svg)
        png_bytes = qr.generate_qr_png_bytes(payload)
        self.assertTrue(len(png_bytes) > 50)
        self.assertEqual(png_bytes[:8], b"\x89PNG\r\n\x1a\n")

    def test_badge_html_escapes_user_content(self) -> None:
        badge = qr.generate_student_badge_html(
            {
                "student_no": "STD-1001",
                "full_name": "<img src=x onerror=alert(1)>",
                "status": "<script>alert(1)</script>",
            },
            "<b>Class</b>",
            "<i>School</i>",
        )

        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", badge)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", badge)
        self.assertIn("&lt;b&gt;Class&lt;/b&gt;", badge)
        self.assertIn("&lt;i&gt;School&lt;/i&gt;", badge)


if __name__ == "__main__":
    unittest.main()
