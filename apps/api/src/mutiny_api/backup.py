"""Operator SQLite backup / restore for Hosted lineage data.

Uses SQLite's online backup API (``Connection.backup``) for a transactionally
consistent snapshot — including committed WAL frames — without copying
``-wal`` / ``-shm`` sidecars by hand.

This module is CLI/operator tooling only. It must not be exposed as a Hosted
HTTP filesystem or DB API.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from mutiny_api.db import SCHEMA_VERSION, resolve_db_path

REQUIRED_TABLES: frozenset[str] = frozenset(
    {
        "projects",
        "campaigns",
        "candidates",
        "traces",
        "events",
        "regressions",
        "test_runs",
        "schema_meta",
    }
)

# Exact match: future / foreign schema versions must not silently restore.
COMPATIBLE_SCHEMA_VERSIONS: frozenset[str] = frozenset({SCHEMA_VERSION})

ROLLBACK_SUFFIX = ".pre-restore.bak"


class BackupError(Exception):
    """Backup or path configuration failure."""


class RestoreError(Exception):
    """Destructive restore failure or refused without confirmation."""


class BackupValidationError(Exception):
    """SQLite file failed open / integrity / schema checks."""


@dataclass(frozen=True)
class ValidationResult:
    path: Path
    schema_version: str
    integrity_ok: bool
    tables: frozenset[str]


def resolve_operator_db_path(explicit: str | Path | None = None) -> Path:
    """Resolve DB path for operator CLI (same precedence as Hosted API).

    Precedence: explicit CLI ``--db`` → ``MUTINY_DB_PATH`` → ``data/mutiny.sqlite``.
    ``MUTINY_API_TOKEN`` and other env vars never select the database path.
    """
    return resolve_db_path(explicit)


def validate_database(
    path: str | Path,
    *,
    require_schema_version: bool = True,
) -> ValidationResult:
    """Open ``path`` read-only and verify integrity + Mutiny schema contract.

    Does **not** run migrations or mutate the file.
    """
    db_path = Path(path).expanduser()
    if not db_path.is_file():
        raise BackupValidationError(f"database file does not exist: {db_path}")

    try:
        conn = sqlite3.connect(
            f"file:{db_path.resolve()}?mode=ro",
            uri=True,
            timeout=30.0,
        )
    except sqlite3.Error as exc:
        raise BackupValidationError(
            f"not a valid SQLite database at {db_path}: {exc}"
        ) from exc

    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or str(integrity[0]) != "ok":
            detail = integrity[0] if integrity else "unknown"
            raise BackupValidationError(
                f"PRAGMA integrity_check failed for {db_path}: {detail}"
            )

        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise BackupValidationError(
                f"database at {db_path} missing required tables: {missing}"
            )

        if "schema_meta" not in tables:
            raise BackupValidationError(
                f"database at {db_path} missing schema_meta"
            )
        version_row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()
        if version_row is None:
            raise BackupValidationError(
                f"database at {db_path} has no schema_meta.version"
            )
        schema_version = str(version_row[0])
        if require_schema_version and schema_version not in COMPATIBLE_SCHEMA_VERSIONS:
            raise BackupValidationError(
                f"schema version {schema_version!r} is incompatible with this "
                f"Mutiny build (compatible: {sorted(COMPATIBLE_SCHEMA_VERSIONS)}; "
                "refusing silent upgrade/downgrade)"
            )
        return ValidationResult(
            path=db_path,
            schema_version=schema_version,
            integrity_ok=True,
            tables=frozenset(tables),
        )
    except BackupValidationError:
        raise
    except sqlite3.Error as exc:
        raise BackupValidationError(
            f"not a valid SQLite database at {db_path}: {exc}"
        ) from exc
    finally:
        conn.close()


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return os.path.normpath(str(a)) == os.path.normpath(str(b))


def _temp_sibling(destination: Path, kind: str) -> Path:
    token = uuid.uuid4().hex[:12]
    return destination.with_name(
        f".{destination.name}.mutiny-{kind}-{os.getpid()}-{token}.tmp"
    )


def _remove_if_exists(path: Path) -> None:
    try:
        if path.is_file() or path.is_symlink():
            path.unlink()
    except OSError:
        pass


def _online_backup(source: Path, dest_file: Path) -> None:
    """Copy ``source`` → ``dest_file`` via SQLite backup API (WAL-aware)."""
    src: sqlite3.Connection | None = None
    dst: sqlite3.Connection | None = None
    try:
        src = sqlite3.connect(str(source), timeout=30.0)
        src.execute("PRAGMA busy_timeout = 5000")
        # Do not migrate / rewrite schema_meta — backup must not mutate source.
        dst = sqlite3.connect(str(dest_file), timeout=30.0)
        src.backup(dst)
        dst.commit()
    except sqlite3.Error as exc:
        raise BackupError(
            f"SQLite backup API failed ({source} → {dest_file}): {exc}"
        ) from exc
    finally:
        if dst is not None:
            dst.close()
        if src is not None:
            src.close()


def backup_database(
    source: str | Path,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Create a consistent SQLite backup at ``destination``.

    Failed attempts delete the temp artifact and do not leave an apparently
    valid partial file at ``destination`` (unless overwrite replaced a prior
    good file only after a validated temp succeeded).
    """
    src = Path(source).expanduser()
    dest = Path(destination).expanduser()

    if not src.is_file():
        raise BackupError(f"source database does not exist: {src}")
    if _same_file(src, dest):
        raise BackupError("destination must be a different path than source")

    validate_database(src)

    if dest.exists() and not overwrite:
        raise BackupError(
            f"destination already exists (pass overwrite=True / --overwrite): {dest}"
        )
    if dest.exists() and dest.is_dir():
        raise BackupError(f"destination is a directory: {dest}")

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BackupError(
            f"cannot create destination parent directory {dest.parent}: {exc}"
        ) from exc

    tmp = _temp_sibling(dest, "backup")
    _remove_if_exists(tmp)
    try:
        _online_backup(src, tmp)
        validate_database(tmp)
        # Atomic replace on the same filesystem (POSIX); cross-device moves are
        # not guaranteed atomic — keep dest on the same volume when possible.
        os.replace(str(tmp), str(dest))
    except Exception:
        _remove_if_exists(tmp)
        raise

    return dest


