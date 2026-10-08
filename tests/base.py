"""أدوات مشتركة لاختبارات المشروع: قاعدة بيانات مؤقتة معزولة لكل اختبار."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import db
from core.repos import settings as settings_repo


class DbTestCase(unittest.TestCase):
    """قاعدة بيانات مؤقتة معزولة لكل صنف اختبار، وتُفرَّغ الجداول بين الاختبارات.

    إنشاء ملف قاعدة جديد لكل اختبار بطيء على ويندوز (فحص مضاد الفيروسات)،
    لذا نُنشئ الملف مرة واحدة لكل صنف ثم نُفرّغ الجداول (سريع ومعزول تماماً).
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._class_tmp = tempfile.TemporaryDirectory(prefix="inst_test_")
        cls._env_backup = {
            key: os.environ.get(key) for key in ("INST_DB", "INST_DATA_DIR", "INST_PBKDF2_ITERATIONS")
        }
        os.environ["INST_DATA_DIR"] = cls._class_tmp.name
        os.environ["INST_DB"] = str(Path(cls._class_tmp.name) / "test.db")
        os.environ["INST_PBKDF2_ITERATIONS"] = "1000"  # تسريع الاختبارات فقط
        db.init_db()

    @classmethod
    def tearDownClass(cls) -> None:
        for key, value in cls._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls._class_tmp.cleanup()

    def setUp(self) -> None:
        self._reset_database()
        settings_repo.ensure_defaults()
        self.actor = {"id": None, "username": "tester", "role": "admin"}

    @staticmethod
    def _reset_database() -> None:
        """تفريغ كل الجداول (مع الحفاظ على المخطط) بترتيب عكس التبعيات."""
        # ترتيب حذف آمن يحترم القيود المرجعية حتى مع foreign_keys=ON
        order = [
            "audit_log",
            "finance_payments",
            "finance_invoices",
            "finance_fee_items",
            "teaching_assignments",
            "enrollments",
            "students",
            "classes",
            "subjects",
            "levels",
            "terms",
            "academic_years",
            "teachers",
            "users",
            "settings",
        ]
        with db.transaction() as conn:
            for table in order:
                conn.execute(f'DELETE FROM "{table}"')


    # ---------- مساعدات بناء بيانات الاختبار ----------

    def make_year(self, name: str = "2026/2027", make_current: bool = True) -> int:
        from core.services import years_service

        return years_service.create_year(name, "2026-09-01", "2027-06-30", make_current, actor=self.actor)

    def make_term(self, year_id: int, name: str = "الفصل الأول", make_current: bool = True) -> int:
        from core.services import terms_service

        return terms_service.create_term(
            year_id, name, "2026-09-01", "2027-01-15", make_current, actor=self.actor
        )

    def make_level(self, name: str = "الابتدائي") -> int:
        from core.services import levels_service

        return levels_service.create_level(name, 10, None, actor=self.actor)

    def make_class(self, level_id: int, year_id: int, name: str = "أ", capacity: int = 3) -> int:
        from core.services import classes_service

        return classes_service.create_class(name, level_id, year_id, capacity, None, None, actor=self.actor)

    def make_student(self, name: str = "أحمد محمد", **extra: object) -> int:
        from core.services import students_service

        payload = {"full_name": name, "status": "منتظم"}
        payload.update(extra)
        return students_service.create_student(payload, year_name="2026", actor=self.actor)

    def make_teacher(self, name: str = "خالد العلي") -> int:
        from core.services import teachers_service

        return teachers_service.create_teacher(name, None, "0555555555", None, None, "رياضيات", 5000, actor=self.actor)

    def make_subject(self, name: str = "الرياضيات", level_id: int | None = None) -> int:
        from core.services import subjects_service

        return subjects_service.create_subject(name, None, level_id, 4, 100, actor=self.actor)

    def admin_user(self, username: str = "admin", password: str = "Manager#2026") -> int:
        from core.services import users_service

        return users_service.create_user(
            username, "مدير النظام", "admin", password, must_change=False, actor=self.actor
        )
