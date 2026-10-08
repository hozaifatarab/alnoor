"""فحص الاستيرادات غير المستخدمة في ملفات Python (تحليل AST بسيط)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def unused_imports(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    imported: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        # استيراد جانبي (.setToolTip / sys.path) أو معلّم noqa يبقى عمداً.
        segment = "\n".join(lines[node.lineno - 1 : node.end_lineno])
        if "noqa" in segment:
            continue
        for alias in node.names:
            if alias.name == "*":
                continue
            name = (alias.asname or alias.name).split(".")[0]
            imported[name] = node.lineno
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            inner: ast.AST = node
            while isinstance(inner, ast.Attribute):
                inner = inner.value
            if isinstance(inner, ast.Name):
                used.add(inner.id)
    return sorted(
        f"{name} (سطر {line})" for name, line in imported.items() if name not in used
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        print("الاستخدام: python tools\\_unused_imports.py <file.py> [...]")
        return 2
    status = 0
    paths: list[Path] = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if any(ch in arg for ch in "*?["):
            paths.extend(sorted(Path().glob(arg)))
        elif p.is_dir():
            paths.extend(sorted(p.rglob("*.py")))
        else:
            paths.append(p)
    if not paths:
        print("لا توجد ملفات مطابقة")
        return 2
    for path in paths:
        unused = unused_imports(path)
        if unused:
            status = 1
            print(f"{path}: غير مستخدم -> {', '.join(unused)}")
        else:
            print(f"{path}: OK")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
