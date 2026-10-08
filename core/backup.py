"""Authenticated encrypted backups for the SQLite application database."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"INSTDB1\x00"
_SALT_SIZE = 16
_NONCE_SIZE = 12
_KEY_SIZE = 32
_MIN_PASSPHRASE_LENGTH = 12


class BackupError(ValueError):
    """Raised when a backup cannot be safely created or restored."""


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if len(passphrase) < _MIN_PASSPHRASE_LENGTH:
        raise BackupError("عبارة المرور يجب أن تكون 12 حرفاً على الأقل")
    return Scrypt(salt=salt, length=_KEY_SIZE, n=2**14, r=8, p=1).derive(
        passphrase.encode("utf-8")
    )


def _validate_database(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA integrity_check").fetchone()
    if not result or result[0] != "ok":
        raise BackupError("فشل فحص سلامة قاعدة البيانات")

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    required = {"schema_version", "users", "settings"}
    if not required.issubset(tables):
        raise BackupError("الملف لا يحتوي على مخطط قاعدة بيانات المؤسسة")
    if not connection.execute("SELECT 1 FROM schema_version LIMIT 1").fetchone():
        raise BackupError("قاعدة البيانات لا تحتوي على إصدار مخطط مطبق")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise BackupError("توجد مراجع غير صالحة في قاعدة البيانات")


def _atomic_write(destination: Path, content: bytes) -> None:
    if destination.exists():
        raise BackupError(f"الملف موجود مسبقاً ولن يُستبدل: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.chmod(temporary_name, 0o600)
        except OSError:
            pass
        os.replace(temporary_name, destination)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def create_encrypted_backup(
    source_path: str | Path,
    destination_path: str | Path,
    passphrase: str,
) -> Path:
    """Create a consistent SQLite snapshot and encrypt it with AES-GCM."""
    source = Path(source_path)
    destination = Path(destination_path)
    if not source.is_file():
        raise BackupError(f"قاعدة البيانات غير موجودة: {source}")
    if source.resolve() == destination.resolve():
        raise BackupError("لا يمكن حفظ النسخة فوق ملف قاعدة البيانات")

    salt = os.urandom(_SALT_SIZE)
    nonce = os.urandom(_NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    source_connection = sqlite3.connect(str(source), timeout=15)
    snapshot = sqlite3.connect(":memory:")
    try:
        source_connection.backup(snapshot)
        _validate_database(snapshot)
        encrypted = AESGCM(key).encrypt(nonce, snapshot.serialize(), MAGIC)
    except sqlite3.Error as exc:
        raise BackupError(f"تعذر إنشاء لقطة قاعدة البيانات: {exc}") from exc
    finally:
        snapshot.close()
        source_connection.close()

    _atomic_write(destination, MAGIC + salt + nonce + encrypted)
    return destination


def _decrypt_backup(backup_path: Path, passphrase: str) -> bytes:
    try:
        data = backup_path.read_bytes()
    except OSError as exc:
        raise BackupError(f"تعذر قراءة ملف النسخة: {exc}") from exc

    header_size = len(MAGIC) + _SALT_SIZE + _NONCE_SIZE
    if len(data) < header_size + 16 or not data.startswith(MAGIC):
        raise BackupError("صيغة ملف النسخة غير معروفة أو تالفة")

    offset = len(MAGIC)
    salt = data[offset : offset + _SALT_SIZE]
    offset += _SALT_SIZE
    nonce = data[offset : offset + _NONCE_SIZE]
    ciphertext = data[header_size:]
    key = _derive_key(passphrase, salt)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, MAGIC)
    except (InvalidTag, ValueError) as exc:
        raise BackupError("عبارة المرور غير صحيحة أو ملف النسخة عُدّل") from exc


def restore_encrypted_backup(
    backup_path: str | Path,
    target_path: str | Path,
    passphrase: str,
) -> Path | None:
    """Validate a backup before atomically replacing a database file.

    Returns the encrypted pre-restore copy when the target already existed.
    The application must be stopped before restoring its active database.
    """
    backup = Path(backup_path)
    target = Path(target_path)
    if backup.resolve() == target.resolve():
        raise BackupError("ملف النسخة لا يمكن أن يكون ملف قاعدة البيانات الهدف")

    plaintext = _decrypt_backup(backup, passphrase)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".restore", dir=target.parent
    )
    temporary_path = Path(temporary_name)
    validation_connection: sqlite3.Connection | None = None
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(plaintext)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass
        validation_connection = sqlite3.connect(str(temporary_path), timeout=15)
        _validate_database(validation_connection)
        validation_connection.close()
        validation_connection = None

        safety_copy: Path | None = None
        if target.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            safety_copy = target.with_name(f"{target.name}.pre-restore-{stamp}.instdb")
            create_encrypted_backup(target, safety_copy, passphrase)

        for suffix in ("-wal", "-shm"):
            Path(f"{target}{suffix}").unlink(missing_ok=True)
        os.replace(temporary_path, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    except (OSError, sqlite3.Error) as exc:
        raise BackupError(
            f"تعذرت الاستعادة. أوقف التطبيق وتأكد من صلاحيات المجلد: {exc}"
        ) from exc
    finally:
        if validation_connection is not None:
            validation_connection.close()
        temporary_path.unlink(missing_ok=True)

    return safety_copy