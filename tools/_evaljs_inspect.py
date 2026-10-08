"""فحص مصدر eval_js في PyWebIO (هل يدعم Promise؟). (مؤقت)"""
import inspect

import pywebio.session as s

print(inspect.getsource(s.eval_js))
try:
    import pywebio.session.base as base

    print("---- SessionCmd ----")
    print(inspect.getsource(base.Session.eval_js))
except Exception as exc:
    print("base:", exc)
