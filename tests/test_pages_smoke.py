"""اختبارات الدخان: استيراد التطبيق والشاشات وتوافق جدول المسارات مع الصلاحيات."""
from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from core import config

from .base import DbTestCase

PAGE_MODULES = [
    "pages.login",
    "pages.profile",
    "pages.dashboard",
    "pages.attendance_scan",
    "pages.attendance",
    "pages.grades",
    "pages.student_cards",
    "pages.id_cards",
    "pages.finance",
    "pages.students",
    "pages.teachers",
    "pages.academic",
    "pages.classes",
    "pages.subjects",
    "pages.enrollments",
    "pages.assignments",
    "pages.users",
    "pages.settings",
    "pages.audit_log",
]

UI_MODULES = ["ui.theme", "ui.layout", "ui.components", "ui.charts", "ui.options", "ui.scanner"]


class ImportSmokeTests(DbTestCase):
    def test_page_modules_import(self) -> None:
        for name in PAGE_MODULES:
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_ui_modules_import(self) -> None:
        for name in UI_MODULES:
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_core_modules_import(self) -> None:
        for name in ("core.auth", "core.bootstrap", "core.db", "core.security", "core.validators"):
            with self.subTest(module=name):
                importlib.import_module(name)


class RoutesSmokeTests(DbTestCase):
    def test_routes_registered_with_permissions(self) -> None:
        from app import ROUTES, build_applications

        expected = {
            "index",
            "dashboard",
            "attendance_scan",
            "attendance",
            "grades",
            "finance",
            "student_cards",
            "id_cards",
            "students",
            "teachers",
            "academic",
            "classes",
            "subjects",
            "enrollments",
            "assignments",
            "users",
            "settings",
            "audit_log",
            "my_account",
        }
        self.assertEqual(set(ROUTES), expected)
        applications = build_applications()
        self.assertEqual(set(applications), expected)
        for name, handler in applications.items():
            with self.subTest(route=name):
                self.assertTrue(callable(handler))

    def test_public_route_is_login(self) -> None:
        from app import ROUTES
        from pages import login

        self.assertEqual(ROUTES["index"], (login.login, "public"))
        self.assertEqual(ROUTES["dashboard"][1], config.PERM_DASHBOARD)

    def test_guarded_routes_have_wrapper(self) -> None:
        """كل مسار محمي يجب أن يكون مُزيَّناً بـ wraps (يحمل __wrapped__)."""
        from app import build_applications

        applications = build_applications()
        guarded = [name for name in applications if name not in ("index",)]
        for name in guarded:
            with self.subTest(route=name):
                self.assertTrue(hasattr(applications[name], "__wrapped__"))

    def test_nav_items_match_permissions(self) -> None:
        from ui import layout

        apps = {item[0] for item in layout.NAV_ITEMS}
        self.assertIn("students", apps)
        self.assertIn("settings", apps)
        for _app_name, _label, permission in layout.NAV_ITEMS:
            self.assertIn(permission, config.ALL_PERMISSIONS)

    def test_staff_navigation_hides_admin_pages(self) -> None:
        from ui import layout

        staff_user = {"role": config.ROLE_STAFF}
        apps = {item[0] for item in layout.nav_items_for(staff_user)}
        self.assertIn("students", apps)
        self.assertNotIn("users", apps)
        self.assertNotIn("settings", apps)
        self.assertNotIn("finance", apps)
        self.assertNotIn("student_cards", apps)
        self.assertIn("my_account", apps)

    def test_accountant_navigation_includes_finance(self) -> None:
        from ui import layout

        accountant_user = {"role": config.ROLE_ACCOUNTANT}
        apps = {item[0] for item in layout.nav_items_for(accountant_user)}
        self.assertIn("finance", apps)
        self.assertNotIn("users", apps)
        self.assertNotIn("student_cards", apps)

    def test_student_cards_are_manager_only(self) -> None:
        from app import ROUTES
        from ui import layout

        self.assertEqual(ROUTES["student_cards"][1], config.PERM_STUDENT_CARDS)
        self.assertIn(config.PERM_STUDENT_CARDS, config.ALL_PERMISSIONS)
        # المدير فقط — لا staff ولا teacher ولا accountant ولا viewer
        for role in (config.ROLE_ADMIN,):
            self.assertTrue(config.can(role, config.PERM_STUDENT_CARDS))
        for role in (config.ROLE_STAFF, config.ROLE_TEACHER, config.ROLE_ACCOUNTANT, config.ROLE_VIEWER):
            with self.subTest(role=role):
                self.assertFalse(config.can(role, config.PERM_STUDENT_CARDS))
                apps = {item[0] for item in layout.nav_items_for({"role": role})}
                self.assertNotIn("student_cards", apps)
        admin_apps = {item[0] for item in layout.nav_items_for({"role": config.ROLE_ADMIN})}
        self.assertIn("student_cards", admin_apps)

    def test_phase2_routes_and_nav_are_wired(self) -> None:
        """مسارات المرحلة 2 (مسح/حضور/درجات/بطاقات) مسجّلة وظاهرة حسب الصلاحيات."""
        from app import ROUTES
        from ui import layout

        self.assertEqual(ROUTES["attendance_scan"][1], config.PERM_ATTENDANCE)
        self.assertEqual(ROUTES["attendance"][1], config.PERM_ATTENDANCE)
        self.assertEqual(ROUTES["grades"][1], config.PERM_GRADES)

        apps = {item[0] for item in layout.nav_items_for({"role": config.ROLE_TEACHER})}
        self.assertIn("attendance_scan", apps)
        self.assertIn("attendance", apps)
        self.assertIn("grades", apps)

        staff_apps = {item[0] for item in layout.nav_items_for({"role": config.ROLE_STAFF})}
        self.assertIn("attendance_scan", staff_apps)
        self.assertIn("grades", staff_apps)

        viewer_apps = {item[0] for item in layout.nav_items_for({"role": config.ROLE_VIEWER})}
        self.assertNotIn("attendance_scan", viewer_apps)
        self.assertNotIn("grades", viewer_apps)

    def test_scanner_points_to_bundled_vendor_file(self) -> None:
        """مسار jsQR المحلي يطابق الملف الموجود فعلاً في static/vendor."""
        from pathlib import Path

        from ui import scanner

        target = Path(__file__).resolve().parents[1] / "static" / "vendor" / "jsQR.min.js"
        self.assertTrue(target.is_file(), f"ملف jsQR المحلي مفقود: {target}")
        self.assertEqual(scanner.VENDOR_JS, "/static/vendor/jsQR.min.js")

    def test_upload_fallback_renders_offline_safe_html(self) -> None:
        """بديل رفع الصورة يُنتج HTML آمناً ويستخدم نفس مكتبة jsQR المحلية."""
        from unittest.mock import patch

        from ui import scanner

        attack = '<img src=x onerror="alert(1)">'
        with patch("ui.scanner.put_html") as put_html, patch("ui.scanner.run_js"):
            scanner.render_upload_area(attack)
            scanner.bind_upload_reader()
        output = " ".join(call.args[0] for call in put_html.call_args_list)
        self.assertIn('type="file"', output)
        self.assertIn('accept="image/', output)
        self.assertIn("qr-upload", output)
        self.assertNotIn("<img src=x", output)
        self.assertIn("&lt;img", output)

    def test_password_toggle_hint_renders_button_and_js(self) -> None:
        """زر إظهار كلمة المرور يُحقن داخل حقل كلمة المرور (CSS + JS)."""
        from pathlib import Path
        from unittest.mock import patch

        from ui import components

        with patch("ui.components.put_html") as put_html, patch(
            "pywebio.session.run_js"
        ) as run_js:
            components.password_toggle_hint()
        css = put_html.call_args.args[0]
        self.assertIn("pw-field-wrap", css)
        self.assertIn("pw-toggle-btn", css)
        run_js.assert_called_once()
        js = run_js.call_args.args[0]
        self.assertIn('type="password"', js)
        self.assertIn("data-pw-toggle", js)
        self.assertIn("__pwToggleBound", js)
        # الأيقونة تُبنى داخل غلاف الحقل وليس زراً منفصلاً فوق النموذج
        self.assertIn("wrap.appendChild(btn)", js)
        self.assertIn("إظهار كلمة المرور", js)
        self.assertNotIn("إظهار كلمة المرور</button>", css)

        root = Path(__file__).resolve().parents[1]
        login_src = (root / "pages" / "login.py").read_text(encoding="utf-8")
        profile_src = (root / "pages" / "profile.py").read_text(encoding="utf-8")
        self.assertIn("password_toggle_hint", login_src)
        self.assertIn("password_toggle_hint", profile_src)
        components_src = (root / "ui" / "components.py").read_text(encoding="utf-8")
        self.assertIn('f.get("type") == "password"', components_src)

    def test_id_cards_renders_signed_qr(self) -> None:
        """شاشة توليد بطاقة QR تُعرض فعلياً وتُنتج بطاقة موقّعة قابلة للمسح."""
        from unittest.mock import patch

        import pages.id_cards as id_cards_page

        form_data = {
            "full_name": "حذيفة بن سالم",
            "student_no": "std-2026-0001",
            "class_name": "الصف الأول-أ",
            "status": "منتظم",
            "scale": "4",
        }
        html_chunks: list[str] = []
        with (
            patch("pages.id_cards.put_html", side_effect=lambda *a, **k: html_chunks.append(a[0] if a else "")),
            patch("pages.id_cards.put_buttons"),
            patch("ui.layout.put_html", side_effect=lambda *a, **k: html_chunks.append(a[0] if a else "")),
            patch("ui.layout.footer"),
        ):
            id_cards_page._render_result(form_data)
        page = " ".join(html_chunks)
        self.assertIn("حذيفة بن سالم", page)
        self.assertIn("STD-2026-0001", page)
        self.assertIn("<svg", page)  # رمز QR فعلي داخل البطاقة
        self.assertIn("الصف الأول-أ", page)


