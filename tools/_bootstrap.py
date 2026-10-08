"""تهيئة موحّدة لأدوات سطر الأوامر: ترميز UTF-8 + إضافة جذر المشروع إلى المسار.

الاستخدام في بداية أي سكربت داخل ``tools``::

    import _bootstrap  # noqa: F401
"""
from __future__ import annotations

import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover
        pass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
