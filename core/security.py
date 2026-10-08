"""الأمان: تشفير كلمات المرور، التوقيع، وسياسات الحماية.

* كلمات المرور: PBKDF2-HMAC-SHA256 بملح عشوائي لكل مستخدم ومقارنة زمنية ثابتة.
* التوقيع: HMAC-SHA256 (يُستخدم لتوقيع حمولة بطاقات QR في المرحلة 2).
"""
from __future__ import annotations

import binascii
import hashlib
import hmac
import secrets

from . import config
from .exceptions import ValidationError


def new_salt() -> str:
    """ملح عشوائي بصيغة hex."""
    return secrets.token_hex(16)


def new_secret(length: int = 32) -> str:
    """سرّ عشوائي آمن (لمفاتيح النظام مثل مفتاح توقيع QR)."""
    return secrets.token_hex(length)

def hash_password(
    password: str,
    salt: str | None = None,
    iterations: int | None = None,
) -> tuple[str, str]:
    """إرجاع (الهاش, الملح). عدد التكرارات يُقرأ من الإعدادات عند التنفيذ."""
    salt = salt or new_salt()
    rounds = iterations or config.pbkdf2_iterations()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), rounds
    )
    return digest.hex(), salt



def verify_password(
    password: str,
    password_hash: str,
    salt: str,
    iterations: int | None = None,
) -> bool:
    """تحقق زمني ثابت من كلمة المرور."""
    try:
        candidate, _ = hash_password(password, salt=salt, iterations=iterations)
    except (ValueError, binascii.Error):  # ملح تالف
        return False
    return hmac.compare_digest(candidate, password_hash or "")


def validate_password_policy(password: str, username: str = "") -> None:
    """سياسة كلمة المرور: الطول + حرف + رقم + عدم التطابق مع اسم المستخدم."""
    password = password or ""
    if len(password) < config.MIN_PASSWORD_LENGTH:
        raise ValidationError(f"كلمة المرور يجب أن تكون {config.MIN_PASSWORD_LENGTH} أحرف على الأقل")
    if not any(ch.isalpha() for ch in password):
        raise ValidationError("كلمة المرور يجب أن تحتوي على حرف واحد على الأقل")
    if not any(ch.isdigit() for ch in password):
        raise ValidationError("كلمة المرور يجب أن تحتوي على رقم واحد على الأقل")
    if username and username.lower() in password.lower():
        raise ValidationError("كلمة المرور يجب ألّا تحتوي على اسم المستخدم")


def hmac_sign(payload: str, secret: str, length: int = 10) -> str:
    """توقيع مختصر لحمولة نصية (يُستخدم لرموز QR)."""
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:length]


def hmac_verify(payload: str, signature: str, secret: str, length: int = 10) -> bool:
    """تحقق زمني ثابت من التوقيع."""
    return hmac.compare_digest(hmac_sign(payload, secret, length), signature or "")
