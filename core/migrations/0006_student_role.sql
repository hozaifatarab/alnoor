-- ==========================================================
-- 0006_student_role : إضافة دور «طالب» إلى قيود جدول المستخدمين
-- SQLite لا يدعم تعديل قيود CHECK مباشرة، لذا نُعيد بناء الجدول
-- وفق الإجراء الرسمي (12 خطوة) مع تعطيل المفاتيح الأجنبية مؤقتاً
-- حتى لا تُمسّ روابط الأبناء القائمة (teachers.user_id, attendance...).
-- ملاحظة: ربط الطالب بحساب الدخول (students.user_id) في هجرة 0005_accounts.
-- الهجرة forward-only: تُطبَّق مرة واحدة ولا تُعدَّل بعدها.
-- ==========================================================

PRAGMA foreign_keys = OFF;

BEGIN;

CREATE TABLE users__new (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    username             TEXT NOT NULL UNIQUE,
    full_name            TEXT NOT NULL,
    role                 TEXT NOT NULL CHECK (role IN ('admin','staff','accountant','teacher','viewer','student')),
    password_hash        TEXT NOT NULL,
    password_salt        TEXT NOT NULL,
    is_active            INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0,1)),
    failed_attempts      INTEGER NOT NULL DEFAULT 0,
    locked_until         TEXT,
    last_login           TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

INSERT INTO users__new
    (id, username, full_name, role, password_hash, password_salt,
     is_active, must_change_password, failed_attempts, locked_until, last_login, created_at)
SELECT id, username, full_name, role, password_hash, password_salt,
       is_active, must_change_password, failed_attempts, locked_until, last_login, created_at
  FROM users;

DROP TABLE users;
ALTER TABLE users__new RENAME TO users;

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

COMMIT;

PRAGMA foreign_keys = ON;
