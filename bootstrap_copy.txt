"""تهيئة أول تشغيل: إنشاء مدير النظام الافتراضي إذا لم يوجد أي مستخدم."""
from __future__ import annotations

import logging

from . import security
from .repos import audit
from .repos import settings as settings_repo
from .repos import users as users_repo

logger = logging.getLogger(__name__)

FIRST_RUN_USERNAME = "admin"
FIRST_RUN_PASSWORD = "Manager#2026"


def ensure_initial_admin() -> dict[str, str] | None:
    """إنشاء حساب المدير الأول عند قاعدة بيانات فارغة.

    يُعيد بيانات الحساب المُنشأ (لطباعتها مرة واحدة) أو None إن كان هناك مستخدمون.
    """
    if users_repo.list_users():
        return None
    password_hash, salt = security.hash_password(FIRST_RUN_PASSWORD)
    user_id = users_repo.create(
        username=FIRST_RUN_USERNAME,
        full_name="مدير النظام",
        role="admin",
        password_hash=password_hash,
        password_salt=salt,
        is_active=1,
        must_change_password=1,
    )
    audit.log(
        "تهيئة أولى",
        entity="users",
        entity_id=user_id,
        details="إنشاء حساب المدير الافتراضي (تغيير كلمة المرور مطلوب عند أول دخول)",
    )
    settings_repo.ensure_defaults()
    logger.warning("تم إنشاء حساب المدير الافتراضي: %s", FIRST_RUN_USERNAME)
    return {"username": FIRST_RUN_USERNAME, "password": FIRST_RUN_PASSWORD}
