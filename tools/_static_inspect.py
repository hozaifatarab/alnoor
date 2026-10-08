"""فحص كيفية تقديم الملفات الثابتة في start_server (مسار URL). (مؤقت)"""
import inspect

from pywebio.platform import tornado as t

src = inspect.getsource(t)
for i, line in enumerate(src.splitlines(), 1):
    if "static" in line.lower():
        print(f"{i}: {line}")
