"""تحقق المدخلات وتطبيعها.

كل الدوال ترفع ``ValidationError`` برسالة عربية واضحة،
وتُعيد قيمة منظَّفة جاهزة للتخزين.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Iterable, Sequence

from .exceptions import ValidationError

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_DATE_PATTERNS = ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


def normalize_digits(text: str) -> str:
    """تحويل الأرقام العربية إلى لاتينية (تجربة عربية أفضل)."""
    return (text or "").translate(_ARABIC_DIGITS)


def require_text(value: Any, field: str, min_len: int = 1, max_len: int = 120) -> str:
    text = normalize_digits(str(value or "")).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) < min_len:
        raise ValidationError(f"حقل «{field}» مطلوب")
    if len(text) > max_len:
        raise ValidationError(f"حقل «{field}» أطول من المسموح ({max_len} حرفاً)")
    return text


def optional_text(value: Any, max_len: int = 200) -> str | None:
    text = normalize_digits(str(value or "")).strip()
    if not text:
        return None
    if len(text) > max_len:
        raise ValidationError(f"النص أطول من المسموح ({max_len} حرفاً)")
    return text


def require_choice(value: Any, field: str, choices: Sequence[str]) -> str:
    text = require_text(value, field, max_len=40)
    if text not in choices:
        raise ValidationError(f"قيمة «{field}» غير مسموح بها")
    return text


def parse_int(
    value: Any,
    field: str,
    minimum: int | None = None,
    maximum: int | None = None,
    default: int | None = None,
) -> int:
    raw = normalize_digits(str("" if value is None else value)).strip()
    if not raw:
        if default is not None:
            return default
        raise ValidationError(f"حقل «{field}» مطلوب")
    try:
        number = int(float(raw))
    except ValueError as exc:
        raise ValidationError(f"حقل «{field}» يجب أن يكون رقماً صحيحاً") from exc
    if minimum is not None and number < minimum:
        raise ValidationError(f"حقل «{field}» لا يقل عن {minimum}")
    if maximum is not None and number > maximum:
        raise ValidationError(f"حقل «{field}» لا يزيد عن {maximum}")
    return number


def parse_money(value: Any, field: str, minimum: float = 0.0) -> float:
    raw = normalize_digits(str("" if value is None else value)).replace(",", "").replace(" ", "")
    if not raw:
        return 0.0
    try:
        amount = round(float(raw), 2)
    except ValueError as exc:
        raise ValidationError(f"حقل «{field}» يجب أن يكون مبلغاً رقمياً") from exc
    if amount < minimum:
        raise ValidationError(f"حقل «{field}» لا يقل عن {minimum}")
    return amount


def parse_float(
    value: Any,
    field: str,
    minimum: float | None = None,
    maximum: float | None = None,
    default: float = 0.0,
) -> float:
    raw = normalize_digits(str("" if value is None else value)).strip()
    if not raw:
        return default
    try:
        number = float(raw)
    except ValueError as exc:
        raise ValidationError(f"حقل «{field}» يجب أن يكون رقماً") from exc
    if minimum is not None and number < minimum:
        raise ValidationError(f"حقل «{field}» لا يقل عن {minimum}")
    if maximum is not None and number > maximum:
        raise ValidationError(f"حقل «{field}» لا يزيد عن {maximum}")
    return number


def parse_date(value: Any, field: str, required: bool = True) -> str | None:
    """إرجاع التاريخ بصيغة ISO أو None."""
    raw = normalize_digits(str(value or "")).strip()
    if not raw:
        if required:
            raise ValidationError(f"حقل «{field}» مطلوب (بصيغة يوم/شهر/سنة)")
        return None
    for pattern in _DATE_PATTERNS:
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            continue
    raise ValidationError(f"تاريخ «{field}» غير صحيح، استخدم الصيغة 2026-09-01")


def parse_time(value: Any, field: str, default: str = "07:30") -> str:
    raw = normalize_digits(str(value or "")).strip()
    if not raw:
        return default
    if not _TIME_RE.match(raw):
        raise ValidationError(f"وقت «{field}» غير صحيح، استخدم الصيغة 07:30")
    return raw


def validate_national_id(value: Any, required: bool = False) -> str | None:
    raw = normalize_digits(str(value or "")).strip()
    if not raw:
        if required:
            raise ValidationError("رقم الهوية مطلوب")
        return None
    if not raw.isdigit() or not (8 <= len(raw) <= 14):
        raise ValidationError("رقم الهوية يجب أن يكون من 8 إلى 14 رقماً")
    return raw


def validate_phone(value: Any, required: bool = False) -> str | None:
    raw = normalize_digits(str(value or "")).strip().replace(" ", "").replace("-", "")
    if not raw:
        if required:
            raise ValidationError("رقم الجوال مطلوب")
        return None
    if raw.startswith("+"):
        raw = raw[1:]
    if not raw.isdigit() or not (7 <= len(raw) <= 15):
        raise ValidationError("رقم الجوال غير صحيح (7 إلى 15 رقماً)")
    return raw


def validate_email(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if not _EMAIL_RE.match(raw):
        raise ValidationError("البريد الإلكتروني غير صحيح")
    return raw


def parse_holidays(value: Any) -> list[str]:
    """تحويل أيام العطلة (نص مفصول بفواصل أو قائمة) إلى تواريخ ISO منظّفة."""
    if not value:
        return []
    items: Iterable[Any] = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    days: list[str] = []
    for item in items:
        text = normalize_digits(str(item)).strip()
        if not text:
            continue
        try:
            days.append(datetime.strptime(text, "%Y-%m-%d").date().isoformat())
        except ValueError as exc:
            raise ValidationError(f"تاريخ عطلة غير صحيح: {text}") from exc
    return sorted(set(days))


def today_iso() -> str:
    return date.today().isoformat()


def join_nonempty(items: Iterable[str], sep: str = " ") -> str:
    return sep.join(part for part in items if part)