class BootstrapSmokeTests(DbTestCase):
    def test_initial_admin_created_once(self) -> None:
        from core import bootstrap
        from core.services import users_service

        created = bootstrap.ensure_initial_admin()
        self.assertIsNotNone(created)
        self.assertEqual(created["username"], bootstrap.FIRST_RUN_USERNAME)
        self.assertTrue(users_service.authenticate(created["username"], created["password"]))
        self.assertIsNone(bootstrap.ensure_initial_admin(), "لا يجب إنشاء حساب ثانٍ")

    def test_initial_admin_must_change_password(self) -> None:
        from core import bootstrap
        from core.repos import users as users_repo

        bootstrap.ensure_initial_admin()
        admin = users_repo.get_by_username(bootstrap.FIRST_RUN_USERNAME)
        self.assertEqual(admin["must_change_password"], 1)
        self.assertEqual(admin["role"], config.ROLE_ADMIN)


class HtmlOutputSafetyTests(unittest.TestCase):
    def test_shared_html_text_is_escaped(self) -> None:
        from ui import components, layout, scanner

        attack = '<img src=x onerror="alert(1)">'
        with patch("ui.layout.put_html") as put_html:
            layout.alert(attack)
            layout.section(attack, attack)

        output = " ".join(call.args[0] for call in put_html.call_args_list)
        self.assertNotIn("<img", output)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", output)
        self.assertNotIn("<img", components.chip(attack))

        with patch("ui.scanner.put_html") as put_html, patch("ui.scanner.run_js"):
            scanner.render_feedback(attack, False)
        self.assertNotIn("<img", put_html.call_args.args[0])


