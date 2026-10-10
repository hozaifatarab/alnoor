"""المظهر العام: تنسيق RTL عربي + تهيئة PyWebIO.

يُطبَّق التنسيق عبر ``pywebio.config(css_style=...)`` على كل الشاشات.
"""
from __future__ import annotations

from pywebio import config

RTL_FONT = "'Segoe UI', Tahoma, 'Noto Naskh Arabic', 'Cairo', sans-serif"

RTL_CSS = """
* { font-family: __FONT__; }
body, .container, .container-fluid, .pywebio-scope-container, .modal-content,
.form-group, .input-group, .card, .table, h1, h2, h3, h4, h5, p, label {
    direction: rtl; text-align: right;
}
.navbar { direction: rtl; }
.table th, .table td { text-align: right; vertical-align: middle; }
.form-control, .custom-select, .btn { direction: rtl; }
input[type=number], input[type=date], .ltr { direction: ltr; text-align: left; }

/* ترويسة النظام */
.inst-header {
    background: linear-gradient(90deg, #0f6e5c 0%, #12876f 100%);
    color: #fff; padding: 12px 18px; border-radius: 10px; margin-bottom: 10px;
}
.inst-header .inst-title { font-size: 20px; font-weight: 700; }
.inst-header .inst-user  { font-size: 13px; opacity: .92; }
/* ===== شريط جانبي احترافي على اليسار ===== */
.inst-sidebar {
    position: fixed; top: 0; left: 0; bottom: 0; width: 258px; z-index: 1040;
    overflow-y: auto; direction: rtl;
    background: linear-gradient(185deg, #0f6e5c 0%, #0a4d41 60%, #073b32 100%);
    color: #eafaf5; box-shadow: 2px 0 16px rgba(0,0,0,.20);
    display: flex; flex-direction: column;
}
.sb-brand { display: block; padding: 18px 18px 14px; text-decoration: none; color: #fff;
    border-bottom: 1px solid rgba(255,255,255,.12); }
.sb-brand:hover { text-decoration: none; background: rgba(255,255,255,.05); }
.sb-brand-title { font-size: 18px; font-weight: 700; line-height: 1.3; }
.sb-brand-sub { font-size: 12px; opacity: .8; margin-top: 3px; }
.sb-nav { flex: 1 1 auto; padding: 10px 8px; overflow-y: auto; }
.sb-group { margin-bottom: 4px; }
.sb-group-title { font-size: 11px; font-weight: 700; color: #9fd8c9;
    padding: 12px 12px 6px; }
.sb-link { display: block; padding: 8px 12px; margin: 2px 6px; border-radius: 8px;
    color: #eafaf5; text-decoration: none; font-size: 14px;
    border-right: 3px solid transparent; transition: background .15s, color .15s; }
.sb-link:hover { background: rgba(255,255,255,.10); text-decoration: none; }
.sb-link.active { background: #fff; color: #0f6e5c; font-weight: 700; border-right-color: #c9a227; }
.sb-foot { padding: 12px; border-top: 1px solid rgba(255,255,255,.12); }
.sb-user-name { font-size: 14px; font-weight: 600; color: #fff; }
.sb-user-role { font-size: 12px; opacity: .8; margin-top: 2px; }
.sb-logout { margin-top: 8px; color: #ffd7d2; }
.sb-logout:hover { background: rgba(217,83,79,.28); color: #fff; }

/* إزاحة المحتوى (الخرج + النماذج) لفسح مكان للشريط الجانبي */
#output-container, #input-cards {
    margin-left: 278px; max-width: none; width: auto;
}
/* عنوان الصفحة داخل المحتوى */
.inst-pagebar { font-size: 20px; font-weight: 700; color: #0f6e5c;
    padding: 8px 2px 12px; border-bottom: 2px solid #e2e8e6; margin-bottom: 12px; }

/* شاشات ضيقة: يتحول الشريط إلى شريط علوي */
@media (max-width: 900px) {
    .inst-sidebar { position: static; width: 100%; box-shadow: none; }
    .sb-nav { display: flex; flex-wrap: wrap; }
    .sb-group { flex: 1 1 100%; }
    #output-container, #input-cards { margin-left: 0; width: auto; }
}


/* بطاقات المؤشرات */
.kpi-grid { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.kpi-card {
    flex: 1 1 160px; background: #fff; border: 1px solid #e2e8e6; border-right: 5px solid #0f6e5c;
    border-radius: 10px; padding: 10px 14px; box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.kpi-card .kpi-label { font-size: 13px; color: #5b6b67; }
.kpi-card .kpi-value { font-size: 24px; font-weight: 700; color: #0f6e5c; }
.kpi-card.warn { border-right-color: #d9822b; }
.kpi-card.warn .kpi-value { color: #d9822b; }
.kpi-card.danger { border-right-color: #c0392b; }
.kpi-card.danger .kpi-value { color: #c0392b; }

/* شرائح الحالة */
.chip { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
.chip-ok    { background: #e5f6ee; color: #1e7a4c; }
.chip-warn  { background: #fdf1e2; color: #a86416; }
.chip-bad   { background: #fbe9e7; color: #b3372a; }
.chip-muted { background: #eef1f1; color: #5b6b67; }

/* عناوين الأقسام */
.section-title { font-size: 17px; font-weight: 700; color: #0f6e5c; margin: 14px 0 6px; }
.section-hint { font-size: 13px; color: #6b7c78; margin-bottom: 8px; }
.inst-card { background: #fff; border: 1px solid #e2e8e6; border-radius: 10px; padding: 12px 14px; margin-bottom: 12px; }
.inst-footer { margin-top: 24px; padding-top: 8px; border-top: 1px solid #e2e8e6;
    font-size: 12px; color: #839591; text-align: center; }

/* شريط تقدم بسيط للرسوم البيانية */
.bar-wrap { background: #eef1f1; border-radius: 6px; height: 16px; overflow: hidden; margin: 2px 0 8px 0; }
.bar-fill { background: #0f6e5c; height: 100%; }
.bar-fill.warn { background: #d9822b; }
.bar-fill.danger { background: #c0392b; }
.bar-row { font-size: 13px; color: #40514d; display: flex; justify-content: space-between; }

@media print {
    .inst-nav, .inst-footer, .no-print { display: none !important; }
}
""".replace("__FONT__", RTL_FONT)


def apply_config(institution: str, theme: str = "minty") -> None:
    """تهيئة عامة لشكل النظام (تُستدعى مرة واحدة عند الإقلاع)."""
    config(
        title=f"{institution} | نظام الإدارة",
        description="نظام إدارة مؤسسة تعليمية: الطلاب، المعلمون، الفصول، التسجيل، الحضور بـ QR، الدرجات والمالية.",
        theme=theme,
        css_style=RTL_CSS,
    )
