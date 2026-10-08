"""إعداد السجلات (Logging): ملف دوّار بترميز UTF-8 + مخرَج للطرفية آمن من الأخطاء."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config

_configured = False


def log_file_path() -> Path:
    return config.data_dir() / "app.log"


def setup_logging(level: int = logging.INFO) -> Path:
    """تهيئة السجلات مرة واحدة لكل عملية."""
    global _configured
    path = log_file_path()
    if _configured:
        return path

    root = logging.getLogger()
    root.setLevel(level)

    file_handler = RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    )
    root.addHandler(file_handler)

    stream = logging.StreamHandler(sys.stdout)
    try:  # النافذة على ويندوز قد تكون cp1252 فلا تُطبع العربية
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):  # pragma: no cover
        pass
    stream.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    root.addHandler(stream)

    logging.getLogger("tornado.access").setLevel(logging.WARNING)
    _configured = True
    logging.getLogger(__name__).info("تم تهيئة السجلات في %s", path)
    return path