def restore_database(
    source: str | Path,
    destination: str | Path,
    *,
    force: bool = False,
) -> tuple[Path, Path | None]:
    """Replace ``destination`` with a validated copy of ``source``.

    Deliberately destructive. Requires ``force=True`` when ``destination``
    already exists. When practical, the previous destination is preserved as
    ``<destination>.pre-restore.bak`` for rollback.

    Returns ``(destination, rollback_path_or_none)``.
    """
    src = Path(source).expanduser()
    dest = Path(destination).expanduser()

    if not src.is_file():
        raise RestoreError(f"restore source does not exist: {src}")
    if _same_file(src, dest):
        raise RestoreError("restore source and destination must differ")

    validate_database(src)

    if dest.exists() and not force:
        raise RestoreError(
            f"destination database exists; refusing silent overwrite "
            f"(pass --force): {dest}"
        )
    if dest.exists() and dest.is_dir():
        raise RestoreError(f"destination is a directory: {dest}")

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RestoreError(
            f"cannot create destination parent directory {dest.parent}: {exc}"
        ) from exc

    tmp = _temp_sibling(dest, "restore")
    _remove_if_exists(tmp)
    rollback: Path | None = None
    moved_aside = False

    try:
        try:
            _online_backup(src, tmp)
            validate_database(tmp)

            if dest.exists():
                rollback = Path(str(dest) + ROLLBACK_SUFFIX)
                if rollback.exists():
                    rollback = Path(
                        f"{dest}{ROLLBACK_SUFFIX}.{uuid.uuid4().hex[:8]}"
                    )
                os.replace(str(dest), str(rollback))
                moved_aside = True

            os.replace(str(tmp), str(dest))
        except Exception:
            _remove_if_exists(tmp)
            if moved_aside and rollback is not None and rollback.exists():
                # Best-effort: put the original DB back if replace failed.
                try:
                    if not dest.exists():
                        os.replace(str(rollback), str(dest))
                        rollback = None
                except OSError:
                    pass
            raise

        # Re-validate final destination; if this fails, attempt rollback.
        try:
            validate_database(dest)
        except BackupValidationError as exc:
            if rollback is not None and rollback.exists():
                try:
                    _remove_if_exists(dest)
                    os.replace(str(rollback), str(dest))
                    rollback = None
                except OSError as restore_exc:
                    raise RestoreError(
                        f"restored file failed validation ({exc}); also failed "
                        f"to roll back from {rollback}: {restore_exc}"
                    ) from exc
            raise RestoreError(
                f"restored file failed validation; original preserved/restored: {exc}"
            ) from exc
    except (BackupError, BackupValidationError) as exc:
        raise RestoreError(str(exc)) from exc

    return dest, rollback
