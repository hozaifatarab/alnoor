"""جسر ماسح QR داخل المتصفح: كاميرا + رفع صورة + jsQR + إرجاع الرمز إلى بايثون.

التصميم (موثّق في خطة المرحلة 2):
* الكاميرا تُعرض في وسم <video> داخل الصفحة، وjsQR يقرأ الإطارات.
* البديل الجديد (بدون كاميرا/بدون HTTPS): رفع صورة QR من الجهاز —
  تُفكّ في المتصفح نفسه عبر jsQR ثم تُمرَّر لنفس قناة ``window.__qrOnCode``.
* عند نجاح القراءة تُستدعى الدالة العالمية ``window.__qrOnCode`` التي تُرجع
  النص إلى بايثون عبر ``eval_js`` مع Promise (مع نبضة إيقاف كل 15 ثانية
  تضمن عدم تعليق الصفحة للأبد).
* يعمل الماسح إنترنت/بدون: يُحمّل jsQR محلياً من ``/static/vendor/jsQR.min.js``
  وإن لم يوجد يُستخدم CDN.
"""
from __future__ import annotations

from typing import Callable

from pywebio.output import put_html, put_buttons, put_markdown
from pywebio.session import eval_js, run_js
from ui.layout import escape_html

VENDOR_JS = "/static/vendor/jsQR.min.js"
CDN_JS = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"

CONTAINER_ID = "qr-scanner-area"
VIDEO_ID = "qr-video"
CANVAS_ID = "qr-canvas"
UPLOAD_ID = "qr-upload"
UPLOAD_CANVAS_ID = "qr-upload-canvas"
UPLOAD_STATUS_ID = "qr-upload-status"


def render_camera_area(hint: str = "وجّه بطاقة الطالب نحو الكاميرا") -> None:
    """عنصر الكاميرا + تعليمات الاستخدام."""
    put_html(
        f"""
        <div style="background:#0f172a;border-radius:12px;padding:12px;text-align:center;margin-bottom:10px">
            <div style="color:#e2e8f0;font-size:13px;margin-bottom:8px">{escape_html(hint)}</div>
            <div id="{CONTAINER_ID}" style="position:relative;display:inline-block">
                <video id="{VIDEO_ID}" autoplay playsinline muted
                       style="width:360px;max-width:100%;border-radius:10px;background:#1e293b"></video>
                <canvas id="{CANVAS_ID}" style="display:none"></canvas>
                <div style="position:absolute;top:50%;left:50%;
                     transform:translate(-50%,-50%);width:220px;height:220px;
                     border:3px dashed #38bdf8;border-radius:10px"></div>
            </div>
            <div style="color:#94a3b8;font-size:12px;margin-top:8px">
                إن لم تعمل الكاميرا (تتطلب HTTPS أو localhost) استخدم الإدخال اليدوي بالأسفل.
            </div>
        </div>
        """
    )


_BOOT_JS = """
(function () {
    if (window.__qrRunning) {
        window.__qrStop = false;
        if (window.__qrResume) { window.__qrResume(); }
        return;
    }
    window.__qrRunning = true;
    window.__qrStop = false;

    function load(src) {
        return new Promise(function (resolve) {
            var s = document.createElement('script');
            s.src = src;
            s.onload = function () { resolve(!!window.jsQR); };
            s.onerror = function () { resolve(false); };
            document.head.appendChild(s);
        });
    }

    async function ensureLib() {
        if (window.jsQR) { return true; }
        if (await load(__LOCAL_JS__)) { return true; }
        return await load(__CDN_JS__);
    }

    async function run() {
        var ok = await ensureLib();
        var video = document.getElementById('qr-video');
        var canvas = document.getElementById('qr-canvas');
        if (!ok || !video || !canvas) {
            window.__qrCameraError = 'تعذّر تحميل مكتبة قراءة الرموز. استخدم الإدخال اليدوي.';
            return;
        }
        try {
            var stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment'}});
            video.srcObject = stream;
            window.__qrStream = stream;
        } catch (err) {
            window.__qrCameraError = 'تعذّر الوصول إلى الكاميرا (' + err.name + '). استخدم الإدخال اليدوي.';
            return;
        }
        var ctx = canvas.getContext('2d');
        window.__qrResume = function () {
            window.__qrStop = false;
            requestAnimationFrame(tick);
        };
        function tick() {
            if (window.__qrStop) { return; }
            if (video.readyState === video.HAVE_ENOUGH_DATA) {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                var img = ctx.getImageData(0, 0, canvas.width, canvas.height);
                var code = window.jsQR(img.data, img.width, img.height);
                if (code && code.data) {
                    var now = Date.now();
                    var isNew = code.data !== window.__qrLast || (now - (window.__qrLastAt || 0)) > 3000;
                    if (isNew) {
                        window.__qrLast = code.data;
                        window.__qrLastAt = now;
                        if (window.__qrOnCode) { window.__qrOnCode(code.data); }
                        return;
                    }
                }
            }
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }

    run();
})();
"""


