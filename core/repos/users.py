"""مستودع المستخدمين."""
from __future__ import annotations

from typing import Any

from .. import db


def get(user_id: int) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return dict(row) if row else None


def get_by_username(username: str) -> dict[str, Any] | None:
    row = db.query_one(
        "SELECT * FROM users WHERE lower(username) = lower(?)", (username,)
    )
    return dict(row) if row else None


def list_users(search: str | None = None, role: str | None = None) -> list[dict[str, Any]]:
    sql = ["SELECT * FROM users WHERE 1 = 1"]
    params: list[Any] = []
    if search:
        sql.append("AND (username LIKE ? OR full_name LIKE ?)")
        params += [f"%{search}%", f"%{search}%"]
    if role:
        sql.append("AND role = ?")
        params.append(role)
    sql.append("ORDER BY is_active DESC, full_name")
    return [dict(row) for row in db.query_all(" ".join(sql), params)]


def create(
    username: str,
    full_name: str,
    role: str,
    password_hash: str,
    password_salt: str,
    is_active: int = 1,
    must_change_password: int = 0,
) -> int:
    return db.execute(
        "INSERT INTO users(username, full_name, role, password_hash, password_salt,"
        " is_active, must_change_password) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (username, full_name, role, password_hash, password_salt, is_active, must_change_password),
    )


def update_profile(user_id: int, full_name: str, role: str, is_active: int) -> None:
    db.execute(
        "UPDATE users SET full_name = ?, role = ?, is_active = ? WHERE id = ?",
        (full_name, role, is_active, user_id),
    )


def update_password(user_id: int, password_hash: str, password_salt: str, must_change: int = 0) -> None:
    db.execute(
        "UPDATE users SET password_hash = ?, password_salt = ?, must_change_password = ?,"
        " failed_attempts = 0, locked_until = NULL WHERE id = ?",
        (password_hash, password_salt, must_change, user_id),
    )


def register_failure(user_id: int, attempts: int, locked_until: str | None) -> None:
    db.execute(
        "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
        (attempts, locked_until, user_id),
    )


def register_success(user_id: int) -> None:
    db.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL,"
        " last_login = datetime('now','localtime') WHERE id = ?",
        (user_id,),
    )


def delete(user_id: int) -> None:
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))


def count_by_role() -> dict[str, int]:
    rows = db.query_all("SELECT role, COUNT(*) AS total FROM users GROUP BY role")
    return {row["role"]: int(row["total"]) for row in rows}


def count_admins(exclude_user_id: int | None = None) -> int:
    if exclude_user_id is None:
        return int(db.scalar("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1", (), 0) or 0)
    return int(
        db.scalar(
            "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1 AND id <> ?",
            (exclude_user_id,),
            0,
        )
        or 0
    )
