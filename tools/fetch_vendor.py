"""تنزيل مكتبة jsQR (ماسح QR في المتصفح) إلى static/vendor للتشغيل دون إنترنت.

الاستخدام:  python tools/fetch_vendor.py
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

from pathlib import Path

import urllib.request

JSQR_URL = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"
TARGET = _bootstrap.ROOT / "static" / "vendor" / "jsQR.min.js"


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists() and TARGET.stat().st_size > 50_000:
        print(f"موجود مسبقاً: {TARGET} ({TARGET.stat().st_size} بايت)")
        return 0
    print(f"تنزيل {JSQR_URL} ...")
    try:
        with urllib.request.urlopen(JSQR_URL, timeout=60) as resp:
            data = resp.read()
        TARGET.write_bytes(data)
        print(f"تم: {len(data)} بايت -> {TARGET}")
        return 0
    except Exception as exc:  # pragma: no cover - يحتاج إنترنت
        print(f"فشل التنزيل ({exc}). سيتم استخدام CDN افتراضياً في الواجهة.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
