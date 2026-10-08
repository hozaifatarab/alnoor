"""نقطة تشغيل نظام إدارة المؤسسة التعليمية.

الاستخدام::

    python app.py                      # يعمل على http://127.0.0.1:8080
    python app.py --port 9000          # منفذ مخصص
    python app.py --host 0.0.0.0 --remote   # إتاحة الوصول من الشبكة المحلية
    python app.py --no-cdn             # تشغيل بلا إنترنت (أصول محلية)
    python app.py --db data/test.db    # قاعدة بيانات مخصصة
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Callable

from core import auth, bootstrap, config, db, logging_setup
from core.repos import settings as settings_repo
from pages import (
    academic,
    assignments,
    attendance,
    attendance_scan,
    audit_log,
    classes,
    dashboard,
    enrollments,
    finance,
    grades,
    id_cards,
    login,
    profile,
    student_cards,
    students,
    subjects,
    teachers,
    users,
)
from pages import settings as settings_page
from ui import theme

logger = logging.getLogger(__name__)

# جدول المسارات: (اسم التطبيق/المسار, الدالة, الصلاحية المطلوبة أو None = يكفي تسجيل الدخول)
ROUTES: dict[str, tuple[Callable[[], None], str | None]] = {
    "index": (login.login, "public"),
    "dashboard": (dashboard.dashboard, config.PERM_DASHBOARD),
    "attendance_scan": (attendance_scan.attendance_scan, config.PERM_ATTENDANCE),
    "attendance": (attendance.attendance, config.PERM_ATTENDANCE),
    "grades": (grades.grades, config.PERM_GRADES),
    "student_cards": (student_cards.student_cards, config.PERM_STUDENT_CARDS),
    "students": (students.students, config.PERM_STUDENTS),
    "teachers": (teachers.teachers, config.PERM_TEACHERS),
    "academic": (academic.academic, config.PERM_ACADEMIC),
    "classes": (classes.classes, config.PERM_ACADEMIC),
    "subjects": (subjects.subjects, config.PERM_ACADEMIC),
    "enrollments": (enrollments.enrollments, config.PERM_ENROLLMENTS),
    "finance": (finance.finance, config.PERM_FINANCE),
    "assignments": (assignments.assignments, config.PERM_ACADEMIC),
    "users": (users.users, config.PERM_USERS),
    "settings": (settings_page.settings, config.PERM_SETTINGS),
    "audit_log": (audit_log.audit_log, config.PERM_SETTINGS),
    "my_account": (profile.my_account, None),
}


def build_applications() -> dict[str, Callable[[], None]]:
    """تطبيق حماية الصلاحيات مركزياً على كل المسارات (مصدر حقيقة واحد)."""
    applications: dict[str, Callable[[], None]] = {}
    for name, (handler, permission) in ROUTES.items():
        if permission == "public":
            applications[name] = handler
        elif permission is None:
            applications[name] = auth.login_required()(handler)
        else:
            applications[name] = auth.login_required(permission)(handler)
    return applications


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="نظام إدارة المؤسسة التعليمية")
    parser.add_argument("--port", type=int, default=8080, help="منفذ الخدمة (افتراضي 8080)")
    parser.add_argument("--host", default="127.0.0.1", help="عنوان الاستماع (افتراضي 127.0.0.1)")
    parser.add_argument("--db", default=None, help="مسار قاعدة البيانات (افتراضي data/institution.db)")
    parser.add_argument("--no-cdn", action="store_true", help="تعطيل CDN لتشغيل بلا إنترنت")
    parser.add_argument("--remote", action="store_true", help="إتاحة الوصول من أجهزة الشبكة")
    parser.add_argument("--debug", action="store_true", help="وضع التطوير (تفاصيل الأخطاء)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.db:
        import os

        os.environ["INST_DB"] = args.db
    logger_path = logging_setup.setup_logging(logging.DEBUG if args.debug else logging.INFO)
    applied = db.init_db()
    settings_repo.ensure_defaults()
    created = bootstrap.ensure_initial_admin()

    from pywebio.platform.tornado import start_server

    institution = settings_repo.institution_name()
    theme.apply_config(institution, settings_repo.get("theme", "minty"))

    print("=" * 66)
    print(f"  {institution} | {config.APP_TITLE}")
    print("=" * 66)
    print(f"  العنوان     : http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}")
    print(f"  قاعدة البيانات: {config.db_path()}")
    print(f"  هجرات مطبقة : {applied or 'لا جديد (المخطط محدّث)'}")
    print(f"  سجل التشغيل : {logger_path}")
    if created:
        print("-" * 66)
        print("  حساب الدخول الأول (يجب تغيير كلمة المرور فوراً):")
        print(f"    المستخدم : {created['username']}")
        print(f"    كلمة المرور: {created['password']}")
    print("=" * 66)

    if not args.remote:
        print("  ملاحظة: الوصول محصور على الجهاز الحالي. للشبكة المحلية استخدم --remote")
    else:
        logger.warning("تم تمكين الوصول من الشبكة المحلية")

    start_server(
        build_applications(),
        port=args.port,
        host=args.host,
        debug=args.debug,
        cdn=not args.no_cdn,
        static_dir=str(config.STATIC_DIR),
        remote_access=args.remote,
        auto_open_webbrowser=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
