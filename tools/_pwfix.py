"""أداة مؤقتة: توحيد كلمات مرور الاختبارات (تُحذف بعد الاستخدام)."""
from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path

TARGET = Path(_bootstrap.ROOT) / "tests" / "test_auth.py"
REPLACEMENTS = {
    "Admin@1234": "Manager#2026",
    "Admin@2222": "Manager#2222",
    "Operator@1": "Operator#2026",
}


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS.items():
        count = text.count(old)
        text = text.replace(old, new)
        print(f"{old} → {new} : {count} مرة")
    TARGET.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
