"""``mutiny db backup`` / ``mutiny db restore`` — Hosted SQLite operator tooling."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _load_backup_module():
    try:
        from mutiny_api import backup as backup_mod
    except ImportError as exc:  # pragma: no cover - workspace always has api
        print(
            "error: mutiny db requires the Hosted package mutiny-api "
            "(install via the Mutiny workspace: uv sync).",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    return backup_mod


def add_db_parser(subparsers: argparse._SubParsersAction) -> None:
    db_p = subparsers.add_parser(
        "db",
        help=(
            "Operator tools for Hosted SQLite lineage data "
            "(backup / restore; not a customer project API)"
        ),
    )
    db_sub = db_p.add_subparsers(dest="db_command", required=True)

    backup_p = db_sub.add_parser(
        "backup",
        help=(
            "Create a transactionally consistent SQLite backup "
            "(SQLite online backup API; WAL-aware)"
        ),
    )
    backup_p.add_argument(
        "--db",
        type=Path,
        default=None,
        help=(
            "Source database path (overrides MUTINY_DB_PATH; "
            "default: data/mutiny.sqlite)"
        ),
    )
    backup_p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Destination backup file path",
    )
    backup_p.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace destination if it already exists",
    )

    restore_p = db_sub.add_parser(
        "restore",
        help=(
            "Replace a Hosted SQLite database from a validated backup "
            "(destructive; requires --force when destination exists)"
        ),
    )
    restore_p.add_argument(
        "--from",
        dest="restore_from",
        type=Path,
        required=True,
        help="Validated backup SQLite file to restore from",
    )
    restore_p.add_argument(
        "--db",
        type=Path,
        default=None,
        help=(
            "Destination database path (overrides MUTINY_DB_PATH; "
            "default: data/mutiny.sqlite)"
        ),
    )
    restore_p.add_argument(
        "--force",
        action="store_true",
        help="Required to overwrite an existing destination database",
    )


def run_db_command(args: argparse.Namespace) -> int:
    backup_mod = _load_backup_module()

    if args.db_command == "backup":
        return _run_backup(backup_mod, args)
    if args.db_command == "restore":
        return _run_restore(backup_mod, args)
    print(f"error: unknown db command: {args.db_command}", file=sys.stderr)
    return 2


def _run_backup(backup_mod, args: argparse.Namespace) -> int:
    try:
        source = backup_mod.resolve_operator_db_path(args.db)
    except Exception as exc:
        print(f"error: invalid database path config: {exc}", file=sys.stderr)
        return 2

    print(f"source database: {source}")
    print(f"backup destination: {args.out}")

    try:
        dest = backup_mod.backup_database(
            source,
            args.out,
            overwrite=bool(args.overwrite),
        )
    except backup_mod.BackupValidationError as exc:
        print(f"error: source validation failed: {exc}", file=sys.stderr)
        return 1
    except backup_mod.BackupError as exc:
        msg = str(exc)
        # User/config mistakes (missing source, dest exists) → exit 2
        if "does not exist" in msg or "already exists" in msg or "must be" in msg:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"error: backup failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: backup failed: {exc}", file=sys.stderr)
        return 1

    print(f"backup ok: {dest}")
    print(
        "note: backup files contain Hosted lineage and may include sensitive "
        "operational data — store and transmit them securely."
    )
    return 0


def _run_restore(backup_mod, args: argparse.Namespace) -> int:
    try:
        destination = backup_mod.resolve_operator_db_path(args.db)
    except Exception as exc:
        print(f"error: invalid database path config: {exc}", file=sys.stderr)
        return 2

    print(f"restore source: {args.restore_from}")
    print(f"destination database: {destination}")

    if destination.exists() and not args.force:
        print(
            "error: destination exists; refusing silent overwrite "
            "(re-run with --force)",
            file=sys.stderr,
        )
        return 2

    try:
        dest, rollback = backup_mod.restore_database(
            args.restore_from,
            destination,
            force=bool(args.force),
        )
    except backup_mod.BackupValidationError as exc:
        print(f"error: backup validation failed: {exc}", file=sys.stderr)
        return 1
    except backup_mod.RestoreError as exc:
        msg = str(exc)
        if "refusing silent overwrite" in msg or "does not exist" in msg:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"error: restore failed: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: restore failed: {exc}", file=sys.stderr)
        return 1

    print(f"restore ok: {dest}")
    if rollback is not None:
        print(f"previous database preserved at: {rollback}")
    print(
        "note: restore is a destructive operator operation; keep off-host "
        "copies of backups. Local backup ≠ off-site backup."
    )
    return 0
