"""M-PR4: Hosted SQLite path resolution and hygiene."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mutiny_api.db import (
    DEFAULT_DB_PATH,
    DB_PATH_ENV,
    SCHEMA_VERSION,
    DatabaseConfigError,
    connect,
    resolve_db_path,
)
from mutiny_api.repository import Repository


def test_a_default_path_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DB_PATH_ENV, raising=False)
    assert resolve_db_path() == DEFAULT_DB_PATH
    assert DEFAULT_DB_PATH == Path("data/mutiny.sqlite")


def test_b_env_path_used_exactly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "nested" / "configured.sqlite"
    default_probe = tmp_path / "data" / "mutiny.sqlite"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(DB_PATH_ENV, str(configured))

    resolved = resolve_db_path()
    assert resolved == configured

    conn = connect(resolved)
    conn.close()
    assert configured.is_file()
    assert not default_probe.exists()


def test_c_repository_persists_across_reconnect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "persist.sqlite"
    monkeypatch.setenv(DB_PATH_ENV, str(db))
    path = resolve_db_path()

    conn1 = connect(path)
    repo1 = Repository(conn1)
    created = repo1.create_project(
        name="persist-probe",
        path="/tmp/mutiny-persist-probe",
        adapter="openai_agents",
    )
    project_id = created["id"]
    conn1.close()

    conn2 = connect(path)
    repo2 = Repository(conn2)
    loaded = repo2.get_project(project_id)
    conn2.close()

    assert loaded is not None
    assert loaded["id"] == project_id
    assert loaded["name"] == "persist-probe"
    assert db.is_file()


def test_d_invalid_path_fails_without_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("blocker", encoding="utf-8")
    bad = blocker / "mutiny.sqlite"
    monkeypatch.setenv(DB_PATH_ENV, str(bad))

    path = resolve_db_path()
    assert path == bad
    with pytest.raises((OSError, DatabaseConfigError, sqlite3.Error)):
        connect(path)

    assert not (tmp_path / "data" / "mutiny.sqlite").exists()
    assert not DEFAULT_DB_PATH.exists()


def test_d_empty_env_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DB_PATH_ENV, "   ")
    with pytest.raises(DatabaseConfigError, match=DB_PATH_ENV):
        resolve_db_path()


def test_e_explicit_path_wins_over_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_db = tmp_path / "from_env.sqlite"
    explicit = tmp_path / "from_explicit.sqlite"
    monkeypatch.setenv(DB_PATH_ENV, str(env_db))

    resolved = resolve_db_path(explicit)
    assert resolved == explicit
    conn = connect(resolved)
    conn.close()
    assert explicit.is_file()
    assert not env_db.exists()


def test_f_migrations_on_configured_temp_db(tmp_path: Path) -> None:
    db = tmp_path / "migrate.sqlite"
    conn = connect(db)
    version = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'version'"
    ).fetchone()[0]
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(campaigns)").fetchall()
    }
    conn.close()

    assert version == SCHEMA_VERSION
    assert "projects" in tables
    assert "test_runs" in tables
    assert "project_id" in cols
