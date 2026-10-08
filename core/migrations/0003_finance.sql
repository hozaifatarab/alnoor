-- المرحلة 3: الفواتير والمدفوعات والإيصالات المالية

CREATE TABLE IF NOT EXISTS finance_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT NOT NULL UNIQUE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    year_id INTEGER NOT NULL REFERENCES academic_years(id) ON DELETE RESTRICT,
    term_id INTEGER REFERENCES terms(id) ON DELETE RESTRICT,
    description TEXT NOT NULL CHECK (length(trim(description)) > 0),
    amount REAL NOT NULL CHECK (amount > 0),
    discount REAL NOT NULL DEFAULT 0 CHECK (discount >= 0 AND discount < amount),
    issue_date TEXT NOT NULL,
    due_date TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_finance_invoices_student_year
    ON finance_invoices(student_id, year_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_finance_invoices_due_date
    ON finance_invoices(due_date);

CREATE TABLE IF NOT EXISTS finance_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no TEXT NOT NULL UNIQUE,
    invoice_id INTEGER NOT NULL REFERENCES finance_invoices(id) ON DELETE RESTRICT,
    amount REAL NOT NULL CHECK (amount > 0),
    method TEXT NOT NULL CHECK (method IN ('نقدي', 'تحويل', 'بطاقة', 'أخرى')),
    reference TEXT,
    received_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    received_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_finance_payments_invoice
    ON finance_payments(invoice_id, id);
CREATE INDEX IF NOT EXISTS idx_finance_payments_received_at
    ON finance_payments(received_at);