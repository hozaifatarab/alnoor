"""اختبارات طبقة قاعدة البيانات: الهجرات، القيود، المعاملات."""
from __future__ import annotations

import unittest
import sqlite3
import tempfile
from pathlib import Path

from core import backup, config, db
from core.exceptions import BusinessRuleError, DuplicateError, ValidationError

from .base import DbTestCase


class MigrationTests(DbTestCase):
    def test_migration_applied_once(self) -> None:
        applied = db.init_db()
        self.assertEqual(applied, [], "لا يجب تطبيق هجرات مكررة")
        self.assertNotEqual(db.schema_version(), "none")

    def test_core_tables_exist(self) -> None:
        names = {
            row["name"]
            for row in db.query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        for expected in (
            "users",
            "settings",
            "academic_years",
            "terms",
            "levels",
            "classes",
            "subjects",
            "teachers",
            "students",
            "enrollments",
            "finance_fee_items",
            "finance_invoices",
            "finance_payments",
            "teaching_assignments",
            "audit_log",
            "schema_version",
        ):
            self.assertIn(expected, names)

    def test_settings_defaults_inserted(self) -> None:
        from core.repos import settings as settings_repo

        values = settings_repo.all_settings()
        self.assertIn("institution_name", values)
        self.assertTrue(values["institution_name"])


class ConstraintTests(DbTestCase):
    def test_foreign_key_enforced(self) -> None:
        with self.assertRaises(BusinessRuleError):
            db.execute(
                "INSERT INTO classes(name, level_id, year_id, capacity) VALUES (?, ?, ?, ?)",
                ("ب", 9999, 9999, 30),
            )

    def test_unique_violation_maps_to_duplicate_error(self) -> None:
        db.execute("INSERT INTO levels(name) VALUES (?)", ("مرحلة أ",))
        with self.assertRaises(DuplicateError):
            db.execute("INSERT INTO levels(name) VALUES (?)", ("مرحلة أ",))

    def test_check_violation_maps_to_validation_error(self) -> None:
        with self.assertRaises(ValidationError):
            db.execute(
                "INSERT INTO students(student_no, full_name, status) VALUES (?, ?, ?)",
                ("S-1", "طالب اختبار", "حالة غير مسموحة"),
            )

    def test_foreign_keys_pragma_enabled(self) -> None:
        self.assertEqual(db.scalar("PRAGMA foreign_keys"), 1)


class TransactionTests(DbTestCase):
    def test_rollback_on_error(self) -> None:
        with self.assertRaises(RuntimeError):
            with db.transaction() as conn:
                conn.execute("INSERT INTO levels(name) VALUES (?)", ("مرحلة مؤقتة",))
                raise RuntimeError("فشل مقصود")
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM levels WHERE name = ?", ("مرحلة مؤقتة",)), 0)

    def test_commit_persists(self) -> None:
        with db.transaction() as conn:
            conn.execute("INSERT INTO levels(name) VALUES (?)", ("مرحلة ثابتة",))
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM levels WHERE name = ?", ("مرحلة ثابتة",)), 1)


class BackupRestoreTests(DbTestCase):
    PASSPHRASE = "Correct Horse Battery 2026!"

    def test_encrypted_backup_restores_consistent_snapshot(self) -> None:
        db.execute("INSERT INTO levels(name) VALUES (?)", ("قبل النسخة",))
        with tempfile.TemporaryDirectory() as directory:
            backup_path = Path(directory) / "school.instdb"
            restored_path = Path(directory) / "restored.db"
            backup.create_encrypted_backup(config.db_path(), backup_path, self.PASSPHRASE)

            db.execute("INSERT INTO levels(name) VALUES (?)", ("بعد النسخة",))
            safety_copy = backup.restore_encrypted_backup(
                backup_path, restored_path, self.PASSPHRASE
            )

            self.assertIsNone(safety_copy)
            restored = sqlite3.connect(restored_path)
            try:
                names = [row[0] for row in restored.execute("SELECT name FROM levels")]
            finally:
                restored.close()
            self.assertEqual(names, ["قبل النسخة"])

    def test_wrong_passphrase_does_not_replace_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backup_path = Path(directory) / "school.instdb"
            target_path = Path(directory) / "target.db"
            backup.create_encrypted_backup(config.db_path(), backup_path, self.PASSPHRASE)
            target = sqlite3.connect(target_path)
            try:
                target.execute("CREATE TABLE marker(value TEXT)")
                target.execute("INSERT INTO marker VALUES ('keep')")
                target.commit()
            finally:
                target.close()

            with self.assertRaises(backup.BackupError):
                backup.restore_encrypted_backup(backup_path, target_path, "wrong passphrase")

            target = sqlite3.connect(target_path)
            try:
                marker = target.execute("SELECT value FROM marker").fetchone()[0]
            finally:
                target.close()
            self.assertEqual(marker, "keep")

    def test_tampered_backup_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backup_path = Path(directory) / "school.instdb"
            backup.create_encrypted_backup(config.db_path(), backup_path, self.PASSPHRASE)
            data = bytearray(backup_path.read_bytes())
            data[-1] ^= 1
            backup_path.write_bytes(data)

            with self.assertRaises(backup.BackupError):
                backup.restore_encrypted_backup(
                    backup_path, Path(directory) / "restored.db", self.PASSPHRASE
                )

    def test_existing_backup_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            backup_path = Path(directory) / "school.instdb"
            backup_path.write_bytes(b"keep")

            with self.assertRaises(backup.BackupError):
                backup.create_encrypted_backup(config.db_path(), backup_path, self.PASSPHRASE)

            self.assertEqual(backup_path.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
