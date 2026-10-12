"""فحص بيئة التشغيل: الإصدارات وتوفّر الواجهات البرمجية المطلوبة.

يُشغَّل بـ:  python tools/check_env.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REQUIRED_API = [
    "pywebio.config",
    "pywebio.start_server",
    "pywebio.input.input_group",
    "pywebio.input.actions",
    "pywebio.input.select",
    "pywebio.input.radio",
    "pywebio.output.put_table",
    "pywebio.output.put_buttons",
    "pywebio.output.put_html",
    "pywebio.output.put_markdown",
    "pywebio.output.popup",
    "pywebio.output.use_scope",
    "pywebio.output.clear",
    "pywebio.output.put_error",
    "pywebio.output.put_success",
    "pywebio.output.toast",
    "pywebio.session.go_app",
    "pywebio.session.set_env",
    "pywebio.session.local",
    "pywebio.session.run_js",
    "pywebio.session.eval_js",
    "pywebio.session.download",
    "pywebio.pin.put_input",
    "pywebio.pin.pin_wait_change",
    "pywebio.platform.tornado.start_server",
]


def main() -> int:
    import importlib

    print("=" * 62)
    print("فحص بيئة نظام المؤسسة التعليمية")
    print("=" * 62)

    try:
        import pywebio
        import segno
    except ImportError as exc:  # pragma: no cover
        print(f"[فشل] حزمة مفقودة: {exc}")
        return 1

    print(f"pywebio : {pywebio.__version__}")
    print(f"segno   : {segno.__version__}")
    print(f"python  : {sys.version.split()[0]}")
    print("-" * 62)

    print("واجهات PyWebIO المطلوبة:")
    failures = 0
    for name in REQUIRED_API:
        module_name, attr = name.rsplit(".", 1)
        try:
            module = importlib.import_module(module_name)
            getattr(module, attr)
        except (ImportError, AttributeError) as exc:
            print(f"  [مفقود] {name}: {exc}")
            failures += 1
    if failures == 0:
        print(f"  [سليم] كل الواجهات متوفرة ({len(REQUIRED_API)})")

    print("-" * 62)
    from pywebio.platform import tornado as tornado_platform

    signature = inspect.signature(tornado_platform.start_server)
    print(f"start_server: {signature}")

    from core import config

    print(f"مسار قاعدة البيانات: {config.db_path()}")
    print(f"مجلد الهجرات: {config.MIGRATIONS_DIR}")
    migrations = sorted(p.name for p in config.MIGRATIONS_DIR.glob("*.sql"))
    print(f"الهجرات الموجودة: {migrations}")

    print("=" * 62)
    print("النتيجة:", "بيئة جاهزة" if failures == 0 else "توجد نواقص")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
