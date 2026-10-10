"""مستودع سجل التدقيق (Audit log)."""
from __future__ import annotations

from typing import Any

from .. import db


def log(
    action: str,
    entity: str | None = None,
    entity_id: Any = None,
    details: str | None = None,
    user: dict[str, Any] | None = None,
    ip: str | None = None,
    conn: Any = None,
) -> int:
    """تسجيل عملية حساسة في سجل التدقيق.

    تُمرَّر ``conn`` عند الكتابة داخل معاملة مفتوحة؛ ففتح اتصال آخر للكتابة
    أثناء معاملة يتعارض مع قيد كاتب واحد في WAL (تعليق ثم فشل).
    """
    sql = (
        "INSERT INTO audit_log(user_id, username, action, entity, entity_id, details, ip)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    params = (
        (user or {}).get("id"),
        (user or {}).get("username"),
        action,
        entity,
        None if entity_id is None else str(entity_id),
        details,
        ip,
    )
    if conn is not None:
        return int(conn.execute(sql, params).lastrowid or 0)
    return db.execute(sql, params)


def recent(limit: int = 100, entity: str | None = None) -> list[dict[str, Any]]:
    if entity:
        rows = db.query_all(
            "SELECT * FROM audit_log WHERE entity = ? ORDER BY id DESC LIMIT ?", (entity, limit)
        )
    else:
        rows = db.query_all("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(row) for row in rows]


def count() -> int:
    return int(db.scalar("SELECT COUNT(*) FROM audit_log", (), 0) or 0)
