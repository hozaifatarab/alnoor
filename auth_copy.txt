"""طبقة المصادقة المرتبطة بجلسة PyWebIO + حماية الشاشات بالصلاحيات."""
from __future__ import annotations

import logging
import base64
import time
from http.cookies import SimpleCookie
from functools import wraps
from typing import Any, Callable

from . import config, db, security
from .exceptions import AppError, NotFoundError, PermissionDenied
from .repos import audit
from .repos import settings as settings_repo
from .services import users_service

logger = logging.getLogger(__name__)
AUTH_COOKIE = "inst_auth"
AUTH_SESSION_SECONDS = 8 * 60 * 60


def client_ip() -> str | None:
    """عنوان المستخدم الحالي (إن توفّر)."""
    try:
        from pywebio.session import get_info

        return get_info().user_ip
    except Exception:  # pragma: no cover - خارج سياق جلسة
        return None


def _session_local() -> Any:
    from pywebio.session import local

    return local


def _session_secret() -> str:
    """Get or initialize the secret used to sign cross-app session cookies."""
    with db.transaction() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", ("auth_secret",)).fetchone()
        if row and row["value"]:
            return str(row["value"])

        secret = security.new_secret(32)
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = datetime('now','localtime')",
            ("auth_secret", secret),
        )
        return secret


def _make_session_token(user: dict[str, Any]) -> str:
    secret = _session_secret()
    password_fingerprint = security.hmac_sign(user["password_hash"], secret, length=64)
    payload = f"{int(user['id'])}:{int(time.time()) + AUTH_SESSION_SECONDS}:{password_fingerprint}"
    encoded = base64.urlsafe_b64encode(payload.encode("ascii")).decode("ascii").rstrip("=")
    signature = security.hmac_sign(encoded, secret, length=64)
    return f"{encoded}.{signature}"


def _user_from_session_token(token: str | None) -> dict[str, Any] | None:
    if not token or len(token) > 512 or "." not in token:
        return None
    encoded, signature = token.split(".", 1)
    secret = _session_secret()
    if not security.hmac_verify(encoded, signature, secret, length=64):
        return None
    try:
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("ascii")
        user_id_text, expires_text, password_fingerprint = payload.split(":", 2)
        user_id = int(user_id_text)
        if int(expires_text) <= int(time.time()):
            return None
    except (ValueError, UnicodeError):
        return None

    try:
        user = users_service.get_user(user_id)
    except NotFoundError:
        return None
    if not user["is_active"] or not security.hmac_verify(
        user["password_hash"], password_fingerprint, secret, length=64
    ):
        return None
    return user


def _request_auth_cookie() -> str | None:
    try:
        from pywebio.session import get_info

        cookie = SimpleCookie()
        cookie.load(get_info().request.headers.get("Cookie", ""))
        morsel = cookie.get(AUTH_COOKIE)
        return morsel.value if morsel else None
    except Exception:  # pragma: no cover - خارج سياق جلسة
        return None


def _write_auth_cookie(token: str, max_age: int) -> None:
    from pywebio.session import get_info, run_js

    secure = "; Secure" if getattr(get_info().request, "protocol", "") == "https" else ""
    run_js(
        f"document.cookie = '{AUTH_COOKIE}={token}; Path=/; SameSite=Lax; "
        f"Max-Age={max_age}{secure}'"
    )


def current_user() -> dict[str, Any] | None:
    """المستخدم الحالي من الجلسة، مع تحديث حالته من قاعدة البيانات."""
    try:
        local = _session_local()
    except Exception:  # pragma: no cover
        return None
    user_id = getattr(local, "user_id", None)
    if user_id:
        try:
            user = users_service.get_user(int(user_id))
        except NotFoundError:
            user = None
    else:
        token = _request_auth_cookie()
        user = _user_from_session_token(token)
        if user:
            local.user_id = int(user["id"])
            local.username = user["username"]
        elif token:
            _clear_session()
    if not user:
        return None
    if not user or not user["is_active"]:
        _clear_session()
        return None
    return user


def _clear_session() -> None:
    try:
        local = _session_local()
        local.user_id = None
    except Exception:  # pragma: no cover
        pass
    try:
        _write_auth_cookie("", 0)
    except Exception:  # pragma: no cover - خارج سياق جلسة
        pass


def is_authenticated() -> bool:
    return current_user() is not None


