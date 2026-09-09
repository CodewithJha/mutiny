"""SQLite schema and connection helpers. Core never imports this module."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# Authoritative Hosted API DB path resolution (M-PR4).
# Precedence: explicit argument → MUTINY_DB_PATH → DEFAULT_DB_PATH.
DB_PATH_ENV = "MUTINY_DB_PATH"
DEFAULT_DB_PATH = Path("data/mutiny.sqlite")


class DatabaseConfigError(ValueError):
    """Invalid or unusable database path configuration."""


def resolve_db_path(explicit: str | Path | None = None) -> Path:
    """Resolve the Hosted API SQLite file path.

    Precedence:
      1. ``explicit`` (constructor / test fixture)
      2. ``MUTINY_DB_PATH`` environment variable
      3. ``data/mutiny.sqlite`` (safe local default)

    Empty explicit/env values raise ``DatabaseConfigError``. There is no
    silent fallback to another database location.
    """
    if explicit is not None:
        raw = str(explicit).strip()
        if not raw:
            raise DatabaseConfigError("database path is empty")
        return Path(raw).expanduser()

    if DB_PATH_ENV in os.environ:
        raw = os.environ.get(DB_PATH_ENV, "").strip()
        if not raw:
            raise DatabaseConfigError(
                f"{DB_PATH_ENV} is set but empty; unset it or provide a path"
            )
        return Path(raw).expanduser()

    return DEFAULT_DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    adapter TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    metrics_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    project_id TEXT REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    parent_id TEXT,
    generation INTEGER NOT NULL DEFAULT 0,
    genome_json TEXT NOT NULL,
    fitness REAL,
    status TEXT NOT NULL,
    violated INTEGER NOT NULL DEFAULT 0,
    hits_json TEXT,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE IF NOT EXISTS traces (
    candidate_id TEXT PRIMARY KEY,
    trace_json TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    client_event_id TEXT,
    payload_hash TEXT,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE IF NOT EXISTS regressions (
    id TEXT PRIMARY KEY,
    campaign_id TEXT,
    candidate_id TEXT,
    path TEXT,
    artifact_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS test_runs (
    id TEXT PRIMARY KEY,
    regression_id TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms REAL,
    policy_version TEXT,
    agent_version TEXT,
    fixed_agent INTEGER NOT NULL DEFAULT 0,
    violated_rule_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    summary TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (regression_id) REFERENCES regressions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_candidates_campaign ON candidates(campaign_id);
CREATE INDEX IF NOT EXISTS idx_events_campaign ON events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
CREATE INDEX IF NOT EXISTS idx_projects_path ON projects(path);
CREATE INDEX IF NOT EXISTS idx_test_runs_regression ON test_runs(regression_id);
CREATE INDEX IF NOT EXISTS idx_test_runs_created ON test_runs(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_client_id
    ON events(campaign_id, client_event_id)
    WHERE client_event_id IS NOT NULL;
"""
# NOTE: idx_campaigns_project is created in migrate() after ensuring project_id
# exists — CREATE TABLE IF NOT EXISTS will not add project_id to older DBs, so
# indexing it inside SCHEMA would fail before migrate() can ALTER.

SCHEMA_VERSION = "11"


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def migrate(conn: sqlite3.Connection) -> None:
    """Bring an existing DB up to the current schema (idempotent)."""
    # Fresh installs get project_id from CREATE TABLE; older DBs need ALTER.
    if "campaigns" in {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }:
        cols = _table_columns(conn, "campaigns")
        if "project_id" not in cols:
            conn.execute(
                "ALTER TABLE campaigns ADD COLUMN project_id TEXT "
                "REFERENCES projects(id)"
            )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_campaigns_project ON campaigns(project_id)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_path ON projects(path)")
    # Milestone D: test_runs history (CREATE IF NOT EXISTS is idempotent).
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS test_runs (
            id TEXT PRIMARY KEY,
            regression_id TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms REAL,
            policy_version TEXT,
            agent_version TEXT,
            fixed_agent INTEGER NOT NULL DEFAULT 0,
            violated_rule_ids_json TEXT NOT NULL DEFAULT '[]',
            evidence_json TEXT NOT NULL DEFAULT '[]',
            summary TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (regression_id) REFERENCES regressions(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_test_runs_regression ON test_runs(regression_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_test_runs_created ON test_runs(created_at)"
    )
    # M-PR8B: client event IDs for ingest idempotency (older DBs need ALTER).
    if "events" in {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }:
        ev_cols = _table_columns(conn, "events")
        if "client_event_id" not in ev_cols:
            conn.execute("ALTER TABLE events ADD COLUMN client_event_id TEXT")
        if "payload_hash" not in ev_cols:
            conn.execute("ALTER TABLE events ADD COLUMN payload_hash TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_client_id "
        "ON events(campaign_id, client_event_id) "
        "WHERE client_event_id IS NOT NULL"
    )


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open (and migrate) the SQLite DB at ``db_path``.

    Parent directories are created when missing (existing Hosted contract).
    Failures raise; callers must not catch and silently open another path.
    """
    path = Path(db_path)
    if not str(path).strip() or str(path).strip() == ".":
        raise DatabaseConfigError(f"invalid database path: {db_path!r}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DatabaseConfigError(
            f"cannot create database parent directory for {path}: {exc}"
        ) from exc

    try:
        conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
    except sqlite3.Error as exc:
        raise DatabaseConfigError(
            f"cannot open SQLite database at {path}: {exc}"
        ) from exc

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(SCHEMA)
    migrate(conn)
    conn.execute(
        "INSERT INTO schema_meta(key, value) VALUES('version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (SCHEMA_VERSION,),
    )
    conn.commit()
    return conn
