"""هرم استثناءات النظام.

كل رسائل الأخطاء تُترجم في طبقة الواجهة إلى رسائل عربية واضحة للمستخدم،
ولا تُكشف أي تفاصيل تقنية (SQL أو مسارات ملفات) للمستخدم النهائي.
"""
from __future__ import annotations


class AppError(Exception):
    """الأصل لكل أخطاء النظام المتوقعة."""

    message = "حدث خطأ غير متوقع"

    def __init__(self, message: str | None = None, **context: object) -> None:
        super().__init__(message or self.message)
        self.context = context

    @property
    def user_message(self) -> str:
        return str(self)


class ValidationError(AppError):
    """مدخلات غير صحيحة قادمة من المستخدم."""

    message = "المدخلات غير صحيحة"


class NotFoundError(AppError):
    """الكيان المطلوب غير موجود."""

    message = "العنصر المطلوب غير موجود"


class DuplicateError(AppError):
    """قيمة مكرّرة تخالف قيد التفرد."""

    message = "القيمة مسجّلة مسبقاً"


class PermissionDenied(AppError):
    """المستخدم لا يملك صلاحية تنفيذ العملية."""

    message = "لا تملك صلاحية تنفيذ هذه العملية"


class BusinessRuleError(AppError):
    """العملية تخالف قاعدة أعمال (مثل تجاوز سعة الفصل)."""

    message = "لا يمكن تنفيذ العملية وفق قواعد النظام"


class AuthError(AppError):
    """فشل في عملية المصادقة."""

    message = "تعذّر تسجيل الدخول"


class LockedError(AuthError):
    """الحساب مقفل مؤقتاً بسبب المحاولات الفاشلة."""

    message = "الحساب مقفل مؤقتاً، حاول لاحقاً"
