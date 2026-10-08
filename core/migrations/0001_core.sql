-- ==========================================================
-- 0001_core : الجداول الأساسية للمرحلة 1 (الهوية + الأكاديمي)
-- ملاحظة: جدول schema_version يُنشأ في الكود قبل تطبيق الهجرة.
-- الهجرات forward-only ومرقّمة، ولا تُعدَّل بعد التطبيق.
-- ==========================================================

CREATE TABLE IF NOT EXISTS users (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    username             TEXT NOT NULL UNIQUE,
    full_name            TEXT NOT NULL,
    role                 TEXT NOT NULL CHECK (role IN ('admin','staff','accountant','teacher','viewer')),
    password_hash        TEXT NOT NULL,
    password_salt        TEXT NOT NULL,
    is_active            INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0,1)),
    failed_attempts      INTEGER NOT NULL DEFAULT 0,
    locked_until         TEXT,
    last_login           TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS academic_years (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    start_date TEXT,
    end_date   TEXT,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0,1))
);

CREATE TABLE IF NOT EXISTS terms (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    year_id    INTEGER NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    start_date TEXT,
    end_date   TEXT,
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0,1)),
    UNIQUE (year_id, name)
);

CREATE TABLE IF NOT EXISTS levels (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS teachers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   TEXT NOT NULL,
    national_id TEXT UNIQUE,
    phone       TEXT,
    email       TEXT,
    hire_date   TEXT,
    specialty   TEXT,
    salary      REAL NOT NULL DEFAULT 0 CHECK (salary >= 0),
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS classes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    level_id            INTEGER NOT NULL REFERENCES levels(id),
    year_id             INTEGER NOT NULL REFERENCES academic_years(id),
    capacity            INTEGER NOT NULL DEFAULT 30 CHECK (capacity > 0),
    room                TEXT,
    homeroom_teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
    UNIQUE (name, year_id)
);

CREATE TABLE IF NOT EXISTS subjects (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT UNIQUE,
    name         TEXT NOT NULL,
    level_id     INTEGER REFERENCES levels(id) ON DELETE SET NULL,
    weekly_hours REAL NOT NULL DEFAULT 0 CHECK (weekly_hours >= 0),
    max_score    REAL NOT NULL DEFAULT 100 CHECK (max_score > 0),
    is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);

CREATE TABLE IF NOT EXISTS students (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_no     TEXT NOT NULL UNIQUE,
    full_name      TEXT NOT NULL,
    national_id    TEXT UNIQUE,
    gender         TEXT CHECK (gender IN ('ذكر','أنثى')),
    birth_date     TEXT,
    guardian_name  TEXT,
    guardian_phone TEXT,
    address        TEXT,
    status         TEXT NOT NULL DEFAULT 'منتظم' CHECK (status IN ('منتظم','منسحب','متخرج','موقوف')),
    notes          TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_users_role      ON users(role);
CREATE INDEX IF NOT EXISTS idx_teachers_active ON teachers(is_active);
CREATE INDEX IF NOT EXISTS idx_classes_year    ON classes(year_id);
CREATE INDEX IF NOT EXISTS idx_classes_level   ON classes(level_id);
CREATE INDEX IF NOT EXISTS idx_subjects_level  ON subjects(level_id);
CREATE INDEX IF NOT EXISTS idx_students_name   ON students(full_name);
CREATE INDEX IF NOT EXISTS idx_students_status ON students(status);

CREATE TABLE IF NOT EXISTS enrollments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id    INTEGER NOT NULL REFERENCES classes(id),
    year_id     INTEGER NOT NULL REFERENCES academic_years(id),
    term_id     INTEGER REFERENCES terms(id) ON DELETE SET NULL,
    enroll_date TEXT NOT NULL DEFAULT (date('now','localtime')),
    status      TEXT NOT NULL DEFAULT 'مسجّل' CHECK (status IN ('مسجّل','منقول','منسحب')),
    discount    REAL NOT NULL DEFAULT 0 CHECK (discount >= 0),
    UNIQUE (student_id, year_id)
);

CREATE TABLE IF NOT EXISTS teaching_assignments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    class_id   INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    term_id    INTEGER REFERENCES terms(id) ON DELETE SET NULL,
    UNIQUE (teacher_id, subject_id, class_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER,
    username  TEXT,
    action    TEXT NOT NULL,
    entity    TEXT,
    entity_id TEXT,
    details   TEXT,
    ip        TEXT,
    at        TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_enroll_class   ON enrollments(class_id, status);
CREATE INDEX IF NOT EXISTS idx_enroll_student ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enroll_year    ON enrollments(year_id);
CREATE INDEX IF NOT EXISTS idx_assign_teacher ON teaching_assignments(teacher_id);
CREATE INDEX IF NOT EXISTS idx_assign_class   ON teaching_assignments(class_id);
CREATE INDEX IF NOT EXISTS idx_audit_at       ON audit_log(at);
CREATE INDEX IF NOT EXISTS idx_audit_entity   ON audit_log(entity, entity_id);

