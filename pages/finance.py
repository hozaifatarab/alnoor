"""شاشة الفواتير والمدفوعات للمحاسبة."""
from __future__ import annotations

from typing import Any

from pywebio.input import input, input_group, select
from pywebio.output import put_buttons
from pywebio.session import download, go_app

from core import auth, config
from core.services import finance_service
from ui import components, layout, options

APP = "finance"


def finance() -> None:
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="الفواتير والمدفوعات")

    with components.error_boundary("الإدارة المالية"):
        year_data = input_group(
            "تصفية الفواتير",
            [
                select(
                    "السنة الدراسية",
                    name="year_id",
                    options=options.years(any_label="— كل السنوات —"),
                    required=False,
                )
            ],
            cancelable=False,
        )
        year_id = int(year_data["year_id"]) if year_data.get("year_id") else None
        totals = finance_service.summary(year_id)
        layout.kpi_cards(
            [
                {"label": "الفواتير", "value": totals["invoice_count"]},
                {"label": "إجمالي المستحق", "value": _money(totals["billed"])},
                {"label": "المحصل", "value": _money(totals["paid"]), "kind": "ok"},
                {"label": "المتبقي", "value": _money(totals["outstanding"]), "kind": "warn"},
            ]
        )

        fee_items = finance_service.list_fee_items(year_id)
        layout.section("بنود الرسوم", f"عدد البنود الفعالة: {len(fee_items)}")
        components.table(
            ["البيان", "السنة", "المرحلة", "المبلغ", "الخصم", "الاستحقاق", "الفواتير المولدة"],
            [
                [
                    row["description"],
                    row["year_name"],
                    row.get("level_name") or "كل المراحل",
                    _money(row["amount"]),
                    _money(row["discount"]),
                    row.get("due_date") or "—",
                    row["generated_count"],
                ]
                for row in fee_items
            ],
            empty_message="لا توجد بنود رسوم لهذه السنة",
        )

        invoices = finance_service.list_invoices(year_id=year_id)
        layout.section("الفواتير", f"عدد الفواتير: {len(invoices)}")
        components.table(
            ["رقم الفاتورة", "الطالب", "السنة", "البيان", "المبلغ", "الخصم", "المدفوع", "المتبقي", "الحالة"],
            [
                [
                    row["invoice_no"],
                    f"{row['student_no']} — {row['full_name']}",
                    row["year_name"],
                    row["description"],
                    _money(row["amount"]),
                    _money(row["discount"]),
                    _money(row["paid_amount"]),
                    _money(row["balance"]),
                    components.chip(
                        "مسددة" if row["balance"] <= 0 else "مستحقة",
                        "ok" if row["balance"] <= 0 else "warn",
                    ),
                ]
                for row in invoices
            ],
            empty_message="لا توجد فواتير لهذه التصفية",
        )
        put_buttons(
            [
                {"label": "➕ إصدار فاتورة", "value": "invoice", "color": "primary"},
                {"label": "💳 تسجيل دفعة", "value": "payment", "color": "secondary"},
                {"label": "🧾 عرض الإيصالات", "value": "receipts", "color": "secondary"},
                {"label": "＋ بند رسوم", "value": "fee_item", "color": "secondary"},
                {"label": "⚡ توليد فواتير البند", "value": "generate_fees", "color": "secondary"},
                {"label": "⬇ تصدير تقرير CSV", "value": "export", "color": "secondary"},
            ],
            onclick=lambda action: _handle(action, year_id),
            small=True,
        )
        layout.footer()


def _handle(action: str, year_id: int | None = None) -> None:
    with components.error_boundary("الإدارة المالية"):
        if action == "invoice":
            _create_invoice()
        elif action == "payment":
            _record_payment()
        elif action == "receipts":
            _show_receipts()
        elif action == "fee_item":
            _create_fee_item()
        elif action == "generate_fees":
            _generate_fee_invoices()
        elif action == "export":
            _export_invoice_report(year_id)


def _export_invoice_report(year_id: int | None) -> None:
    content = finance_service.export_invoices_csv(year_id)
    if len(content) <= 3:
        components.toast_warn("لا توجد فواتير لتصديرها")
        return
    year_label = str(year_id) if year_id else "all-years"
    download(f"finance-invoices-{year_label}.csv", content)
    components.toast_ok("تم تنزيل التقرير المالي")


