"""فحص سريع: بناء التطبيق والمسارات بدون تشغيل الخادم."""
from __future__ import annotations

import _bootstrap  # noqa: F401

import app as app_module

apps = app_module.build_applications()
routes = app_module.ROUTES

expected = {
    "index", "dashboard", "attendance_scan", "attendance", "grades",
    "student_cards", "students", "teachers", "academic", "classes",
    "subjects", "enrollments", "assignments", "users", "settings",
    "audit_log", "my_account",
}

assert set(routes) == expected, f"ROUTES mismatch: {set(routes) ^ expected}"
assert set(apps) == expected, f"apps mismatch: {set(apps) ^ expected}"

guarded = [n for n in apps if n != "index"]
missing_wraps = [n for n in guarded if not hasattr(apps[n], "__wrapped__")]
assert not missing_wraps, f"routes without permission wrapper: {missing_wraps}"

# استيراد كل صفحات الواجهة للتأكد من سلامة التثبيت
import importlib

for page in (
    "pages.attendance", "pages.attendance_scan", "pages.student_cards",
    "pages.grades", "pages.dashboard", "pages.students", "pages.login",
    "ui.scanner", "ui.charts", "ui.layout", "core.qr",
):
    importlib.import_module(page)

print("BOOT_OK", len(apps), "routes")
print("ROUTES:", ", ".join(sorted(apps)))
