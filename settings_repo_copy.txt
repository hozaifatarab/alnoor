"""مستودع الإعدادات (مفتاح/قيمة)."""
from __future__ import annotations

from typing import Any, Mapping

from .. import config, db


def all_settings() -> dict[str, str]:
    """كل الإعدادات مدموجة مع القيم الافتراضية."""
    values = dict(config.SETTING_DEFAULTS)
    for row in db.query_all("SELECT key, value FROM settings"):
        values[row["key"]] = row["value"]
    return values


def raw_settings() -> dict[str, str]:
    """الإعدادات المخزّنة فعلياً فقط (بدون الافتراضية)."""
    return {row["key"]: row["value"] for row in db.query_all("SELECT key, value FROM settings")}


def get(key: str, default: Any = None) -> str:
    row = db.query_one("SELECT value FROM settings WHERE key = ?", (key,))
    if row is None:
        return config.SETTING_DEFAULTS.get(key, default)
    return row["value"]


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(str(get(key, default)).strip() or default)
    except (TypeError, ValueError):
        return default


def get_float(key: str, default: float = 0.0) -> float:
    try:
        return float(str(get(key, default)).strip() or default)
    except (TypeError, ValueError):
        return default


def set_value(key: str, value: Any) -> None:
    db.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?)"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
        " updated_at = datetime('now','localtime')",
        (key, "" if value is None else str(value)),
    )


def set_many(values: Mapping[str, Any]) -> None:
    for key, value in values.items():
        set_value(key, value)


def ensure_defaults() -> list[str]:
    """إضافة الإعدادات الناقصة فقط (idempotent) وإرجاع ما أُضيف."""
    existing = raw_settings()
    added: list[str] = []
    for key, value in config.SETTING_DEFAULTS.items():
        if key not in existing:
            set_value(key, value)
            added.append(key)
    return added


def institution_name() -> str:
    return get("institution_name", config.DEFAULT_INSTITUTION_NAME) or config.DEFAULT_INSTITUTION_NAME


def currency() -> str:
    return get("currency", config.DEFAULT_CURRENCY) or config.DEFAULT_CURRENCY


def current_year_id() -> int | None:
    value = get("current_year_id", "")
    return int(value) if str(value).isdigit() else None


def current_term_id() -> int | None:
    value = get("current_term_id", "")
    return int(value) if str(value).isdigit() else None


def qr_secret() -> str:
    """سرّ توقيع بطاقات QR (يُولَّد تلقائياً عند أول استخدام)."""
    from ..security import new_secret

    secret = get("qr_secret", "")
    if not secret:
        secret = new_secret(32)
        set_value("qr_secret", secret)
    return secret
