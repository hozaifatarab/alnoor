"""فحص سريع لحالة الجداول وسجلات البيانات."""
import _bootstrap  # noqa: F401
import sqlite3
from core import config

conn = sqlite3.connect(config.db_path())
from core import db
db.init_db()

tables = [
    t[0] for t in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
]
print(f"قاعدة البيانات: {config.db_path()}")
print("-" * 50)
for tbl in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"  {tbl:<25}: {count}")
conn.close()
