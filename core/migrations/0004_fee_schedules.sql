-- المرحلة 3: بنود الرسوم والتوليد الجماعي للفواتير

CREATE TABLE IF NOT EXISTS finance_fee_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year_id INTEGER NOT NULL REFERENCES academic_years(id) ON DELETE RESTRICT,
    level_id INTEGER REFERENCES levels(id) ON DELETE RESTRICT,
    description TEXT NOT NULL CHECK (length(trim(description)) > 0),
    amount REAL NOT NULL CHECK (amount > 0),
    discount REAL NOT NULL DEFAULT 0 CHECK (discount >= 0 AND discount < amount),
    due_date TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_finance_fee_items_year
    ON finance_fee_items(year_id, is_active, id DESC);

ALTER TABLE finance_invoices
    ADD COLUMN fee_item_id INTEGER REFERENCES finance_fee_items(id) ON DELETE RESTRICT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_finance_invoice_fee_student
    ON finance_invoices(fee_item_id, student_id)
    WHERE fee_item_id IS NOT NULL;