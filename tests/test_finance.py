"""اختبارات الفواتير والمدفوعات المالية."""
from __future__ import annotations

import unittest
import csv
import io

from core.exceptions import BusinessRuleError, ValidationError
from core.repos import finance as finance_repo
from core.services import finance_service

from .base import DbTestCase


class FinanceServiceTests(DbTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.year_id = self.make_year()
        self.student_id = self.make_student()

    def make_invoice(self, amount: float = 1000, discount: float = 100) -> int:
        return finance_service.create_invoice(
            self.student_id,
            self.year_id,
            "رسوم دراسية",
            amount,
            discount,
            actor=self.actor,
        )

    def test_partial_payments_reduce_balance_and_create_receipts(self) -> None:
        invoice_id = self.make_invoice()
        first_receipt = finance_service.record_payment(invoice_id, 300, "نقدي", actor=self.actor)
        second_receipt = finance_service.record_payment(invoice_id, 200, "تحويل", actor=self.actor)

        invoice = finance_repo.get_invoice(invoice_id)
        self.assertEqual(invoice["balance"], 400)
        self.assertEqual(invoice["paid_amount"], 500)
        self.assertNotEqual(first_receipt, second_receipt)
        self.assertEqual(len(finance_service.payments_for_invoice(invoice_id)), 2)

    def test_overpayment_is_rejected_without_recording(self) -> None:
        invoice_id = self.make_invoice()
        finance_service.record_payment(invoice_id, 850, "نقدي", actor=self.actor)

        with self.assertRaises(BusinessRuleError):
            finance_service.record_payment(invoice_id, 51, "بطاقة", actor=self.actor)

        invoice = finance_repo.get_invoice(invoice_id)
        self.assertEqual(invoice["paid_amount"], 850)
        self.assertEqual(invoice["balance"], 50)
        self.assertEqual(len(finance_service.payments_for_invoice(invoice_id)), 1)

    def test_discount_must_be_less_than_invoice_amount(self) -> None:
        with self.assertRaises(BusinessRuleError):
            self.make_invoice(amount=100, discount=100)

    def test_non_finite_money_values_are_rejected(self) -> None:
        with self.assertRaises(BusinessRuleError):
            self.make_invoice(amount=float("inf"), discount=0)
        invoice_id = self.make_invoice()
        with self.assertRaises(BusinessRuleError):
            finance_service.record_payment(invoice_id, float("nan"), "نقدي", actor=self.actor)

    def test_term_must_belong_to_invoice_year(self) -> None:
        from core.services import terms_service, years_service

        other_year = years_service.create_year(
            "2027/2028", "2027-09-01", "2028-06-30", False, actor=self.actor
        )
        other_term = terms_service.create_term(
            other_year, "فصل آخر", "2027-09-01", "2028-01-01", actor=self.actor
        )
        with self.assertRaises(BusinessRuleError):
            finance_service.create_invoice(
                self.student_id,
                self.year_id,
                "رسوم دراسية",
                100,
                term_id=other_term,
                actor=self.actor,
            )

    def test_invalid_payment_method_is_rejected(self) -> None:
        invoice_id = self.make_invoice()
        with self.assertRaises(ValidationError):
            finance_service.record_payment(invoice_id, 10, "شيك غير معتمد", actor=self.actor)

    def test_summary_matches_invoice_and_payment_totals(self) -> None:
        invoice_id = self.make_invoice(amount=500, discount=25)
        finance_service.record_payment(invoice_id, 100, "نقدي", actor=self.actor)

        summary = finance_service.summary(self.year_id)
        self.assertEqual(summary, {"invoice_count": 1, "billed": 475, "paid": 100, "outstanding": 375})

    def test_invoice_csv_is_utf8_bom_and_spreadsheet_safe(self) -> None:
        invoice_id = finance_service.create_invoice(
            self.student_id,
            self.year_id,
            "=HYPERLINK(\"https://bad.example\")",
            100,
            actor=self.actor,
        )

        report = finance_service.export_invoices_csv(self.year_id)
        rows = list(csv.reader(io.StringIO(report.decode("utf-8-sig"))))

        self.assertTrue(report.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(rows[1][0], finance_repo.get_invoice(invoice_id)["invoice_no"])
        self.assertTrue(rows[1][5].startswith("'="))
        self.assertEqual(rows[1][9], "100.00")

    def test_printable_receipt_escapes_untrusted_content(self) -> None:
        from pages.finance import _printable_receipt_html

        invoice_id = finance_service.create_invoice(
            self.student_id,
            self.year_id,
            "<img src=x onerror=alert(1)>",
            100,
            actor=self.actor,
        )
        finance_service.record_payment(invoice_id, 25, "نقدي", actor=self.actor)
        payment_id = finance_repo.payments_for_invoice(invoice_id)[0]["id"]
        receipt = finance_service.receipt_details(payment_id)

        printable = _printable_receipt_html(receipt)

        self.assertIn("25.00", printable)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", printable)
        self.assertNotIn("<img", printable)

    def test_fee_item_generates_invoices_for_matching_level_once(self) -> None:
        from core.services import enrollments_service

        primary_level = self.make_level("ابتدائي")
        middle_level = self.make_level("متوسط")
        primary_class = self.make_class(primary_level, self.year_id, "أ")
        middle_class = self.make_class(middle_level, self.year_id, "ب")
        primary_student = self.make_student("طالب ابتدائي")
        middle_student = self.make_student("طالب متوسط")
        enrollments_service.enroll(primary_student, primary_class, self.year_id, actor=self.actor)
        enrollments_service.enroll(middle_student, middle_class, self.year_id, actor=self.actor)

        fee_item_id = finance_service.create_fee_item(
            self.year_id,
            "رسوم المرحلة الابتدائية",
            750,
            discount=50,
            level_id=primary_level,
            actor=self.actor,
        )

        first_count = finance_service.generate_invoices_for_fee_item(fee_item_id, actor=self.actor)
        second_count = finance_service.generate_invoices_for_fee_item(fee_item_id, actor=self.actor)
        invoices = finance_service.list_invoices(year_id=self.year_id)

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices[0]["student_id"], primary_student)
        self.assertEqual(invoices[0]["fee_item_id"], fee_item_id)
        self.assertEqual(invoices[0]["balance"], 700)

    def test_fee_item_without_level_covers_all_enrolled_students(self) -> None:
        from core.services import enrollments_service

        level = self.make_level()
        class_id = self.make_class(level, self.year_id)
        student = self.make_student()
        enrollments_service.enroll(student, class_id, self.year_id, actor=self.actor)
        fee_item_id = finance_service.create_fee_item(
            self.year_id, "رسوم عامة", 100, actor=self.actor
        )

        self.assertEqual(finance_service.generate_invoices_for_fee_item(fee_item_id), 1)


if __name__ == "__main__":
    unittest.main()