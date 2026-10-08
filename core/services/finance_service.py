"""قواعد الفواتير والمدفوعات المالية."""
from __future__ import annotations

import csv
import io
import math
from datetime import date
from typing import Any
from uuid import uuid4

from core import validators as v
from core.exceptions import BusinessRuleError, NotFoundError
from core.repos import academic as academic_repo
from core.repos import audit
from core.repos import finance as finance_repo
from core.repos import settings as settings_repo
from core.repos import students as students_repo

PAYMENT_METHODS = ("نقدي", "تحويل", "بطاقة", "أخرى")


def _spreadsheet_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def create_invoice(
    student_id: Any,
    year_id: Any,
    description: Any,
    amount: Any,
    discount: Any = 0,
    term_id: Any = None,
    issue_date: Any = None,
    due_date: Any = None,
    *,
    actor: dict[str, Any] | None = None,
) -> int:
    student_value = v.parse_int(student_id, "الطالب", minimum=1)
    year_value = v.parse_int(year_id, "السنة الدراسية", minimum=1)
    student = students_repo.get_raw(student_value)
    if not student:
        raise NotFoundError("الطالب غير موجود")
    year = academic_repo.get_year(year_value)
    if not year:
        raise NotFoundError("السنة الدراسية غير موجودة")

    term_value: int | None = None
    if str(term_id or "").strip():
        term_value = v.parse_int(term_id, "الفصل الدراسي", minimum=1)
        term = academic_repo.get_term(term_value)
        if not term:
            raise NotFoundError("الفصل الدراسي غير موجود")
        if int(term["year_id"]) != year_value:
            raise BusinessRuleError("الفصل الدراسي لا يتبع السنة المختارة")

    clean_description = v.require_text(description, "وصف الفاتورة", max_len=160)
    amount_value = v.parse_money(amount, "المبلغ", minimum=0.01)
    discount_value = v.parse_money(discount, "الخصم")
    if not math.isfinite(amount_value) or not math.isfinite(discount_value):
        raise BusinessRuleError("المبلغ والخصم يجب أن يكونا قيماً مالية محدودة")
    if discount_value >= amount_value:
        raise BusinessRuleError("الخصم يجب أن يكون أقل من مبلغ الفاتورة")
    issue_date_value = v.parse_date(issue_date, "تاريخ الإصدار", required=False) or date.today().isoformat()
    due_date_value = v.parse_date(due_date, "تاريخ الاستحقاق", required=False)
    if due_date_value and due_date_value < issue_date_value:
        raise BusinessRuleError("تاريخ الاستحقاق لا يسبق تاريخ الإصدار")

    actor_id = actor.get("id") if actor else None
    invoice_no = f"INV-{date.today():%Y%m%d}-{uuid4().hex[:8].upper()}"
    invoice_id = finance_repo.create_invoice(
        invoice_no,
        student_value,
        year_value,
        term_value,
        clean_description,
        amount_value,
        discount_value,
        issue_date_value,
        due_date_value,
        actor_id,
    )
    audit.log(
        "إنشاء فاتورة مالية",
        entity="finance_invoices",
        entity_id=invoice_id,
        details=f"{invoice_no} للطالب {student['student_no']} بمبلغ {amount_value:.2f}",
        user=actor,
    )
    return invoice_id


def create_fee_item(
    year_id: Any,
    description: Any,
    amount: Any,
    discount: Any = 0,
    level_id: Any = None,
    due_date: Any = None,
    *,
    actor: dict[str, Any] | None = None,
) -> int:
    year_value = v.parse_int(year_id, "السنة الدراسية", minimum=1)
    if not academic_repo.get_year(year_value):
        raise NotFoundError("السنة الدراسية غير موجودة")
    level_value = v.parse_int(level_id, "المرحلة", minimum=1) if str(level_id or "").strip() else None
    if level_value is not None and not academic_repo.get_level(level_value):
        raise NotFoundError("المرحلة غير موجودة")

    clean_description = v.require_text(description, "وصف بند الرسوم", max_len=160)
    amount_value = v.parse_money(amount, "المبلغ", minimum=0.01)
    discount_value = v.parse_money(discount, "الخصم")
    if not math.isfinite(amount_value) or not math.isfinite(discount_value):
        raise BusinessRuleError("المبلغ والخصم يجب أن يكونا قيماً مالية محدودة")
    if discount_value >= amount_value:
        raise BusinessRuleError("الخصم يجب أن يكون أقل من مبلغ بند الرسوم")
    due_date_value = v.parse_date(due_date, "تاريخ الاستحقاق", required=False)
    actor_id = actor.get("id") if actor else None
    fee_item_id = finance_repo.create_fee_item(
        year_value,
        level_value,
        clean_description,
        amount_value,
        discount_value,
        due_date_value,
        actor_id,
    )
    audit.log(
        "إنشاء بند رسوم",
        entity="finance_fee_items",
        entity_id=fee_item_id,
        details=f"{clean_description} — {amount_value:.2f}",
        user=actor,
    )
    return fee_item_id


def list_fee_items(year_id: Any = None) -> list[dict[str, Any]]:
    year_value = v.parse_int(year_id, "السنة الدراسية", minimum=1) if str(year_id or "").strip() else None
    if year_value is not None and not academic_repo.get_year(year_value):
        raise NotFoundError("السنة الدراسية غير موجودة")
    return finance_repo.list_fee_items(year_value)


