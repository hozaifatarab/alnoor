"""توليد والتحقق من رموز QR الموقعة للطلاب والبطاقات المدرسية."""
from __future__ import annotations

import io
from html import escape
from typing import Any

import segno

from core import security
from core.exceptions import ValidationError
from core.repos import settings as settings_repo

PAYLOAD_PREFIX = "STD"
SIGNATURE_LENGTH = 32


def get_qr_secret() -> str:
    """الحصول على السر المستخدم في توقيع رموز QR."""
    secret = settings_repo.get("qr_secret")
    if not secret:
        secret = security.new_secret(32)
        settings_repo.set_value("qr_secret", secret)
    return secret


def make_payload(student_no: str, year_name: str | None = None) -> str:
    """توليد حمولة موقّعة ضد التزوير لطالب:

    الصيغة: STD|YEAR|STUDENT_NO|SIGNATURE_32 (HMAC-SHA256 مختصر إلى 128 بت)
    """
    clean_no = str(student_no).strip().upper()
    if not clean_no:
        raise ValidationError("رقم الطالب مطلوب لتوليد الرمز")
    year = (year_name or "GEN").strip()
    base = f"{PAYLOAD_PREFIX}|{year}|{clean_no}"
    signature = security.hmac_sign(base, get_qr_secret(), length=SIGNATURE_LENGTH)
    return f"{base}|{signature}"


def verify_payload(
    raw_text: str, *, allow_unsigned_student_no: bool = False
) -> tuple[bool, str, str]:
    """التحقق من صحة حمولة QR المستلمة."""
    if not raw_text or not isinstance(raw_text, str):
        return False, "", "الرمز فارغ"

    text = raw_text.strip()

    # فحص صيغة الحمولة الموقعة
    if text.startswith(f"{PAYLOAD_PREFIX}|"):
        parts = text.split("|")
        if len(parts) != 4:
            return False, "", "تنسيق الرمز غير صحيح"
        _prefix, year, student_no, signature = parts
        base = f"{PAYLOAD_PREFIX}|{year}|{student_no}"
        if len(signature) != SIGNATURE_LENGTH:
            return False, student_no, "طول توقيع الرمز غير صحيح"
        if security.hmac_verify(base, signature, get_qr_secret(), length=len(signature)):
            return True, student_no, "رمز موقّع صحيح"
        return False, student_no, "توقيع الرمز غير صالح أو مزور"

    if not allow_unsigned_student_no:
        return False, "", "رموز الكاميرا يجب أن تكون موقعة من النظام"

    # Unsigned identifiers are accepted only from the explicit manual/USB path.
    clean_no = text.upper()
    valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    if len(clean_no) >= 3 and all(c in valid_chars for c in clean_no):
        return True, clean_no, "رقم أكاديمي مباشر (يدوي/قارئ USB)"

    return False, "", "رمز غير معروف"


def generate_qr_svg(payload: str, scale: int = 5) -> str:
    """توليد رمز QR بصيغة SVG نقي بدون صور نقطية."""
    qr = segno.make(payload, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", scale=scale, dark="#1e293b", light="#ffffff")
    return buf.getvalue().decode("utf-8")


def generate_qr_png_bytes(payload: str, scale: int = 8) -> bytes:
    """توليد رمز QR كبايتات PNG للعرض والتنزيل."""
    qr = segno.make(payload, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, dark="#1e293b", light="#ffffff")
    return buf.getvalue()


def generate_student_badge_html(
    student: dict[str, Any],
    class_name: str,
    institution_name: str,
    year_name: str | None = None,
) -> str:
    """إنشاء بطاقة طالب رقمية/قابلة للطباعة HTML."""
    payload = make_payload(student["student_no"], year_name)
    svg_data = generate_qr_svg(payload, scale=4)
    if "<?xml" in svg_data:
        svg_data = svg_data[svg_data.find("<svg") :]
    institution_name = escape(str(institution_name), quote=True)
    class_name = escape(str(class_name), quote=True)
    student_no = escape(str(student["student_no"]), quote=True)
    full_name = escape(str(student["full_name"]), quote=True)
    status = escape(str(student.get("status", "منتظم")), quote=True)

    return f"""
    <div style="width: 300px; border: 2px solid #cbd5e1; border-radius: 12px; padding: 14px; background: #ffffff; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); font-family: 'Cairo', sans-serif; text-align: center; margin: 8px; display: inline-block; vertical-align: top;">
        <div style="background: #0284c7; color: white; border-radius: 6px; padding: 5px; font-weight: bold; font-size: 13px; margin-bottom: 10px;">
            {institution_name}
        </div>
        <div style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 3px;">
            {full_name}
        </div>
        <div style="font-size: 12px; color: #64748b; margin-bottom: 8px;">
            الرقم: <span style="font-family: monospace; font-weight: 700; color: #0284c7;">{student_no}</span>
        </div>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 6px; margin: 0 auto 10px auto; width: 160px; height: 160px; display: flex; align-items: center; justify-content: center;">
            {svg_data}
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; color: #475569; border-top: 1px solid #f1f5f9; padding-top: 6px;">
            <span>الفصل: <strong>{class_name}</strong></span>
            <span>الحالة: <strong>{status}</strong></span>
        </div>
    </div>
    """
