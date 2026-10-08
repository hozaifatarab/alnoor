"""فحص سريع: هل تستورد خدمات المرحلة 2 وتسجل المسارات؟ (ملف تحقق مؤقت)"""
import sys
import traceback

sys.path.insert(0, ".")

results = []
for name in (
    "core.qr",
    "core.repos.attendance",
    "core.repos.grades",
    "core.services.attendance_service",
    "core.services.grades_service",
    "app",
):
    try:
        __import__(name)
        results.append(f"OK   {name}")
    except Exception:
        results.append(f"FAIL {name}\n{traceback.format_exc()}")

try:
    import app

    results.append(f"ROUTES: {sorted(app.ROUTES)}")
except Exception:
    pass

print("\n".join(results))
