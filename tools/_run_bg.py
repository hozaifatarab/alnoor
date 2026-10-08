"""تشغيل أمر في عملية خلفية معزولة وكتابة مخرجاته إلى ملف (تجاوز لبطء الطرفية)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: _run_bg.py <logfile> <unittest-args...>")
        return 2
    log_path = ROOT / sys.argv[1]
    args = sys.argv[2:]
    if args[:1] == ["-m"]:
        cmd = [sys.executable, "-m", *args[1:]]
    else:
        cmd = [sys.executable, *args]
    import os
    env = dict(os.environ)
    if args[:1] == ["-m"]:
        # تسريع الاختبارات فقط — لا يُستخدم أبداً لتشغيل الخادم الفعلي،
        # لأن عدد التكرارات يجب أن يطابق القيمة التي هُشّت بها كلمات المرور
        # المخزنة في قاعدة البيانات (الافتراضي 200000).
        env.setdefault("INST_PBKDF2_ITERATIONS", "1000")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    out = open(log_path, "w", encoding="utf-8", errors="replace")
    creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=out,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env=env,
        creationflags=creationflags,
        close_fds=True,
    )
    print("started")
    return 0


if __name__ == "__main__":
    sys.exit(main())
