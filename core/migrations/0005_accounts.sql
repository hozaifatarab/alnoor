-- ============================================================
-- المرحلة: ربط الطلاب بحسابات الدخول + تسجيل موحّد (المرحلة 5)
-- ============================================================
-- المعلمون مرتبطون بحساب دخول عبر user_id منذ المرحلة 1.
-- الطلاب لم يكن لهم حساب، فنضيف نفس الربط لتوحيد شاشة التسجيل.

ALTER TABLE students
    ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_students_user
    ON students(user_id)
    WHERE user_id IS NOT NULL;