def start_scanner(local_js: str = VENDOR_JS, cdn_js: str = CDN_JS) -> None:
    """تشغيل محرك القراءة في المتصفح (يستدعي window.__qrOnCode عند نجاح القراءة)."""
    run_js(_BOOT_JS.replace("__LOCAL_JS__", repr(local_js)).replace("__CDN_JS__", repr(cdn_js)))



def stop_scanner() -> None:
    """إيقاف القراءة وإغلاق الكاميرا من المتصفح."""
    run_js(
        """
        window.__qrStop = true;
        if (window.__qrStream) {
            try { window.__qrStream.getTracks().forEach(function (t) { t.stop(); }); } catch (e) {}
            window.__qrStream = null;
        }
        var v = document.getElementById('qr-video');
        if (v) { v.srcObject = null; }
        """
    )


_WAIT_JS = """
new Promise(function (resolve) {
    window.__qrOnCode = function (text) { window.__qrOnCode = null; resolve(text); };
    setTimeout(function () {
        if (window.__qrOnCode) { window.__qrOnCode = null; resolve('__TICK__'); }
    }, __TIMEOUT__);
})
"""


def wait_for_code(timeout_ms: int = 15000) -> str | None:
    """انتظار قراءة رمز واحد (أو ``__TICK__`` عند انتهاء المهلة).

    يعتمد على دعم PyWebIO لحل Promise داخل ``eval_js`` (موثّق منذ الإصدار 1.3).
    """
    result = eval_js(_WAIT_JS.replace("__TIMEOUT__", str(timeout_ms)))
    return result if isinstance(result, str) else None


def scanner_stopped() -> bool:
    """هل طلب المستخدم إيقاف المسح من داخل المتصفح؟"""
    try:
        return bool(eval_js("!!window.__qrStop"))
    except Exception:  # pragma: no cover
        return True


def camera_error() -> str | None:
    """رسالة خطأ الكاميرا إن وُجدت."""
    try:
        return eval_js("window.__qrCameraError || ''") or None
    except Exception:  # pragma: no cover
        return None


def resume_scanner() -> None:
    """إعادة تسليح الماسح بعد معالجة قراءة."""
    run_js("if (window.__qrResume) { window.__qrResume(); }")


def render_manual_entry(on_submit: Callable[[str], None]) -> None:
    """بديل مضمون: إدخال الرقم الأكاديمي يدوياً أو عبر قارئ باركود (USB)."""
    put_markdown("**إدخال يدوي / قارئ باركود USB**")
    put_buttons(
        [{"label": "⌨ إدخال الرقم يدوياً", "value": "manual", "color": "secondary"}],
        onclick=lambda _value: manual_dialog(on_submit),
        small=True,
    )


def render_upload_area(hint: str = "لا توجد كاميرا؟ صوّر البطاقة بهاتفك ثم ارفع الصورة هنا") -> None:
    """بديل رفع صورة QR: يعمل بدون كاميرا وبدون HTTPS (فكّ كامل داخل المتصفح)."""
    put_html(
        f"""
        <div style="background:#f0f9ff;border:2px dashed #38bdf8;border-radius:12px;
                    padding:14px;text-align:center;margin:10px 0">
            <div style="font-size:14px;font-weight:700;color:#0c4a6e;margin-bottom:4px">
                📤 بديل الكاميرا: رفع صورة QR
            </div>
            <div style="color:#475569;font-size:12px;margin-bottom:10px">{escape_html(hint)}</div>
            <label for="{UPLOAD_ID}"
                   style="display:inline-block;background:#0284c7;color:#fff;border-radius:8px;
                          padding:8px 18px;font-size:14px;font-weight:700;cursor:pointer">
                اختيار صورة البطاقة…
            </label>
            <input id="{UPLOAD_ID}" type="file" accept="image/*" style="display:none">
            <canvas id="{UPLOAD_CANVAS_ID}" style="display:none"></canvas>
            <div id="{UPLOAD_STATUS_ID}" style="font-size:12px;color:#64748b;margin-top:8px"></div>
        </div>
        """
    )


