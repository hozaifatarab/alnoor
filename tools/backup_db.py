"""Create or restore an encrypted SQLite database backup.

Usage::

    python tools/backup_db.py backup [backup-file]
    python tools/backup_db.py restore backup-file [--target database-file]
"""
from __future__ import annotations

import _bootstrap  # noqa: F401

import argparse
from datetime import datetime
from getpass import getpass
from pathlib import Path
import sys

from core import backup, config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="نسخ واستعادة قاعدة بيانات مشفّرة")
    commands = parser.add_subparsers(dest="action", required=True)

    create = commands.add_parser("backup", help="إنشاء نسخة مشفّرة متسقة")
    create.add_argument("file", nargs="?", type=Path, help="مسار ملف النسخة")
    create.add_argument("--gui", action="store_true", help="إدخال عبارة المرور في نافذة مخفية")

    restore = commands.add_parser("restore", help="استعادة نسخة مشفّرة")
    restore.add_argument("file", type=Path, help="ملف النسخة المشفّرة")
    restore.add_argument("--target", type=Path, help="قاعدة الهدف (الافتراضي قاعدة النظام)")
    restore.add_argument("--gui", action="store_true", help="إدخال عبارة المرور في نافذة مخفية")
    return parser


def _read_passphrase_gui(confirm: bool) -> str:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title("عبارة مرور النسخة المشفّرة")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    fields: list[tk.Entry] = []
    tk.Label(root, text="أدخل عبارة مرور من 12 حرفاً على الأقل:").grid(
        row=0, column=0, columnspan=2, padx=12, pady=(12, 4), sticky="w"
    )
    first = tk.Entry(root, show="*", width=36)
    first.grid(row=1, column=0, columnspan=2, padx=12, pady=4)
    fields.append(first)
    if confirm:
        tk.Label(root, text="أعد كتابة العبارة للتأكيد:").grid(
            row=2, column=0, columnspan=2, padx=12, pady=(8, 4), sticky="w"
        )
        second = tk.Entry(root, show="*", width=36)
        second.grid(row=3, column=0, columnspan=2, padx=12, pady=4)
        fields.append(second)

    result: dict[str, str] = {}

    def accept() -> None:
        value = fields[0].get()
        if len(value) < 12:
            messagebox.showerror("عبارة قصيرة", "يجب أن تتكون العبارة من 12 حرفاً على الأقل", parent=root)
            return
        if confirm and fields[1].get() != value:
            messagebox.showerror("عدم تطابق", "العبارتان غير متطابقتين", parent=root)
            return
        result["passphrase"] = value
        root.destroy()

    def cancel() -> None:
        root.destroy()

    button_row = 4 if confirm else 2
    tk.Button(root, text="موافق", command=accept, default="active").grid(
        row=button_row, column=0, padx=12, pady=12, sticky="e"
    )
    tk.Button(root, text="إلغاء", command=cancel).grid(
        row=button_row, column=1, padx=12, pady=12, sticky="w"
    )
    root.bind("<Return>", lambda _event: accept())
    fields[0].focus_set()
    root.mainloop()
    if not result:
        raise backup.BackupError("أُلغيت العملية")
    return result["passphrase"]


def _read_passphrase(confirm: bool, use_gui: bool = False) -> str:
    if use_gui:
        return _read_passphrase_gui(confirm)
    passphrase = getpass("عبارة مرور التشفير (12 حرفاً على الأقل): ")
    if len(passphrase) < 12:
        raise backup.BackupError("عبارة المرور يجب أن تكون 12 حرفاً على الأقل")
    if confirm and getpass("أعد كتابة عبارة المرور: ") != passphrase:
        raise backup.BackupError("عبارتا المرور غير متطابقتين")
    return passphrase


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        passphrase = _read_passphrase(
            confirm=args.action == "backup", use_gui=args.gui
        )
        if args.action == "backup":
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            destination = args.file or (config.data_dir() / "backups" / f"school-{stamp}.instdb")
            backup.create_encrypted_backup(config.db_path(), destination, passphrase)
            print(f"تم إنشاء نسخة مشفّرة: {destination}")
            return 0

        target = args.target or config.db_path()
        if not sys.stdin.isatty():
            raise backup.BackupError("الاستعادة تتطلب طرفية تفاعلية للتأكيد")
        print("أوقف التطبيق قبل استعادة قاعدة البيانات.")
        if input(f"اكتب RESTORE لتأكيد الاستبدال: ").strip() != "RESTORE":
            raise backup.BackupError("أُلغيت الاستعادة")
        safety_copy = backup.restore_encrypted_backup(args.file, target, passphrase)
        print(f"تمت الاستعادة إلى: {target}")
        if safety_copy:
            print(f"نسخة القاعدة السابقة: {safety_copy}")
        return 0
    except backup.BackupError as exc:
        print(f"خطأ: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())