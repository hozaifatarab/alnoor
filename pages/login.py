"""شاشة تسجيل الدخول — بطاقة تراثية على خلفية نجمية (إعادة تصميم كاملة).

المزايا: منع تعبئة المتصفح التلقائية (سبب فشل الدخول السابق)، معاينة كلمة
المرور عبر زر 👁، ودليل يوضّح طول ما وصل فعلياً عند الفشل لتسهيل التشخيص.
"""
from __future__ import annotations

from pywebio.input import PASSWORD, input, input_group
from pywebio.output import put_error, put_html, put_scope, put_success, use_scope
from pywebio.session import go_app, run_js, set_env

from core import auth
from core.exceptions import AppError
from core.repos import settings as settings_repo
from ui import components, layout


# تنسيقات الصفحة: لوحة ألوان نحاسية + خلفية بنقش النجمة الثمانية + بطاقة كريمية.
_LOGIN_STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Reem+Kufi:wght@400..700&family=IBM+Plex+Sans+Arabic:wght@300;400;500;600;700&display=swap');

.login-mode {
    --l-brand: #0f6e5c;
    --l-brand-2: #0b4a3f;
    --l-gold: #c9a227;
    --l-gold-2: #e8c65a;
    --l-cream: #fbf7ee;
    --l-err: #b3372a;
    --l-font-display: 'Reem Kufi', 'Segoe UI', Tahoma, sans-serif;
    --l-font-body: 'IBM Plex Sans Arabic', 'Segoe UI', Tahoma, sans-serif;
}
.login-mode body {
    min-height: 100vh;
    font-family: var(--l-font-body);
    background:
        radial-gradient(900px 620px at 88% -8%, rgba(18, 135, 111, .55), transparent 62%),
        radial-gradient(720px 520px at -12% 112%, rgba(201, 162, 39, .16), transparent 58%),
        linear-gradient(165deg, #06372e 0%, #04251f 46%, #02120f 100%) !important;
}
.login-bg {
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='96'%3E%3Cg fill='none' stroke='%23c9a227' stroke-opacity='0.17' stroke-width='1'%3E%3Crect x='24' y='24' width='48' height='48'/%3E%3Crect x='24' y='24' width='48' height='48' transform='rotate(45 48 48)'/%3E%3Ccircle cx='48' cy='48' r='30'/%3E%3C/g%3E%3C/svg%3E");
    background-size: 96px 96px;
    -webkit-mask-image: radial-gradient(130% 95% at 50% 0%, #000 25%, transparent 78%);
    mask-image: radial-gradient(130% 95% at 50% 0%, #000 25%, transparent 78%);
    animation: l-drift 70s linear infinite;
}
.login-bg::after {
    content: ""; position: absolute; top: -24vh; left: 50%; transform: translateX(-50%);
    width: 920px; height: 720px; border-radius: 50%;
    background: radial-gradient(closest-side, rgba(18, 135, 111, .55), transparent 72%);
    filter: blur(12px);
}
.login-grain {
    position: absolute; inset: 0; opacity: .055;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='180' height='180' filter='url(%23n)'/%3E%3C/svg%3E");
    background-size: 180px 180px;
}
.login-mode #output-container, .login-mode .container {
    position: relative; z-index: 1;
    max-width: 465px !important; margin: 0 auto;
    padding: 42px 14px 58px;
}
.login-head { text-align: center; animation: l-rise .65s cubic-bezier(.2, .85, .3, 1) both; }
.login-medallion { width: 104px; height: 104px; margin: 0 auto 16px; color: var(--l-gold-2); }
.login-medallion svg { width: 100%; height: 100%; overflow: visible; }
.login-medallion .ring-a { transform-origin: 50% 50%; animation: l-spin 46s linear infinite; }
.login-medallion .ring-b { transform-origin: 50% 50%; animation: l-spin-r 34s linear infinite; }
.login-medallion .medallion-glyph { font-family: var(--l-font-display); font-size: 36px; fill: var(--l-gold-2); }
.login-inst {
    font-family: var(--l-font-display); font-size: 30px; font-weight: 600;
    color: #f6efdd; text-shadow: 0 3px 16px rgba(0, 0, 0, .5); line-height: 1.4;
}
.login-sub { margin-top: 7px; font-size: 13.5px; color: rgba(232, 198, 90, .88); }
.login-rule { display: flex; align-items: center; justify-content: center; gap: 12px; margin: 18px 0 6px; }
.login-rule::before, .login-rule::after {
    content: ""; height: 1px; width: 88px;
    background: linear-gradient(90deg, transparent, rgba(201, 162, 39, .75));
}
.login-rule::after { transform: scaleX(-1); }
.login-rule span { color: var(--l-gold-2); font-size: 15px; }
.login-note {
    border-radius: 10px; padding: 9px 14px; font-size: 13.5px; line-height: 1.7;
    margin: 10px 0; border: 1px solid; animation: l-rise .65s .1s cubic-bezier(.2, .85, .3, 1) both;
}
.login-note--info { background: rgba(15, 110, 92, .3); border-color: rgba(232, 198, 90, .35); color: #dcefe8; }
.login-note--warn { background: rgba(168, 100, 22, .3); border-color: rgba(232, 198, 90, .5); color: #fbe9c9; }
.login-mode button[data-pw-toggle] {
    background: rgba(255, 255, 255, .06) !important;
    border: 1px solid rgba(201, 162, 39, .55) !important;
    color: var(--l-gold-2) !important;
    border-radius: 999px; padding: 6px 16px !important; font-size: 13px !important;
    box-shadow: none !important; transition: .2s ease;
    animation: l-rise .65s .16s cubic-bezier(.2, .85, .3, 1) both;
}
.login-mode button[data-pw-toggle]:hover { background: rgba(201, 162, 39, .2) !important; transform: translateY(-1px); }
.login-mode .card {
    background: var(--l-cream) !important;
    border: 1px solid rgba(201, 162, 39, .8) !important;
    outline: 1px solid rgba(201, 162, 39, .35); outline-offset: 4px;
    border-radius: 16px !important; overflow: hidden;
    box-shadow: 0 34px 64px -24px rgba(0, 0, 0, .75), 0 0 0 1px rgba(0, 0, 0, .25);
    animation: l-rise .7s .2s cubic-bezier(.2, .85, .3, 1) both;
}
.login-mode .card-header {
    background: linear-gradient(180deg, #f4ecd9, #efe4cb) !important;
    color: var(--l-brand-2) !important;
    font-family: var(--l-font-display) !important; font-size: 17px !important;
    text-align: center !important; border-bottom: 1px dashed rgba(15, 110, 92, .4) !important;
    padding: 13px 16px !important;
}
.login-mode .card-header:empty { display: none; }
.login-mode .card-body { padding: 22px 22px 20px !important; }
.login-mode .form-group { margin-bottom: 15px; }
.login-mode label {
    color: var(--l-brand-2) !important; font-weight: 600 !important;
    font-size: 13px !important; margin-bottom: 6px !important;
}
.login-mode .form-control {
    direction: ltr !important; text-align: left !important;
    border: 1px solid #d9cfb6 !important; background: #fff !important;
    border-radius: 9px !important; padding: 10px 13px !important;
    font-size: 16px !important; color: #1c2b27 !important;
    transition: border-color .18s, box-shadow .18s;
}
.login-mode .form-control:focus {
    border-color: var(--l-brand) !important;
    box-shadow: 0 0 0 3px rgba(15, 110, 92, .22) !important;
}
.login-mode .ws-form-submit-btns { display: flex; gap: 10px; margin-top: 4px; }
.login-mode .ws-form-submit-btns .btn-primary {
    flex: 1;
    background: linear-gradient(180deg, var(--l-brand), var(--l-brand-2)) !important;
    border: 1px solid rgba(5, 46, 38, .7) !important;
    color: #f3e9c8 !important;
    font-family: var(--l-font-display) !important; font-size: 17px !important;
    padding: 11px 14px !important; border-radius: 11px !important;
    box-shadow: 0 12px 22px -10px rgba(15, 110, 92, .85);
    transition: transform .16s ease, box-shadow .16s ease, filter .16s ease;
}
.login-mode .ws-form-submit-btns .btn-primary:hover {
    transform: translateY(-2px); filter: brightness(1.08);
    box-shadow: 0 18px 26px -10px rgba(15, 110, 92, .9);
}
.login-mode .ws-form-submit-btns .btn-primary:active { transform: translateY(0); }
.login-mode .ws-form-submit-btns .btn-warning {
    background: transparent !important; color: #a86416 !important;
    border: 1px dashed rgba(168, 100, 22, .55) !important;
    font-size: 13px !important; border-radius: 11px !important;
}
.login-diag {
    margin-top: 8px; padding: 9px 13px; font-size: 13px; line-height: 1.8;
    color: #f4d9a6; background: rgba(168, 100, 22, .18);
    border: 1px dashed rgba(232, 198, 90, .5); border-radius: 10px;
}
.login-foot {
    position: relative; z-index: 1; text-align: center; margin-top: 30px;
    padding-top: 14px; border-top: 1px dashed rgba(201, 162, 39, .3);
    font-size: 12px; color: rgba(232, 198, 90, .65);
    animation: l-rise .65s .32s cubic-bezier(.2, .85, .3, 1) both;
}
@keyframes l-rise { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: none; } }
@keyframes l-spin { to { transform: rotate(360deg); } }
@keyframes l-spin-r { to { transform: rotate(-360deg); } }
@keyframes l-drift { to { background-position: 96px 192px; } }
@media (prefers-reduced-motion: reduce) {
    .login-mode * { animation-duration: .01ms !important; animation-delay: 0s !important; }
    .login-bg { animation: none; }
}
"""

# حارس المتصفح: يفعّل وضع التصميم، يمسح التعبئة التلقائية، ويعرّف زر الإرسال.
_LOGIN_JS = """
(function () {
    document.documentElement.classList.add('login-mode');
    if (window.__loginGuard) { return; }
    window.__loginGuard = true;

    function harden(el) {
        if (el.dataset.loginHarden) { return; }
        el.dataset.loginHarden = '1';
        el.setAttribute('autocomplete', 'off');
        el.setAttribute('data-1p-ignore', 'true');
        el.setAttribute('data-lpignore', 'true');
        el.setAttribute('data-bwignore', 'true');
        el.addEventListener('focus', function () { el.dataset.typed = '1'; });
        el.addEventListener('input', function () { el.dataset.typed = '1'; });
    }

    function sweep(pw) {
        if (pw.dataset.typed || document.activeElement === pw) { return; }
        if (pw.value) { pw.value = ''; }
    }

    function service() {
        document.querySelectorAll('input').forEach(harden);
        document.querySelectorAll('input[type="password"]').forEach(function (pw) {
            if (pw.dataset.sweepQueued) { return; }
            pw.dataset.sweepQueued = '1';
            // نافذات زمنية لالتقاط التعبئة المتأخرة من مدير كلمات المرور.
            setTimeout(function () { sweep(pw); }, 350);
            setTimeout(function () { sweep(pw); }, 1300);
            setTimeout(function () { sweep(pw); }, 2600);
        });
        document.querySelectorAll('.ws-form-submit-btns .btn-primary').forEach(function (b) {
            if (b.dataset.loginLabel) { return; }
            b.dataset.loginLabel = '1';
            b.textContent = 'تسجيل الدخول';
        });
        if (!window.__loginFocusDone) {
            var user = document.querySelector('input[name="username"]');
            if (user) {
                window.__loginFocusDone = true;
                try { user.focus(); } catch (e) {}
            }
        }
    }

    if (document.body) {
        service();
        var mo = new MutationObserver(service);
        mo.observe(document.body, { childList: true, subtree: true });
    }
})();
"""

_ERROR_SCOPE = "login_error"


def _header_html(institution: str) -> str:
    """ترويسة الصفحة: ميدالية نجمية + اسم المؤسسة + فاصل ذهبي."""
    return (
        '<div class="login-head">'
        '<div class="login-medallion" aria-hidden="true">'
        '<svg viewBox="0 0 100 100">'
        '<g class="ring-a" fill="none" stroke="currentColor" stroke-width="1.6">'
        '<rect x="22" y="22" width="56" height="56" transform="rotate(0 50 50)"/>'
        '<rect x="22" y="22" width="56" height="56" transform="rotate(45 50 50)"/>'
        "</g>"
        '<g class="ring-b" fill="none" stroke="currentColor" stroke-width="1" stroke-dasharray="3 5">'
        '<circle cx="50" cy="50" r="45"/>'
        "</g>"
        '<circle cx="50" cy="50" r="34" fill="rgba(5,46,38,.55)" stroke="currentColor" stroke-width="1.2"/>'
        '<text class="medallion-glyph" x="50" y="52" text-anchor="middle" dominant-baseline="middle">م</text>'
        "</svg>"
        "</div>"
        f'<div class="login-inst">{layout.escape_html(institution)}</div>'
        '<div class="login-sub">نظام إدارة المؤسسة التعليمية</div>'
        '<div class="login-rule"><span>✦</span></div>'
        "</div>"
    )


def render_login_form(notice: str | None = None) -> None:
    """عرض نموذج الدخول (يُستدعى أيضاً من الشاشات المحمية عند انتهاء الجلسة)."""
    institution = settings_repo.institution_name()
    set_env(title=f"تسجيل الدخول | {institution}", output_animation=False)

    put_html(f"<style>{_LOGIN_STYLE}</style>")
    put_html('<div class="login-bg"><div class="login-grain"></div></div>')
    run_js(_LOGIN_JS)
    put_html(_header_html(institution))

    if notice:
        put_html(f'<div class="login-note login-note--warn">{layout.escape_html(notice)}</div>')
    put_html(
        '<div class="login-note login-note--info">'
        "في حال نسيان كلمة المرور، تواصل مع مدير النظام لإعادة تعيينها. "
        "لا تعتمد على تعبئة المتصفح التلقائية — اكتب بياناتك يدوياً.</div>"
    )
    components.password_toggle_hint()
    put_scope(_ERROR_SCOPE)

    while True:
        data = input_group(
            "أدخل بيانات الدخول للمتابعة",
            [
                input(
                    "اسم المستخدم",
                    name="username",
                    required=True,
                    placeholder="مثال: admin",
                    autocomplete="off",
                ),
                input(
                    "كلمة المرور",
                    name="password",
                    type=PASSWORD,
                    required=True,
                    autocomplete="off",
                ),
            ],
            cancelable=False,
        )
        with use_scope(_ERROR_SCOPE, clear=True):
            try:
                user = auth.login(data["username"], data["password"])
            except AppError as exc:
                put_error(f"⚠ {exc.user_message}")
                # دليل تشخيصي: الطول فقط (لا محتوى) ليكشف التعبئة التلقائية الخاطئة.
                put_html(
                    f'<div class="login-diag">وصلت كلمة مرور طولها {len(data["password"])} حرفًا. '
                    "إن كان مختلفاً عمّا تكتبه فالمتصفح ملأها تلقائياً — امسحها واكتبها يدوياً "
                    "واضغط 👁 للمعاينة قبل الإرسال.</div>"
                )
                continue

        put_success(f"مرحباً بك {user['full_name']} — {_role_label(user)}")
        if user["must_change_password"]:
            from pages import profile

            profile.render_change_password(force=True, user=user)
            return
        go_app(auth.home_app_for(user), new_window=False)
        return


def _role_label(user: dict) -> str:
    from core import config

    return config.role_label(user["role"])


def login() -> None:
    """نقطة دخول النظام: إن كان المستخدم مسجّلاً ينتقل للوحة المعلومات مباشرة."""
    user = auth.current_user()
    if user is not None:
        go_app(auth.home_app_for(user), new_window=False)
        return
    render_login_form()
