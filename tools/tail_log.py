"""عرض آخر أسطر من ملف السجل."""
import _bootstrap  # noqa: F401
import sys
from pathlib import Path

target = Path(sys.argv[1] if len(sys.argv) > 1 else "data/testrun.log")
if not target.exists():
    print(f"الملف غير موجود: {target}")
    sys.exit(1)

lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
print(f"إجمالي الأسطر: {len(lines)}")
for line in lines[-25:]:
    print(line)