def _clean_credential(value: str) -> tuple[str, bool, bool]:
    """إزالة المسافات والأحرف الخفية (RTL marks / zero-width) من بيانات الدخول.

    يعيد (القيمة النظيفة، هل وُجدت أحرف خفية، هل وُجدت أرقام عربية-هندية).
    """
    invisible = set("\u200e\u200f\u200b\u200c\u200d\ufeff\u00a0")
    had_invisible = any(ch in invisible for ch in value)
    had_arabic_digits = any("\u0660" <= ch <= "\u0669" or "\u06f0" <= ch <= "\u06f9" for ch in value)
    cleaned = "".join(ch for ch in value if ch not in invisible)
    # تحويل الأرقام العربية/الفارسية إلى ASCII (لوحة المفاتيح العربية)
    cleaned = "".join(chr(ord(ch) - 0x0660 + ord("0")) if "\u0660" <= ch <= "\u0669" else ch for ch in cleaned)
    cleaned = "".join(chr(ord(ch) - 0x06f0 + ord("0")) if "\u06f0" <= ch <= "\u06f9" else ch for ch in cleaned)
    return cleaned.strip(), had_invisible, had_arabic_digits


def login(username: str, password: str, *, remember_app: str | None = None) -> dict[str, Any]:
    """تسجيل الدخول: تحقق + تخزين الجلسة + تدقيق."""
    ip = client_ip()
    username, u_dirty, u_ar = _clean_credential(username)
    password, p_dirty, p_ar = _clean_credential(password)
    try:
        user = users_service.authenticate(username, password, ip=ip)
    except AppError as exc:
        logger.warning(
            "login failed: %r من %s (%s) | len=%d hidden_chars=%s arabic_digits=%s",
            username,
            ip,
            exc.user_message,
            len(password),
            u_dirty or p_dirty,
            u_ar or p_ar,
        )
        raise
    local = _session_local()
    local.user_id = int(user["id"])
    local.username = user["username"]
    local.login_app = remember_app
    _write_auth_cookie(_make_session_token(user), AUTH_SESSION_SECONDS)
    logger.info("login ok: %s من %s", user["username"], ip)
    return user


def logout(*, actor: dict[str, Any] | None = None) -> None:
    user = actor or current_user()
    if user:
        audit.log(
            "تسجيل خروج", entity="users", entity_id=user["id"], details=user["username"], ip=client_ip()
        )
    _clear_session()


def permissions_of(user: dict[str, Any] | None) -> frozenset[str]:
    if not user:
        return frozenset()
    return config.PERMISSION_MATRIX.get(user["role"], frozenset())


def can(permission: str, user: dict[str, Any] | None = None) -> bool:
    user = user or current_user()
    return config.can((user or {}).get("role"), permission)


def require(permission: str, user: dict[str, Any] | None = None) -> dict[str, Any]:
    """يرفع ``PermissionDenied`` إن لم يملك المستخدم الصلاحية."""
    user = user or current_user()
    if not user:
        raise PermissionDenied("يجب تسجيل الدخول أولاً")
    if not can(permission, user):
        audit.log(
            "رفض صلاحية",
            entity="permissions",
            entity_id=permission,
            details=f"{user['username']} حاول الوصول إلى {permission}",
            user=user,
            ip=client_ip(),
        )
        raise PermissionDenied("لا تملك صلاحية الوصول إلى هذه الشاشة")
    return user


def login_required(*permissions: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """مُزيِّن شاشات PyWebIO: يتطلب تسجيل الدخول (وصلاحيات محددة إن وُجدت).

    * غير المُسجَّل → تُعرض شاشة الدخول.
    * صاحب كلمة مرور مؤقتة → تُعرض شاشة تغيير كلمة المرور إلزامياً.
    * بلا صلاحية → رسالة واضحة + تسجيل في سجل التدقيق.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            user = current_user()
            if user is None:
                from pages import login as login_page

                login_page.render_login_form(notice="يجب تسجيل الدخول للمتابعة")
                return None

            if user["must_change_password"]:
                from pages import profile as profile_page

                profile_page.render_change_password(force=True)
                return None

            try:
                for permission in permissions:
                    require(permission, user)
            except PermissionDenied as exc:
                from ui import layout

                layout.page_header(user, active=None)
                layout.alert(str(exc), kind="error")
                layout.back_home()
                return None

            return func(*args, **kwargs)

        return wrapper

    return decorator


def home_app_for(user: dict[str, Any] | None) -> str:
    """أول شاشة مسموحة للمستخدم (بعد الدخول)."""
    if not user:
        return "index"
    if config.can(user["role"], config.PERM_DASHBOARD):
        return "dashboard"
    return "my_account"


def institution_name() -> str:
    return settings_repo.institution_name()
