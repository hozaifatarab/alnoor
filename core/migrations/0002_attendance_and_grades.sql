-- ==========================================================
-- المرحلة 2: الحضور والانصراف بـ QR والتقييمات والدرجات
-- ==========================================================

-- جدول جلسات/سجلات الحضور
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    term_id INTEGER REFERENCES terms(id) ON DELETE SET NULL,
    date TEXT NOT NULL,                         -- بصيغة YYYY-MM-DD
    status TEXT NOT NULL CHECK (status IN ('حاضر', 'متأخر', 'غائب', 'بعذر')),
    scan_time TEXT,                             -- بصيغة HH:MM:SS
    delay_minutes INTEGER DEFAULT 0,            -- دقائق التأخير
    source TEXT NOT NULL DEFAULT 'qr' CHECK (source IN ('qr', 'manual', 'bulk', 'auto_absent')),
    excuse_reason TEXT,                         -- سبب العذر إن وجد
    notes TEXT,
    recorded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(student_id, class_id, date)
);

CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
CREATE INDEX IF NOT EXISTS idx_attendance_class_date ON attendance(class_id, date);
CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);

-- جدول تدقيق عمليات المسح (بما فيها المحاولات المرفوضة/المكررة)
CREATE TABLE IF NOT EXISTS attendance_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_payload TEXT NOT NULL,
    student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
    class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
    scan_date TEXT NOT NULL,
    scan_time TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('success', 'duplicate', 'late', 'invalid_signature', 'not_enrolled', 'inactive', 'not_found', 'error')),
    message TEXT,
    ip_address TEXT,
    recorded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_scans_date ON attendance_scans(scan_date);

-- جدول التقييمات والاختبارات
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                         -- مثل: اختبار دوري 1، مشاركة، نهائي
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    term_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    max_score REAL NOT NULL CHECK (max_score > 0),
    weight REAL NOT NULL DEFAULT 100 CHECK (weight > 0),
    assessment_date TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(name, subject_id, class_id, term_id)
);

CREATE INDEX IF NOT EXISTS idx_assessments_class_subj ON assessments(class_id, subject_id, term_id);

-- جدول درجات الطلاب
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    score REAL NOT NULL CHECK (score >= 0),
    notes TEXT,
    recorded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(assessment_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_grades_assessment ON grades(assessment_id);
CREATE INDEX IF NOT EXISTS idx_grades_student ON grades(student_id);
