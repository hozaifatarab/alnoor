"""شاشة الحساب الشخصي: تغيير كلمة المرور + معلومات الجلسة."""
from __future__ import annotations

from typing import Any

from pywebio.input import PASSWORD, input, input_group
from pywebio.output import put_error, put_success
from pywebio.session import go_app

from core import auth, config
from core.services import users_service
from ui import components, layout


def render_change_password(force: bool = False, user: dict[str, Any] | None = None) -> None:
    """نموذج تغيير كلمة المرور (إلزامي عند أول دخول أو بعد إعادة تعيين)."""
    user = user or auth.current_user()
    if user is None:
        from pages import login

        login.render_login_form(notice="يجب تسجيل الدخول للمتابعة")
        return

    layout.page_header(user, active="my_account", subtitle="تغيير كلمة المرور")
    if force:
        layout.alert(
            "لأسباب أمنية يجب تغيير كلمة المرور المؤقتة قبل استخدام النظام.", "warn"
        )
    layout.section("كلمة المرور", f"الحد الأدنى {config.MIN_PASSWORD_LENGTH} أحرف مع حرف ورقم")
    components.password_toggle_hint()

    with components.error_boundary("تغيير كلمة المرور"):
        fields: list[dict[str, Any]] = []
        if not force:
            fields.append(input("كلمة المرور الحالية", name="old", type=PASSWORD, required=True))
        fields.append(input("كلمة المرور الجديدة", name="new", type=PASSWORD, required=True))
        fields.append(input("تأكيد كلمة المرور الجديدة", name="confirm", type=PASSWORD, required=True))
        data = input_group("", fields, cancelable=not force)
        if data is None and not force:
            return
        if data is None:
            data = {"old": None, "new": "", "confirm": ""}

        if data["new"] != data["confirm"]:
            put_error("⚠ كلمتا المرور غير متطابقتين")
            return

        if force or data.get("old") is None:
            users_service.change_password(
                int(user["id"]),
                data["new"],
                must_change=False,
                actor=user,
                ip=auth.client_ip(),
            )
        else:
            users_service.change_own_password(
                int(user["id"]), data["old"], data["new"], ip=auth.client_ip()
            )
        put_success("تم تغيير كلمة المرور بنجاح")
        if force:
            go_app(auth.home_app_for(user), new_window=False)
            return
        _render_account_card(user)


def my_account() -> None:
    """شاشة الحساب الشخصي."""
    user = auth.current_user()
    if user is None:
        from pages import login

        login.render_login_form(notice="يجب تسجيل الدخول للمتابعة")
        return
    if user["must_change_password"]:
        render_change_password(force=True, user=user)
        return
    layout.page_header(user, active="my_account", subtitle="حسابي")
    _render_account_card(user)
    if components.confirm("هل تريد تسجيل الخروج من النظام؟", "خروج", "بقاء"):
        auth.logout(actor=user)
        go_app("index", new_window=False)


def _render_account_card(user: dict[str, Any]) -> None:
    perms = sorted(auth.permissions_of(user))
    layout.section("بيانات الحساب")
    components.kv_table(
        [
            ("الاسم الكامل", user["full_name"]),
            ("اسم المستخدم", user["username"]),
            ("الدور", config.role_label(user["role"])),
            ("آخر دخول", user.get("last_login") or "—"),
            ("عدد الصلاحيات", len(perms)),
            ("كلمة مرور مؤقتة", "نعم" if user["must_change_password"] else "لا"),
        ]
    )
    layout.section("الصلاحيات المتاحة", "تُدار الصلاحيات من شاشة المستخدمين")
    components.table(["الصلاحية", "الحالة"], [[perm, components.chip("ممنوحة", "ok")] for perm in perms])
