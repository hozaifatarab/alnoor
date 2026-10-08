"""خدمات المستخدمين: الحسابات، كلمات المرور، المصادقة، صلاحية آخر مدير."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from .. import config, security
from ..exceptions import (
    AuthError,
    BusinessRuleError,
    DuplicateError,
    LockedError,
    NotFoundError,
    ValidationError,
)
from ..repos import audit
from ..repos import users as repo
from .. import validators as v

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
_DT_FORMAT = "%Y-%m-%d %H:%M:%S"


def _now() -> datetime:
    return datetime.now()


def _iso(moment: datetime) -> str:
    return moment.strftime(_DT_FORMAT)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    for parser in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, parser)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def list_users(search: str | None = None, role: str | None = None) -> list[dict[str, Any]]:
    return repo.list_users(search, role)


def get_user(user_id: int) -> dict[str, Any]:
    user = repo.get(user_id)
    if user is None:
        raise NotFoundError("المستخدم غير موجود")
    return user


def _validate_username(username: str) -> str:
    username = str(username or "").strip().lower()
    if not USERNAME_RE.match(username):
        raise ValidationError("اسم المستخدم يجب أن يكون 3-32 حرفاً إنجليزياً أو رقماً بدون مسافات")
    return username


def _validate_role(role: str) -> str:
    if role not in config.ROLES:
        raise ValidationError("الدور المحدد غير معروف")
    return role


def create_user(
    username: str,
    full_name: str,
    role: str,
    password: str,
    *,
    must_change: bool = True,
    is_active: bool = True,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> int:
    username = _validate_username(username)
    full_name = v.require_text(full_name, "الاسم الكامل", min_len=3, max_len=80)
    role = _validate_role(role)
    security.validate_password_policy(password, username)
    if repo.get_by_username(username):
        raise DuplicateError(f"اسم المستخدم «{username}» مستخدم مسبقاً")
    password_hash, salt = security.hash_password(password)
    user_id = repo.create(
        username=username,
        full_name=full_name,
        role=role,
        password_hash=password_hash,
        password_salt=salt,
        is_active=1 if is_active else 0,
        must_change_password=1 if must_change else 0,
    )
    audit.log(
        "إنشاء مستخدم",
        entity="users",
        entity_id=user_id,
        details=f"{username} ({config.role_label(role)})",
        user=actor,
        ip=ip,
    )
    return user_id


def update_user(
    user_id: int,
    full_name: str,
    role: str,
    is_active: bool,
    *,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    current = get_user(user_id)
    full_name = v.require_text(full_name, "الاسم الكامل", min_len=3, max_len=80)
    role = _validate_role(role)
    loses_admin = current["role"] == config.ROLE_ADMIN and (
        role != config.ROLE_ADMIN or not is_active
    )
    if loses_admin and repo.count_admins(exclude_user_id=user_id) == 0:
        raise BusinessRuleError("لا يمكن تعطيل أو تغيير دور آخر مدير نظام فعّال")
    repo.update_profile(user_id, full_name, role, 1 if is_active else 0)
    audit.log(
        "تعديل مستخدم",
        entity="users",
        entity_id=user_id,
        details=f"{current['username']} | {config.role_label(role)} | فعّال: "
        f"{'نعم' if is_active else 'لا'}",
        user=actor,
        ip=ip,
    )


def change_password(
    user_id: int,
    new_password: str,
    *,
    must_change: bool = False,
    actor: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    user = get_user(user_id)
    security.validate_password_policy(new_password, user["username"])
    password_hash, salt = security.hash_password(new_password)
    repo.update_password(user_id, password_hash, salt, 1 if must_change else 0)
    audit.log(
        "تغيير كلمة مرور",
        entity="users",
        entity_id=user_id,
        details=user["username"],
        user=actor,
        ip=ip,
    )


def verify_own_password(user_id: int, password: str) -> bool:
    user = get_user(user_id)
    return security.verify_password(password, user["password_hash"], user["password_salt"])


def change_own_password(
    user_id: int, old_password: str, new_password: str, *, ip: str | None = None
) -> None:
    if not verify_own_password(user_id, old_password):
        raise AuthError("كلمة المرور الحالية غير صحيحة")
    change_password(user_id, new_password, must_change=False, actor=None, ip=ip)


def delete_user(
    user_id: int, *, actor: dict[str, Any] | None = None, ip: str | None = None
) -> None:
    user = get_user(user_id)
    if (actor or {}).get("id") == user_id:
        raise BusinessRuleError("لا يمكنك حذف حسابك الحالي")
    if user["role"] == config.ROLE_ADMIN and repo.count_admins(exclude_user_id=user_id) == 0:
        raise BusinessRuleError("لا يمكن حذف آخر مدير نظام فعّال")
    repo.delete(user_id)
    audit.log(
        "حذف مستخدم", entity="users", entity_id=user_id, details=user["username"], user=actor, ip=ip
    )


def authenticate(username: str, password: str, *, ip: str | None = None) -> dict[str, Any]:
    """التحقق من بيانات الدخول مع سياسة قفل الحساب.

    رسالة الفشل عامة في كل الحالات لمنع كشف وجود الحساب،
    ويرفع ``LockedError`` عند تجاوز عدد المحاولات.
    """
    username = str(username or "").strip().lower()
    user = repo.get_by_username(username)
    if user is None:
        raise AuthError("اسم المستخدم أو كلمة المرور غير صحيحة")

    locked_until = _parse(user.get("locked_until"))
    if locked_until and locked_until > _now():
        remaining = int((locked_until - _now()).total_seconds() // 60) + 1
        raise LockedError(f"الحساب مقفل مؤقتاً، أعد المحاولة بعد {remaining} دقيقة")

    if not user["is_active"]:
        raise AuthError("الحساب معطّل، راجع مدير النظام")

    if not security.verify_password(password, user["password_hash"], user["password_salt"]):
        attempts = int(user.get("failed_attempts") or 0) + 1
        if attempts >= config.MAX_LOGIN_ATTEMPTS:
            lock_until = _iso(_now() + timedelta(minutes=config.LOCK_MINUTES))
            repo.register_failure(user["id"], 0, lock_until)
            audit.log("قفل حساب", entity="users", entity_id=user["id"], details=username, ip=ip)
            raise LockedError(
                f"تم قفل الحساب {config.LOCK_MINUTES} دقيقة بعد "
                f"{config.MAX_LOGIN_ATTEMPTS} محاولات فاشلة"
            )
        repo.register_failure(user["id"], attempts, None)
        audit.log(
            "فشل تسجيل دخول",
            entity="users",
            entity_id=user["id"],
            details=f"{username} (محاولة {attempts})",
            ip=ip,
        )
        raise AuthError("اسم المستخدم أو كلمة المرور غير صحيحة")

    repo.register_success(user["id"])
    audit.log("تسجيل دخول", entity="users", entity_id=user["id"], details=username, ip=ip)
    return get_user(user["id"])


def stats() -> dict[str, Any]:
    by_role = repo.count_by_role()
    return {"total": sum(by_role.values()), "by_role": by_role, "admins": repo.count_admins()}