def _create_fee_item() -> None:
    year_options = options.years()
    if not year_options:
        components.toast_error("أضف سنة دراسية قبل إنشاء بند رسوم")
        return
    data = components.form_modal(
        "إنشاء بند رسوم",
        [
            select("السنة الدراسية *", name="year_id", options=year_options, required=True),
            select(
                "المرحلة",
                name="level_id",
                options=options.levels(any_label="— كل المراحل —"),
                required=False,
            ),
            input("البيان *", name="description", required=True, placeholder="رسوم دراسية"),
            input("المبلغ *", name="amount", type="number", required=True),
            input("الخصم", name="discount", type="number", value="0", required=False),
            input("تاريخ الاستحقاق", name="due_date", placeholder="YYYY-MM-DD", required=False),
        ],
        size="large",
    )
    if not data:
        return
    finance_service.create_fee_item(
        data["year_id"],
        data["description"],
        data["amount"],
        data.get("discount") or 0,
        data.get("level_id"),
        data.get("due_date"),
        actor=auth.current_user(),
    )
    components.toast_ok("تم إنشاء بند الرسوم")
    go_app(APP, new_window=False)


def _generate_fee_invoices() -> None:
    fee_items = finance_service.list_fee_items()
    if not fee_items:
        components.toast_warn("أنشئ بند رسوم فعالاً أولاً")
        return
    data = components.form_modal(
        "توليد فواتير بند الرسوم",
        [
            select(
                "بند الرسوم *",
                name="fee_item_id",
                options=[
                    {
                        "label": (
                            f"{row['description']} — {row['year_name']} — "
                            f"{row.get('level_name') or 'كل المراحل'} — {_money(row['amount'])}"
                        ),
                        "value": str(row["id"]),
                    }
                    for row in fee_items
                ],
                required=True,
            )
        ],
    )
    if not data:
        return
    created = finance_service.generate_invoices_for_fee_item(
        data["fee_item_id"], actor=auth.current_user()
    )
    if created:
        components.toast_ok(f"تم إصدار {created} فاتورة جديدة")
    else:
        components.toast_warn("لا توجد تسجيلات مطابقة أو سبق إصدار فواتير هذا البند")
    go_app(APP, new_window=False)


def _create_invoice() -> None:
    student_options = options.students()
    year_options = options.years()
    if not student_options or not year_options:
        components.toast_error("أضف طالباً وسنة دراسية قبل إصدار فاتورة")
        return

    data = components.form_modal(
        "إصدار فاتورة",
        [
            select("الطالب *", name="student_id", options=student_options, required=True),
            select("السنة الدراسية *", name="year_id", options=year_options, required=True),
            select(
                "الفصل الدراسي",
                name="term_id",
                options=options.terms(any_label="— دون تخصيص فصل —"),
                required=False,
            ),
            input("البيان *", name="description", required=True, placeholder="رسوم دراسية"),
            input("المبلغ *", name="amount", type="number", required=True),
            input("الخصم", name="discount", type="number", value="0", required=False),
            input("تاريخ الإصدار", name="issue_date", placeholder="YYYY-MM-DD", required=False),
            input("تاريخ الاستحقاق", name="due_date", placeholder="YYYY-MM-DD", required=False),
        ],
        size="large",
    )
    if not data:
        return
    finance_service.create_invoice(
        data["student_id"],
        data["year_id"],
        data["description"],
        data["amount"],
        data.get("discount") or 0,
        data.get("term_id"),
        data.get("issue_date"),
        data.get("due_date"),
        actor=auth.current_user(),
    )
    components.toast_ok("تم إصدار الفاتورة")
    go_app(APP, new_window=False)


def _record_payment() -> None:
    invoices = finance_service.list_invoices(status="outstanding")
    if not invoices:
        components.toast_warn("لا توجد فواتير مستحقة")
        return
    data = components.form_modal(
        "تسجيل دفعة",
        [
            select(
                "الفاتورة *",
                name="invoice_id",
                options=[
                    {
                        "label": f"{row['invoice_no']} — {row['student_no']} {row['full_name']} — متبقي {_money(row['balance'])}",
                        "value": str(row["id"]),
                    }
                    for row in invoices
                ],
                required=True,
            ),
            input("المبلغ المدفوع *", name="amount", type="number", required=True),
            select(
                "طريقة الدفع *",
                name="method",
                options=options.choices(finance_service.PAYMENT_METHODS),
                required=True,
            ),
            input("رقم مرجعي (اختياري)", name="reference", required=False),
        ],
    )
    if not data:
        return
    receipt_no = finance_service.record_payment(
        data["invoice_id"],
        data["amount"],
        data["method"],
        data.get("reference"),
        actor=auth.current_user(),
    )
    components.toast_ok(f"تم تسجيل الدفعة — الإيصال {receipt_no}")
    go_app(APP, new_window=False)