def generate_invoices_for_fee_item(
    fee_item_id: Any,
    *,
    actor: dict[str, Any] | None = None,
) -> int:
    fee_item_value = v.parse_int(fee_item_id, "بند الرسوم", minimum=1)
    fee_item = next(
        (item for item in finance_repo.list_fee_items() if int(item["id"]) == fee_item_value),
        None,
    )
    if fee_item is None:
        raise NotFoundError("بند الرسوم غير موجود أو غير فعال")
    actor_id = actor.get("id") if actor else None
    created = finance_repo.generate_invoices_for_fee_item(fee_item_value, actor_id)
    audit.log(
        "توليد فواتير جماعي",
        entity="finance_fee_items",
        entity_id=fee_item_value,
        details=f"{fee_item['description']} — فواتير جديدة: {created}",
        user=actor,
    )
    return created


def record_payment(
    invoice_id: Any,
    amount: Any,
    method: Any,
    reference: Any = None,
    *,
    actor: dict[str, Any] | None = None,
) -> str:
    invoice_value = v.parse_int(invoice_id, "الفاتورة", minimum=1)
    amount_value = v.parse_money(amount, "المبلغ المدفوع", minimum=0.01)
    if not math.isfinite(amount_value):
        raise BusinessRuleError("المبلغ المدفوع يجب أن يكون قيمة مالية محدودة")
    method_value = v.require_choice(method, "طريقة الدفع", PAYMENT_METHODS)
    reference_value = v.optional_text(reference, max_len=120)
    actor_id = actor.get("id") if actor else None
    _payment_id, receipt_no = finance_repo.record_payment(
        invoice_value, amount_value, method_value, reference_value, actor_id
    )
    audit.log(
        "استلام دفعة مالية",
        entity="finance_payments",
        entity_id=invoice_value,
        details=f"الإيصال {receipt_no} — {amount_value:.2f} — {method_value}",
        user=actor,
    )
    return receipt_no


def list_invoices(
    student_id: Any = None,
    year_id: Any = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    student_value = v.parse_int(student_id, "الطالب", minimum=1) if str(student_id or "").strip() else None
    year_value = v.parse_int(year_id, "السنة الدراسية", minimum=1) if str(year_id or "").strip() else None
    if status not in (None, "paid", "outstanding"):
        raise BusinessRuleError("حالة الفاتورة غير معروفة")
    return finance_repo.list_invoices(student_value, year_value, status)


def payments_for_invoice(invoice_id: Any) -> list[dict[str, Any]]:
    invoice_value = v.parse_int(invoice_id, "الفاتورة", minimum=1)
    if not finance_repo.get_invoice(invoice_value):
        raise NotFoundError("الفاتورة غير موجودة")
    return finance_repo.payments_for_invoice(invoice_value)


def receipt_details(payment_id: Any) -> dict[str, Any]:
    payment_value = v.parse_int(payment_id, "الإيصال", minimum=1)
    receipt = finance_repo.get_payment_receipt(payment_value)
    if receipt is None:
        raise NotFoundError("الإيصال غير موجود")
    receipt["institution_name"] = settings_repo.institution_name()
    receipt["currency"] = settings_repo.currency()
    return receipt


def summary(year_id: Any = None) -> dict[str, float | int]:
    year_value = v.parse_int(year_id, "السنة الدراسية", minimum=1) if str(year_id or "").strip() else None
    if year_value is not None and not academic_repo.get_year(year_value):
        raise NotFoundError("السنة الدراسية غير موجودة")
    return finance_repo.summary(year_value)


def export_invoices_csv(year_id: Any = None) -> bytes:
    """Export invoice balances as UTF-8 CSV safe to open in spreadsheet apps."""
    year_value = v.parse_int(year_id, "السنة الدراسية", minimum=1) if str(year_id or "").strip() else None
    if year_value is not None and not academic_repo.get_year(year_value):
        raise NotFoundError("السنة الدراسية غير موجودة")

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "رقم الفاتورة",
            "رقم الطالب",
            "اسم الطالب",
            "السنة الدراسية",
            "الفصل الدراسي",
            "البيان",
            "المبلغ",
            "الخصم",
            "المدفوع",
            "المتبقي",
            "تاريخ الإصدار",
            "تاريخ الاستحقاق",
            "الحالة",
        ]
    )
    for invoice in finance_repo.list_invoices(year_id=year_value):
        writer.writerow(
            [
                _spreadsheet_safe(invoice["invoice_no"]),
                _spreadsheet_safe(invoice["student_no"]),
                _spreadsheet_safe(invoice["full_name"]),
                _spreadsheet_safe(invoice["year_name"]),
                _spreadsheet_safe(invoice.get("term_name")),
                _spreadsheet_safe(invoice["description"]),
                f"{float(invoice['amount']):.2f}",
                f"{float(invoice['discount']):.2f}",
                f"{float(invoice['paid_amount']):.2f}",
                f"{float(invoice['balance']):.2f}",
                _spreadsheet_safe(invoice["issue_date"]),
                _spreadsheet_safe(invoice.get("due_date")),
                "مسددة" if invoice["balance"] <= 0 else "مستحقة",
            ]
        )
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")