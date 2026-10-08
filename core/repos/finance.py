"""مستودع الفواتير والمدفوعات المالية."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from .. import db
from ..exceptions import BusinessRuleError, NotFoundError

_INVOICE_SELECT = """
SELECT i.*, s.student_no, s.full_name, y.name AS year_name,
       t.name AS term_name,
       COALESCE(SUM(p.amount), 0) AS paid_amount,
       ROUND(i.amount - i.discount - COALESCE(SUM(p.amount), 0), 2) AS balance
  FROM finance_invoices i
  JOIN students s ON s.id = i.student_id
  JOIN academic_years y ON y.id = i.year_id
  LEFT JOIN terms t ON t.id = i.term_id
  LEFT JOIN finance_payments p ON p.invoice_id = i.id
"""


def create_invoice(
    invoice_no: str,
    student_id: int,
    year_id: int,
    term_id: int | None,
    description: str,
    amount: float,
    discount: float,
    issue_date: str,
    due_date: str | None,
    created_by: int | None,
    fee_item_id: int | None = None,
) -> int:
    return db.execute(
        "INSERT INTO finance_invoices(invoice_no, student_id, year_id, term_id, description,"
        " amount, discount, issue_date, due_date, created_by, fee_item_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            invoice_no,
            student_id,
            year_id,
            term_id,
            description,
            amount,
            discount,
            issue_date,
            due_date,
            created_by,
            fee_item_id,
        ),
    )


def create_fee_item(
    year_id: int,
    level_id: int | None,
    description: str,
    amount: float,
    discount: float,
    due_date: str | None,
    created_by: int | None,
) -> int:
    return db.execute(
        "INSERT INTO finance_fee_items(year_id, level_id, description, amount, discount, due_date, created_by)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (year_id, level_id, description, amount, discount, due_date, created_by),
    )


def list_fee_items(year_id: int | None = None) -> list[dict[str, Any]]:
    sql = [
        "SELECT f.*, y.name AS year_name, l.name AS level_name,"
        " (SELECT COUNT(*) FROM finance_invoices i WHERE i.fee_item_id = f.id) AS generated_count"
        " FROM finance_fee_items f"
        " JOIN academic_years y ON y.id = f.year_id"
        " LEFT JOIN levels l ON l.id = f.level_id"
        " WHERE f.is_active = 1"
    ]
    params: list[Any] = []
    if year_id:
        sql.append("AND f.year_id = ?")
        params.append(year_id)
    sql.append("ORDER BY y.name DESC, f.id DESC")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def generate_invoices_for_fee_item(fee_item_id: int, created_by: int | None) -> int:
    """Generate at most one invoice per eligible enrolled student, atomically."""
    with db.transaction() as conn:
        fee_item = conn.execute(
            "SELECT * FROM finance_fee_items WHERE id = ? AND is_active = 1",
            (fee_item_id,),
        ).fetchone()
        if fee_item is None:
            raise NotFoundError("بند الرسوم غير موجود أو غير فعال")

        students = conn.execute(
            "SELECT DISTINCT s.id AS student_id FROM enrollments e"
            " JOIN students s ON s.id = e.student_id"
            " JOIN classes c ON c.id = e.class_id"
            " WHERE e.year_id = ? AND e.status = 'مسجّل' AND c.year_id = ?"
            " AND s.status = 'منتظم'"
            " AND (? IS NULL OR c.level_id = ?)"
            " ORDER BY s.id",
            (
                fee_item["year_id"],
                fee_item["year_id"],
                fee_item["level_id"],
                fee_item["level_id"],
            ),
        ).fetchall()

        created = 0
        for student in students:
            invoice_no = f"INV-{datetime.now():%Y%m%d}-{uuid4().hex[:8].upper()}"
            cursor = conn.execute(
                "INSERT OR IGNORE INTO finance_invoices(invoice_no, student_id, year_id, description,"
                " amount, discount, issue_date, due_date, created_by, fee_item_id)"
                " VALUES (?, ?, ?, ?, ?, ?, date('now','localtime'), ?, ?, ?)",
                (
                    invoice_no,
                    student["student_id"],
                    fee_item["year_id"],
                    fee_item["description"],
                    fee_item["amount"],
                    fee_item["discount"],
                    fee_item["due_date"],
                    created_by,
                    fee_item_id,
                ),
            )
            created += int(cursor.rowcount > 0)
        return created


def list_invoices(
    student_id: int | None = None,
    year_id: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    sql = [_INVOICE_SELECT, "WHERE 1 = 1"]
    params: list[Any] = []
    if student_id:
        sql.append("AND i.student_id = ?")
        params.append(student_id)
    if year_id:
        sql.append("AND i.year_id = ?")
        params.append(year_id)
    sql.append("GROUP BY i.id")
    if status == "paid":
        sql.append("HAVING ROUND(i.amount - i.discount - COALESCE(SUM(p.amount), 0), 2) <= 0")
    elif status == "outstanding":
        sql.append("HAVING ROUND(i.amount - i.discount - COALESCE(SUM(p.amount), 0), 2) > 0")
    sql.append("ORDER BY i.issue_date DESC, i.id DESC")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def get_invoice(invoice_id: int) -> dict[str, Any] | None:
    rows = db.query_all(
        _INVOICE_SELECT + " WHERE i.id = ? GROUP BY i.id", (invoice_id,)
    )
    return dict(rows[0]) if rows else None


def record_payment(
    invoice_id: int,
    amount: float,
    method: str,
    reference: str | None,
    received_by: int | None,
) -> tuple[int, str]:
    """Check balance and append a payment atomically to prevent overpayment races."""
    with db.transaction() as conn:
        invoice = conn.execute(
            "SELECT i.amount, i.discount, COALESCE(SUM(p.amount), 0) AS paid_amount"
            " FROM finance_invoices i LEFT JOIN finance_payments p ON p.invoice_id = i.id"
            " WHERE i.id = ? GROUP BY i.id",
            (invoice_id,),
        ).fetchone()
        if invoice is None:
            raise NotFoundError("الفاتورة غير موجودة")
        balance = round(float(invoice["amount"]) - float(invoice["discount"]) - float(invoice["paid_amount"]), 2)
        if amount - balance > 0.001:
            raise BusinessRuleError(f"المبلغ يتجاوز الرصيد المتبقي ({balance:.2f})")
        if balance <= 0:
            raise BusinessRuleError("الفاتورة مسددة بالكامل")

        receipt_no = f"RCP-{datetime.now():%Y%m%d}-{uuid4().hex[:8].upper()}"
        cursor = conn.execute(
            "INSERT INTO finance_payments(receipt_no, invoice_id, amount, method, reference, received_by)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (receipt_no, invoice_id, amount, method, reference, received_by),
        )
        return int(cursor.lastrowid), receipt_no


def payments_for_invoice(invoice_id: int) -> list[dict[str, Any]]:
    rows = db.query_all(
        "SELECT p.*, u.username AS received_by_username FROM finance_payments p"
        " LEFT JOIN users u ON u.id = p.received_by"
        " WHERE p.invoice_id = ? ORDER BY p.id DESC",
        (invoice_id,),
    )
    return [dict(row) for row in rows]


def get_payment_receipt(payment_id: int) -> dict[str, Any] | None:
    row = db.query_one(
        "SELECT p.*, i.invoice_no, i.description, i.amount AS invoice_amount, i.discount,"
        " s.student_no, s.full_name, y.name AS year_name, u.username AS received_by_username,"
        " (SELECT COALESCE(SUM(p2.amount), 0) FROM finance_payments p2"
        "   WHERE p2.invoice_id = p.invoice_id AND p2.id <= p.id) AS paid_through"
        " FROM finance_payments p"
        " JOIN finance_invoices i ON i.id = p.invoice_id"
        " JOIN students s ON s.id = i.student_id"
        " JOIN academic_years y ON y.id = i.year_id"
        " LEFT JOIN users u ON u.id = p.received_by"
        " WHERE p.id = ?",
        (payment_id,),
    )
    if not row:
        return None
    details = dict(row)
    details["balance_after"] = round(
        float(details["invoice_amount"])
        - float(details["discount"])
        - float(details["paid_through"]),
        2,
    )
    return details


def summary(year_id: int | None = None) -> dict[str, float | int]:
    sql = [
        "SELECT COUNT(*) AS invoice_count,"
        " ROUND(COALESCE(SUM(i.amount - i.discount), 0), 2) AS billed,"
        " ROUND(COALESCE(SUM(COALESCE(p.paid, 0)), 0), 2) AS paid"
        " FROM finance_invoices i"
        " LEFT JOIN (SELECT invoice_id, SUM(amount) AS paid FROM finance_payments GROUP BY invoice_id) p"
        " ON p.invoice_id = i.id"
        " WHERE 1 = 1"
    ]
    params: list[Any] = []
    if year_id:
        sql.append("AND i.year_id = ?")
        params.append(year_id)
    row = db.query_one(" ".join(sql), params)
    billed = float(row["billed"] or 0)
    paid = float(row["paid"] or 0)
    return {
        "invoice_count": int(row["invoice_count"] or 0),
        "billed": billed,
        "paid": paid,
        "outstanding": round(billed - paid, 2),
    }