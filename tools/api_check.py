"""فحص توفر أسماء محددة داخل pywebio.output (يُشغَّل عند الحاجة)."""
from __future__ import annotations

import _bootstrap  # noqa: F401  (تهيئة الترميز والمسار)

NAMES = [
    "clear",
    "clear_scope",
    "remove",
    "put_row",
    "put_column",
    "put_grid",
    "put_scope",
    "use_scope",
    "put_table",
    "put_buttons",
    "put_html",
    "put_markdown",
    "put_text",
    "put_error",
    "put_warning",
    "put_success",
    "put_info",
    "popup",
    "toast",
    "put_image",
    "put_file",
    "put_scrollable",
    "put_loading",
    "put_processbar",
    "put_collapse",
    "put_widget",
]


def main() -> int:
    from pywebio import output

    missing = []
    for name in NAMES:
        if not hasattr(output, name):
            missing.append(name)
    print("متوفرة:", len(NAMES) - len(missing), "/", len(NAMES))
    if missing:
        print("مفقودة:", ", ".join(missing))
    else:
        print("كل الأسماء المطلوبة متوفرة")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