_UPLOAD_JS = """
(function () {
    var input = document.getElementById('qr-upload');
    var statusEl = document.getElementById('qr-upload-status');
    if (!input || input.dataset.qrBound) { return; }
    input.dataset.qrBound = '1';

    function setStatus(msg, ok) {
        if (statusEl) {
            statusEl.textContent = msg;
            statusEl.style.color = ok ? '#16a34a' : '#64748b';
        }
    }

    function load(src) {
        return new Promise(function (resolve) {
            var s = document.createElement('script');
            s.src = src;
            s.onload = function () { resolve(!!window.jsQR); };
            s.onerror = function () { resolve(false); };
            document.head.appendChild(s);
        });
    }

    async function ensureLib() {
        if (window.jsQR) { return true; }
        if (await load(__LOCAL_JS__)) { return true; }
        return await load(__CDN_JS__);
    }

    input.addEventListener('change', async function () {
        var file = input.files && input.files[0];
        if (!file) { return; }
        setStatus('جارٍ قراءة الصورة…');
        var ok = await ensureLib();
        if (!ok) {
            setStatus('تعذّر تحميل مكتبة القراءة. تحقق من الإنترنت أو الأصول المحلية.');
            input.value = '';
            return;
        }
        var url = URL.createObjectURL(file);
        var img = new Image();
        img.onload = function () {
            try {
                var canvas = document.getElementById('qr-upload-canvas');
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;
                var ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);
                var data = ctx.getImageData(0, 0, canvas.width, canvas.height);
                var code = window.jsQR(data.data, data.width, data.height);
                URL.revokeObjectURL(url);
                if (code && code.data) {
                    setStatus('تمت قراءة الرمز بنجاح ✓', true);
                    if (window.__qrOnCode) { window.__qrOnCode(code.data); }
                } else {
                    setStatus('لم يُعثر على رمز QR في الصورة — جرّب صورة أوضح وأقرب.');
                }
            } catch (err) {
                setStatus('تعذّرت قراءة الصورة (' + err.name + ').');
            }
            input.value = '';
        };
        img.onerror = function () {
            URL.revokeObjectURL(url);
            setStatus('ملف الصورة غير صالح.');
            input.value = '';
        };
        img.src = url;
    });
})();
"""


def bind_upload_reader(local_js: str = VENDOR_JS, cdn_js: str = CDN_JS) -> None:
    """تفعيل قارئ الصور المرفوعة (يُستدعى مرة واحدة بعد عرض منطقة الرفع)."""
    run_js(_UPLOAD_JS.replace("__LOCAL_JS__", repr(local_js)).replace("__CDN_JS__", repr(cdn_js)))


def manual_dialog(on_submit: Callable[[str], None]) -> None:
    """نافذة إدخال الرقم الأكاديمي ثم تمريره لمعالجة المسح."""
    from pywebio.input import input, input_group

    data = input_group(
        "مسح / إدخال الرقم الأكاديمي",
        [
            input(
                "الرقم الأكاديمي أو نتيجة القارئ",
                name="code",
                required=True,
                placeholder="مثال: 2026-0001",
                help_text="يعمل مع قارئ الباركود USB (يُكتب الرقم ثم Enter تلقائياً)",
            )
        ],
        cancelable=True,
    )
    if not data:
        return
    on_submit(str(data["code"]).strip())


_BEEP_JS = """
try {
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) {
        var ctx = new Ctx();
        var osc = ctx.createOscillator();
        osc.frequency.value = __FREQ__;
        osc.connect(ctx.destination);
        osc.start();
        setTimeout(function () { osc.stop(); ctx.close(); }, 140);
    }
} catch (e) {}
"""


def render_feedback(message: str, ok: bool) -> None:
    """تنبيه مرئي + صوت قصير لنتيجة القراءة بجانب الكاميرا."""
    color = "#16a34a" if ok else "#dc2626"
    put_html(
        f'<div style="background:{color};color:#fff;border-radius:8px;padding:8px 12px;'
        f'font-size:14px;margin:6px 0">{escape_html(message)}</div>'
    )
    run_js(_BEEP_JS.replace("__FREQ__", "880" if ok else "220"))
