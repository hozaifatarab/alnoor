"""إعدادات النظام العامة: المسارات، الثوابت، الأدوار والصلاحيات، وأنماط RTL.

لا يوجد في هذا الملف أي منطق أعمال — ثوابت ودوال قراءة فقط.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------- هوية النظام ----------
APP_TITLE = "نظام إدارة المؤسسة التعليمية"
APP_SHORT = "المؤسسة التعليمية"
DEFAULT_INSTITUTION_NAME = "مؤسسة النور التعليمية"
DEFAULT_CURRENCY = "ر.س"

# ---------- المسارات ----------
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
VENDOR_DIR = STATIC_DIR / "vendor"
DOCS_DIR = BASE_DIR / "docs"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def data_dir() -> Path:
    """مجلد البيانات (قاعدة البيانات والسجلات). يمكن تجاوزه بـ INST_DATA_DIR."""
    directory = Path(os.environ.get("INST_DATA_DIR", str(BASE_DIR / "data")))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def db_path() -> Path:
    """مسار قاعدة البيانات الحالي (يُقرأ عند الطلب لا عند الاستيراد)."""
    override = os.environ.get("INST_DB")
    return Path(override) if override else data_dir() / "institution.db"


# ---------- سياسات الأمان ----------
MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES = 15
PBKDF2_ITERATIONS = 200_000


def pbkdf2_iterations() -> int:
    """عدد تكرارات PBKDF2 (قابل للتقليل في الاختبارات لسرعة التنفيذ)."""
    try:
        return max(1, int(os.environ.get("INST_PBKDF2_ITERATIONS", PBKDF2_ITERATIONS)))
    except (TypeError, ValueError):
        return PBKDF2_ITERATIONS

# ---------- الأدوار ----------
ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"
ROLE_ACCOUNTANT = "accountant"
ROLE_TEACHER = "teacher"
ROLE_VIEWER = "viewer"
ROLES = (ROLE_ADMIN, ROLE_STAFF, ROLE_ACCOUNTANT, ROLE_TEACHER, ROLE_VIEWER)
ROLE_LABELS = {
    ROLE_ADMIN: "مدير النظام",
    ROLE_STAFF: "شؤون الطلاب",
    ROLE_ACCOUNTANT: "محاسب",
    ROLE_TEACHER: "معلّم",
    ROLE_VIEWER: "عرض فقط",
}

# ---------- الصلاحيات ----------
PERM_DASHBOARD = "dashboard"
PERM_STUDENTS = "students"
PERM_TEACHERS = "teachers"
PERM_ACADEMIC = "academic"
PERM_ENROLLMENTS = "enrollments"
PERM_ATTENDANCE = "attendance"
PERM_GRADES = "grades"
PERM_FINANCE = "finance"
PERM_REPORTS = "reports"
PERM_USERS = "users"
PERM_SETTINGS = "settings"
# إصدار بطاقات QR للطلاب — للمدير فقط (التوقيع بمفتاح النظام عملية حساسة).
PERM_STUDENT_CARDS = "student_cards"

ALL_PERMISSIONS = frozenset({
    PERM_DASHBOARD, PERM_STUDENTS, PERM_TEACHERS, PERM_ACADEMIC, PERM_ENROLLMENTS,
    PERM_ATTENDANCE, PERM_GRADES, PERM_FINANCE, PERM_REPORTS, PERM_USERS, PERM_SETTINGS,
    PERM_STUDENT_CARDS,
})

# مصفوفة الصلاحيات: إصدار بطاقات QR (PERM_STUDENT_CARDS) للمدير فقط —
# التوقيع بمفتاح النظام عملية حساسة ولا تُمنح لأي دور آخر.
PERMISSION_MATRIX: dict[str, frozenset[str]] = {
    ROLE_ADMIN: ALL_PERMISSIONS,
    ROLE_STAFF: frozenset({
        PERM_DASHBOARD, PERM_STUDENTS, PERM_TEACHERS, PERM_ACADEMIC,
        PERM_ENROLLMENTS, PERM_ATTENDANCE, PERM_GRADES, PERM_REPORTS,
    }),
    ROLE_ACCOUNTANT: frozenset({PERM_DASHBOARD, PERM_STUDENTS, PERM_FINANCE, PERM_REPORTS}),
    ROLE_TEACHER: frozenset({PERM_DASHBOARD, PERM_STUDENTS, PERM_ATTENDANCE, PERM_GRADES}),
    ROLE_VIEWER: frozenset({PERM_DASHBOARD, PERM_STUDENTS, PERM_REPORTS}),
}


def can(role: str | None, permission: str) -> bool:
    """هل يملك الدور الصلاحية المطلوبة؟"""
    if not role:
        return False
    return permission in PERMISSION_MATRIX.get(role, frozenset())


def role_label(role: str | None) -> str:
    return ROLE_LABELS.get(role or "", role or "—")


# ---------- إعدادات قابلة للتحكم من الشاشة ----------
SETTING_DEFAULTS: dict[str, str] = {
    "institution_name": DEFAULT_INSTITUTION_NAME,
    "currency": DEFAULT_CURRENCY,
    "address": "",
    "phone": "",
    "current_year_id": "",
    "current_term_id": "",
    "late_after_minutes": "10",
    "default_period_start": "07:30",
    "day_close_time": "14:00",
    "absence_alert_threshold": "3",
    "holidays": "[]",
    "auth_secret": "",
    "qr_secret": "",
    "theme": "minty",
}

# ---------- ثوابت الوحدات الأكاديمية ----------
GENDERS = ("ذكر", "أنثى")
STUDENT_STATUSES = ("منتظم", "منسحب", "متخرج", "موقوف")
ENROLLMENT_STATUSES = ("مسجّل", "منقول", "منسحب")
ATTENDANCE_STATUSES = ("حاضر", "متأخر", "غائب", "بعذر")
ATTENDANCE_SOURCES = ("منظومة", "بطاقة QR", "يدوي")
