"""SQLite schema and connection helpers. Core never imports this module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

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
"""
# NOTE: idx_campaigns_project is created in migrate() after ensuring project_id
# exists — CREATE TABLE IF NOT EXISTS will not add project_id to older DBs, so
# indexing it inside SCHEMA would fail before migrate() can ALTER.

SCHEMA_VERSION = "10"


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


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30.0)
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
