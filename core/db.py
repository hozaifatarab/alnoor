"""طبقة الوصول إلى SQLite.

المبادئ:
* اتصال مستقل لكل عملية (آمن مع خيوط PyWebIO المتعددة) + ``busy_timeout``.
* تفعيل المفاتيح الأجنبية ووضع WAL.
* هجرات مرقّمة بالترتيب (forward-only) مع جدول ``schema_version``.
* كل الاستعلامات بمعاملات (parameterized) لمنع حقن SQL.
"""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from . import config
from .exceptions import BusinessRuleError, DuplicateError, ValidationError

logger = logging.getLogger(__name__)


def connect(db_file: Path | None = None) -> sqlite3.Connection:
    """إنشاء اتصال مهيّأ بقاعدة البيانات."""
    conn = sqlite3.connect(str(db_file or config.db_path()), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """اتصال للقراءة فقط يُغلق تلقائياً."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """معاملة صريحة: تنجح كاملة أو تُلغى كاملة."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _raise_db_error(exc: sqlite3.Error) -> None:
    """ترجمة أخطاء SQLite إلى استثناءات النظام."""
    message = str(exc)
    if "UNIQUE" in message:
        raise DuplicateError("القيمة مسجّلة مسبقاً في النظام", detail=message) from exc
    if "FOREIGN KEY" in message:
        raise BusinessRuleError("مرجع غير صحيح: العنصر المرتبط غير موجود", detail=message) from exc
    if "CHECK" in message or "NOT NULL" in message:
        raise ValidationError("قيمة غير مسموح بها في أحد الحقول", detail=message) from exc
    raise BusinessRuleError("تعذّر تنفيذ العملية على قاعدة البيانات", detail=message) from exc


def query_all(sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    with get_conn() as conn:
        try:
            return list(conn.execute(sql, params))
        except sqlite3.Error as exc:  # pragma: no cover - مسار نادر
            _raise_db_error(exc)
            return []


def query_one(sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
    rows = query_all(sql, params)
    return rows[0] if rows else None


def scalar(sql: str, params: Sequence[Any] = (), default: Any = None) -> Any:
    row = query_one(sql, params)
    if row is None or row[0] is None:
        return default
    return row[0]


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    """تنفيذ أمر كتابة وإرجاع آخر معرّف مُدرج (أو عدد الصفوف المتأثرة)."""
    with transaction() as conn:
        try:
            cursor = conn.execute(sql, params)
        except sqlite3.Error as exc:
            _raise_db_error(exc)
            raise
        return int(cursor.lastrowid or cursor.rowcount)


def execute_many(sql: str, seq: Iterable[Sequence[Any]]) -> int:
    with transaction() as conn:
        try:
            cursor = conn.executemany(sql, list(seq))
        except sqlite3.Error as exc:
            _raise_db_error(exc)
            raise
        return int(cursor.rowcount)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


# ---------------- الهجرات ----------------

def applied_migrations(conn: sqlite3.Connection) -> set[str]:
    return {r["version"] for r in conn.execute("SELECT version FROM schema_version")}


def init_db() -> list[str]:
    """إنشاء/ترقية قاعدة البيانات، وإرجاع الهجرات المُطبَّقة في هذه الجلسة."""
    conn = connect()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version ("
            " version TEXT PRIMARY KEY,"
            " applied_at TEXT NOT NULL DEFAULT (datetime('now','localtime')))"
        )
        conn.commit()
        done = applied_migrations(conn)
        newly: list[str] = []
        for path in sorted(config.MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in done:
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                conn.executescript(sql)
                conn.execute("INSERT INTO schema_version(version) VALUES (?)", (version,))
                conn.commit()
            except sqlite3.Error as exc:
                conn.rollback()
                raise BusinessRuleError(f"فشل تطبيق الهجرة {version}", detail=str(exc)) from exc
            newly.append(version)
            logger.info("migration applied: %s", version)
        return newly
    finally:
        conn.close()


def schema_version() -> str:
    with get_conn() as conn:
        try:
            version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        except sqlite3.Error:
            return "none"
    return version or "none"
