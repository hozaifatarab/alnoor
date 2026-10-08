"""فحص حيّ (E2E): تسجيل دخول فعلي عبر بروتوكول PyWebIO WebSocket.

الخطوات:
1. الاتصال بالجلسة وانتظار نموذج الدخول (input_group).
2. إرسال بيانات المستخدم admin عبر حدث from_submit.
3. التحقق من رسالة الترحيب ونموذج تغيير كلمة المرور الإلزامي.

لا يُغيّر كلمة المرور — يترك ذلك للمستخدم في المتصفح.
"""
from __future__ import annotations

import asyncio
import json
import sys
from inspect import signature
from typing import Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = "ws://127.0.0.1:8080/?app=index"
HEADERS = {"Origin": "http://127.0.0.1:8080"}
# بيانات الدخول تُمرَّر من سطر الأوامر ولا تُخزَّن في الملف:
#     python tools/_session_check.py <username> <password>
USERNAME = sys.argv[1] if len(sys.argv) >= 3 else ""
PASSWORD = sys.argv[2] if len(sys.argv) >= 3 else ""


async def main() -> int:
    import websockets

    if not USERNAME or not PASSWORD:
        print("الاستخدام: python tools/_session_check.py <username> <password>")
        return 2

    kwargs: dict[str, object] = {}
    params = signature(websockets.connect).parameters
    if "origin" in params:
        kwargs["origin"] = HEADERS["Origin"]
    elif "additional_headers" in params:
        kwargs["additional_headers"] = HEADERS
    elif "extra_headers" in params:
        kwargs["extra_headers"] = HEADERS
    if "proxy" in params:
        kwargs["proxy"] = None  # تعطيل وكيل النظام (socks://127.0.0.1)

    loop = asyncio.get_running_loop()
    commands: list[dict] = []

    async def wait_for(ws, predicate: Callable[[dict], bool], timeout: float) -> dict | None:
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            remaining = max(0.1, deadline - loop.time())
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                return None
            if not isinstance(raw, str):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            commands.append(msg)
            if predicate(msg):
                return msg
        return None

    try:
        async with websockets.connect(URL, **kwargs) as ws:
            # المرحلة 1: نموذج الدخول
            form1 = await wait_for(
                ws, lambda m: m.get("command") == "input_group", timeout=8
            )
            if form1 is None:
                print("فشل: نموذج الدخول لم يصل ✗")
                print("الأوامر:", [m.get("command") for m in commands])
                return 2
            print("1) نموذج الدخول ظهر ✓ —", (form1.get("spec") or {}).get("label"))

            # المرحلة 2: إرسال بيانات الدخول
            await ws.send(
                json.dumps(
                    {
                        "task_id": form1.get("task_id"),
                        "event": "from_submit",
                        "data": {"username": USERNAME, "password": PASSWORD},
                    },
                    ensure_ascii=False,
                )
            )
            print("2) أُرسلت بيانات الدخول...")

            welcome = await wait_for(
                ws,
                lambda m: "مرحباً بك" in json.dumps(m, ensure_ascii=False),
                timeout=6,
            )
            if welcome is None:
                print("فشل: لم تصل رسالة الترحيب ✗")
                print("الأوامر:", [m.get("command") for m in commands])
                errs = [
                    json.dumps(m, ensure_ascii=False)[:200]
                    for m in commands
                    if "⚠" in json.dumps(m, ensure_ascii=False)
                    or m.get("command") == "toast"
                ]
                if errs:
                    print("رسائل خطأ:", errs)
                return 3
            print("3) رسالة الترحيب وصلت ✓ (الدخول ناجح)")

            # المرحلة 3: نموذج تغيير كلمة المرور الإلزامي
            form2 = await wait_for(
                ws, lambda m: m.get("command") == "input_group", timeout=6
            )
            if form2 is None:
                print("فشل: نموذج تغيير كلمة المرور لم يصل ✗")
                print("الأوامر:", [m.get("command") for m in commands])
                return 4
            fields = (form2.get("spec") or {}).get("inputs") or []
            names = [f.get("name") for f in fields]
            print("4) نموذج تغيير كلمة المرور الإلزامي ظهر ✓ — الحقول:", names)
            print("نتيجة: مسار الدخول الكامل يعمل ✓✓")
            return 0
    except Exception as exc:
        print("فشل الاتصال بالخادم:", exc)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
