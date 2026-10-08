"""فحص بيئة المرحلة 2: إصدار PyWebIO، توفر eval_js، تنزيل jsQR محلياً. (مؤقت)"""
from __future__ import annotations

import inspect
import urllib.request
from pathlib import Path

import pywebio
import pywebio.session as s

print("pywebio:", pywebio.__version__)
print("eval_js:", inspect.signature(s.eval_js))
print("has run_js:", hasattr(s, "run_js"))

vendor = Path("static/vendor/jsQR.min.js")
vendor.parent.mkdir(parents=True, exist_ok=True)
if vendor.exists() and vendor.stat().st_size > 10000:
    print("jsQR present:", vendor.stat().st_size)
else:
    url = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"
    try:
        data = urllib.request.urlopen(url, timeout=25).read()
        vendor.write_bytes(data)
        print("jsQR downloaded:", len(data))
    except Exception as exc:
        print("jsQR download FAILED:", exc)
