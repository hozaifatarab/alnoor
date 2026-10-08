"""شاشة المستخدمين: إنشاء الحسابات، الأدوار، إعادة تعيين كلمة المرور، الحذف."""
from __future__ import annotations

from typing import Any

from pywebio.input import PASSWORD, input, input_group, select
from pywebio.output import put_buttons, put_html
from pywebio.pin import pin, put_select
from pywebio.session import go_app

from core import auth, config, security
from core.services import users_service
from ui import components, layout, options

APP = "users"


def users() -> None:
    """شاشة إدارة المستخدمين والصلاحيات."""
    user = auth.current_user()
    layout.page_header(user, active=APP, subtitle="المستخدمون والصلاحيات")
    with components.error_boundary("شاشة المستخدمين"):
        filters = input_group(
            "تصفية",
            [
                input("بحث (الاسم/اسم المستخدم)", name="search", required=False),
                select("الدور", name="role", options=options.roles("الكل"), required=False),
            ],
            cancelable=False,
        )
        rows = users_service.list_users(
            (filters.get("search") or "").strip() or None, filters.get("role") or None
        )
        _render_table(rows)
        _render_actions(rows)


def _render_table(rows: list[dict[str, Any]]) -> None:
    layout.section("قائمة المستخدمين", f"عدد النتائج: {len(rows)}")
    components.table(
        ["اسم المستخدم", "الاسم الكامل", "الدور", "الصلاحيات", "آخر دخول", "كلمة مرور مؤقتة", "الحالة"],
        [
            [
                row["username"],
                row["full_name"],
                config.role_label(row["role"]),
                len(config.PERMISSION_MATRIX.get(row["role"], frozenset())),
                row.get("last_login") or "—",
                "نعم" if row["must_change_password"] else "لا",
                components.chip(
                    "فعّال" if row["is_active"] else "معطّل", "ok" if row["is_active"] else "bad"
                ),
            ]
            for row in rows
        ],
        empty_message="لا يوجد مستخدمون مطابقون للتصفية",
    )


def _render_actions(rows: list[dict[str, Any]]) -> None:
    layout.section("إجراءات", "اختر المستخدم ثم الإجراء المطلوب")
    if rows:
        put_select(
            "user_pick",
            options=[
                {"label": f"{row['full_name']} ({row['username']})", "value": str(row["id"])}
                for row in rows
            ],
            label="المستخدم",
        )
    else:
        put_html('<div class="section-hint">لا يوجد مستخدمون لعرض إجراءاتهم.</div>')
    put_buttons(
        [
            {"label": "➕ مستخدم جديد", "value": "add", "color": "primary"},
            {"label": "✎ تعديل", "value": "edit", "color": "secondary"},
            {"label": "🔑 كلمة مرور جديدة", "value": "reset", "color": "secondary"},
            {"label": "⏻ إيقاف/تنشيط", "value": "toggle", "color": "secondary"},
            {"label": "🗑 حذف", "value": "delete", "color": "danger"},
        ],
        onclick=_handle,
        small=True,
    )
    layout.footer()


def _handle(value: str) -> None:
    if value == "add":
        _create()
        return
    picked = pin["user_pick"]
    if not picked:
        components.toast_error("اختر المستخدم أولاً")
        return
    user_id = int(picked)
    if value == "edit":
        _edit(user_id)
    elif value == "reset":
        _reset_password(user_id)
    elif value == "toggle":
        _toggle(user_id)
    elif value == "delete":
        _delete(user_id)


def _create() -> None:
    data = components.form_modal(
        "إنشاء مستخدم جديد",
        [
            input("اسم المستخدم *", name="username", required=True, help_text="حروف إنجليزية/أرقام"),
            input("الاسم الكامل *", name="full_name", required=True),
            select("الدور *", name="role", options=options.roles(), required=True),
            input(
                f"كلمة المرور المؤقتة * ({config.MIN_PASSWORD_LENGTH}+ حرف ورقم)",
                name="password",
                type=PASSWORD,
                required=True,
            ),
        ],
        size="large",
    )
    if not data:
        return
    with components.error_boundary("إنشاء مستخدم"):
        users_service.create_user(
            data["username"],
            data["full_name"],
            data["role"],
            data["password"],
            must_change=True,
            actor=auth.current_user(),
            ip=auth.client_ip(),
        )
        components.toast_ok("تم إنشاء المستخدم (سيُطلب تغيير كلمة المرور عند أول دخول)")
        go_app(APP, new_window=False)


def _edit(user_id: int) -> None:
    target = users_service.get_user(user_id)
    data = components.form_modal(
        f"تعديل: {target['username']}",
        [
            input("الاسم الكامل *", name="full_name", value=target["full_name"], required=True),
            select(
                "الدور *",
                name="role",
                options=[{"label": config.role_label(role), "value": role} for role in config.ROLES],
                value=target["role"],
                required=True,
            ),
            select(
                "الحالة",
                name="is_active",
                options=[{"label": "فعّال", "value": "1"}, {"label": "معطّل", "value": "0"}],
                value="1" if target["is_active"] else "0",
                required=True,
            ),
        ],
    )
    if not data:
        return
    with components.error_boundary("تعديل مستخدم"):
        users_service.update_user(
            user_id,
            data["full_name"],
            data["role"],
            is_active=data["is_active"] == "1",
            actor=auth.current_user(),
            ip=auth.client_ip(),
        )
        components.toast_ok("تم حفظ التعديلات")
        go_app(APP, new_window=False)


def _reset_password(user_id: int) -> None:
    target = users_service.get_user(user_id)
    suggested = security.new_secret(6).upper() + "a1"
    data = components.form_modal(
        f"إعادة تعيين كلمة مرور: {target['username']}",
        [
            input(
                "كلمة المرور الجديدة *",
                name="password",
                value=suggested,
                required=True,
                help_text="سيُطلب من المستخدم تغييرها عند أول دخول",
            )
        ],
    )
    if not data:
        return
    with components.error_boundary("إعادة تعيين كلمة المرور"):
        users_service.change_password(
            user_id,
            data["password"],
            must_change=True,
            actor=auth.current_user(),
            ip=auth.client_ip(),
        )
        components.toast_ok("تم تعيين كلمة مرور مؤقتة")
        go_app(APP, new_window=False)


def _toggle(user_id: int) -> None:
    target = users_service.get_user(user_id)
    label = "تنشيط" if not target["is_active"] else "تعطيل"
    with components.error_boundary("حالة المستخدم"):
        users_service.update_user(
            user_id,
            target["full_name"],
            target["role"],
            is_active=not bool(target["is_active"]),
            actor=auth.current_user(),
            ip=auth.client_ip(),
        )
        components.toast_ok(f"تم {label} الحساب")
        go_app(APP, new_window=False)


def _delete(user_id: int) -> None:
    target = users_service.get_user(user_id)
    if not components.confirm(f"حذف المستخدم «{target['username']}» نهائياً؟", "حذف", "إلغاء"):
        return
    with components.error_boundary("حذف مستخدم"):
        users_service.delete_user(user_id, actor=auth.current_user(), ip=auth.client_ip())
        components.toast_ok("تم حذف المستخدم")
        go_app(APP, new_window=False)