def _show_receipts() -> None:
    invoices = finance_service.list_invoices()
    if not invoices:
        components.toast_warn("لا توجد فواتير لعرض إيصالاتها")
        return
    data = components.form_modal(
        "إيصالات الفاتورة",
        [
            select(
                "الفاتورة *",
                name="invoice_id",
                options=[
                    {
                        "label": f"{row['invoice_no']} — {row['student_no']} {row['full_name']}",
                        "value": str(row["id"]),
                    }
                    for row in invoices
                ],
                required=True,
            )
        ],
    )
    if not data:
        return
    selected = next(row for row in invoices if str(row["id"]) == data["invoice_id"])
    payments = finance_service.payments_for_invoice(data["invoice_id"])
    layout.section(f"إيصالات {selected['invoice_no']}", f"الرصيد الحالي: {_money(selected['balance'])}")
    components.table(
        ["رقم الإيصال", "المبلغ", "طريقة الدفع", "المرجع", "المستلم", "التاريخ"],
        [
            [
                row["receipt_no"],
                _money(row["amount"]),
                row["method"],
                row.get("reference") or "—",
                row.get("received_by_username") or "—",
                row["received_at"],
            ]
            for row in payments
        ],
        empty_message="لم تُسجّل دفعات لهذه الفاتورة",
    )
    if payments:
        layout.section("تنزيل إيصال للطباعة")
        put_buttons(
            [
                {
                    "label": f"🖨 {row['receipt_no']}",
                    "value": str(row["id"]),
                    "color": "secondary",
                }
                for row in payments
            ],
            onclick=_download_receipt_action,
            small=True,
        )
    layout.footer()


def _download_receipt_action(payment_id: str) -> None:
    with components.error_boundary("تنزيل الإيصال"):
        receipt = finance_service.receipt_details(payment_id)
        filename = f"{receipt['receipt_no']}.html"
        download(filename, _printable_receipt_html(receipt).encode("utf-8"))
        components.toast_ok("تم تنزيل الإيصال؛ افتحه ثم اختر طباعة")


def _printable_receipt_html(receipt: dict[str, Any]) -> str:
    safe = layout.escape_html
    title = safe(receipt["receipt_no"])
    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>إيصال {title}</title>
    <style>
        @page {{ size: A5; margin: 14mm; }}
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; padding: 28px; color: #172b24; background: #f2f6f3; font-family: Tahoma, Arial, sans-serif; }}
        main {{ max-width: 620px; margin: 0 auto; padding: 30px; background: #fff; border: 1px solid #d7e2db; }}
        header {{ border-bottom: 2px solid #19734a; padding-bottom: 16px; margin-bottom: 20px; }}
        h1 {{ margin: 0 0 6px; font-size: 22px; }}
        h2 {{ margin: 0; color: #19734a; font-size: 17px; }}
        dl {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px 20px; }}
        dt {{ color: #52675b; font-size: 12px; }}
        dd {{ margin: 4px 0 0; font-weight: 700; overflow-wrap: anywhere; }}
        .amount {{ margin-top: 20px; padding: 16px; background: #edf6ef; font-size: 20px; font-weight: 700; }}
        button {{ margin-top: 24px; padding: 10px 18px; border: 0; background: #19734a; color: white; cursor: pointer; }}
        @media print {{ body {{ padding: 0; background: white; }} main {{ border: 0; padding: 0; }} button {{ display: none; }} }}
    </style>
</head>
<body>
    <main>
        <header>
            <h1>{safe(receipt['institution_name'])}</h1>
            <h2>إيصال استلام دفعة</h2>
        </header>
        <dl>
            <div><dt>رقم الإيصال</dt><dd>{title}</dd></div>
            <div><dt>تاريخ الاستلام</dt><dd>{safe(receipt['received_at'])}</dd></div>
            <div><dt>رقم الفاتورة</dt><dd>{safe(receipt['invoice_no'])}</dd></div>
            <div><dt>الطالب</dt><dd>{safe(receipt['full_name'])}</dd></div>
            <div><dt>الرقم الأكاديمي</dt><dd>{safe(receipt['student_no'])}</dd></div>
            <div><dt>السنة الدراسية</dt><dd>{safe(receipt['year_name'])}</dd></div>
            <div><dt>البيان</dt><dd>{safe(receipt['description'])}</dd></div>
            <div><dt>طريقة الدفع</dt><dd>{safe(receipt['method'])}</dd></div>
            <div><dt>المرجع</dt><dd>{safe(receipt.get('reference') or '—')}</dd></div>
            <div><dt>المستلم</dt><dd>{safe(receipt.get('received_by_username') or '—')}</dd></div>
        </dl>
        <div class="amount">المبلغ المستلم: {float(receipt['amount']):,.2f} {safe(receipt['currency'])}</div>
        <p>المتبقي على الفاتورة بعد هذه الدفعة: {float(receipt['balance_after']):,.2f} {safe(receipt['currency'])}</p>
        <button onclick="window.print()">طباعة الإيصال</button>
    </main>
</body>
</html>"""


def _money(value: Any) -> str:
    return f"{float(value or 0):,.2f} {config.DEFAULT_CURRENCY}"