class PyWebIOApiSmokeTests(unittest.TestCase):
    """فحص ثابت لاستدعاءات pywebio: خيارات خاطئة تظهر أخطاء وقت التشغيل فقط."""

    ALLOWED_INPUT_GROUP_KWARGS = {"validate", "cancelable"}

    def test_input_group_calls_use_valid_kwargs(self) -> None:
        """لا يجوز تمرير خيارات غير مدعومة (مثل help_text) إلى input_group."""
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        offenders: list[str] = []
        for folder in ("pages", "ui"):
            for path in sorted((root / folder).glob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                    if name != "input_group":
                        continue
                    for kw in node.keywords:
                        if kw.arg is None:
                            continue  # تفكيك **kwargs لا يمكن فحصه ثابتاً
                        if kw.arg not in self.ALLOWED_INPUT_GROUP_KWARGS:
                            rel = path.relative_to(root)
                            offenders.append(f"{rel}:{node.lineno} — {kw.arg}")
        self.assertEqual(
            offenders,
            [],
            "input_group باي خيارات غير مدعومة:\n" + "\n".join(offenders),
        )

    def test_pywebio_calls_match_signatures(self) -> None:
        """كل استدعاء لدوال pywebio يجب أن يطابق توقيعها الحقيقي.

        الخيارات الخاطئة هنا لا تُكتشف عند الاستيراد، بل تُعطّل الواجهة
        وقت التشغيل (شاشة بيضاء)، لذلك نفحصها ثابتاً مقابل التوقيع.
        """
        import ast
        import importlib
        import inspect
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        sources = [root / "app.py"]
        for folder in ("pages", "ui"):
            sources.extend(sorted((root / folder).glob("*.py")))

        offenders: list[str] = []
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports: dict[str, tuple[str, str]] = {}
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                if not node.module.startswith("pywebio"):
                    continue
                for alias in node.names:
                    imports[alias.asname or alias.name] = (node.module, alias.name)

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                found = imports.get(node.func.id)
                if found is None:
                    continue
                module_name, original = found
                try:
                    func = getattr(importlib.import_module(module_name), original)
                    params = inspect.signature(func).parameters
                except (ImportError, AttributeError, TypeError, ValueError):
                    continue  # دوال ديناميكية لا يمكن فحصها
                if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
                    continue  # تقبل أي خيار إضافي
                positional = [
                    name
                    for name, p in params.items()
                    if p.kind
                    in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
                named = {
                    name
                    for name, p in params.items()
                    if p.kind
                    in (
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    )
                }
                rel = path.relative_to(root)
                if node.args and len(node.args) > len(positional):
                    accepts_var_positional = any(
                        p.kind is inspect.Parameter.VAR_POSITIONAL
                        for p in params.values()
                    )
                    if not accepts_var_positional:
                        offenders.append(
                            f"{rel}:{node.lineno} — {node.func.id} يستقبل "
                            f"{len(positional)} وسائط موضعية فقط"
                        )
                for kw in node.keywords:
                    if kw.arg is None:
                        continue  # تفكيك **kwargs لا يُفحص ثابتا
                    if kw.arg not in named:
                        offenders.append(
                            f"{rel}:{node.lineno} — {node.func.id} لا يقبل الخيار {kw.arg}"
                        )

        self.assertEqual(
            offenders,
            [],
            "استدعاءات pywebio لا تطابق التوقيع:\n" + "\n".join(offenders),
        )


if __name__ == "__main__":
    unittest.main()
