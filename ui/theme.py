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
.inst-nav { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0 14px 0; }
.inst-nav a, .inst-nav button {
    font-size: 13px; padding: 5px 12px; border-radius: 20px; border: 1px solid #0f6e5c;
    background: #fff; color: #0f6e5c; cursor: pointer;
}
.inst-nav a.active, .inst-nav button.active, .inst-nav .active {
    background: #0f6e5c; color: #fff; font-weight: 600;
}
.inst-nav a:hover, .inst-nav button:hover { text-decoration: none; background: #e8f5f1; }

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
