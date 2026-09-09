"""P2-6: Hosted SQLite backup / restore durability."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest

from mutiny_api import backup as backup_mod
from mutiny_api.backup import (
    COMPATIBLE_SCHEMA_VERSIONS,
    BackupError,
    BackupValidationError,
    RestoreError,
    backup_database,
    resolve_operator_db_path,
    restore_database,
    validate_database,
)
from mutiny_api.db import DB_PATH_ENV, SCHEMA_VERSION, connect
from mutiny_api.repository import Repository
from mutiny_cli.main import main
from mutiny_core.redact import redact_secrets


def _seed_lineage(db_path: Path) -> dict[str, str]:
    conn = connect(db_path)
    repo = Repository(conn)
    project = repo.create_project(
        name="backup-proj",
        path="local_key:backup-proj",
        adapter="openai_agents",
    )
    campaign_id = "camp-backup-1"
    repo.create_campaign(
        campaign_id,
        {"n": 1, "g": 1},
        project_id=project["id"],
        status="completed",
    )
    cand_id = "cand-backup-1"
    repo.upsert_candidate(
        candidate_id=cand_id,
        campaign_id=campaign_id,
        parent_id=None,
        generation=0,
        genome={"prompt": "probe"},
        fitness=1.0,
        status="done",
        violated=True,
        hits=[{"rule_id": "refund_limit"}],
    )
    repo.upsert_trace(
        cand_id,
        {"turns": [{"role": "user", "content": "hi"}]},
    )
    repo.append_event(campaign_id, "campaign_started", {"ok": True})
    regression = repo.save_regression(
        "reg-backup-1",
        campaign_id=campaign_id,
        candidate_id=cand_id,
        path=".mutiny/tests/reg-backup-1.json",
        artifact={
            "id": "reg-backup-1",
            "name": "reg-backup-1",
            "genome": {"prompt": "probe"},
        },
    )
    # test_runs via direct insert if helper is awkward
    conn.execute(
        "INSERT INTO test_runs "
        "(id, regression_id, status, duration_ms, policy_version, agent_version, "
        "fixed_agent, violated_rule_ids_json, evidence_json, summary, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "tr-backup-1",
            regression["id"],
            "failed",
            12.5,
            "1",
            "1",
            0,
            "[]",
            "[]",
            "seed",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    conn.commit()
    # Confirm WAL mode for durability tests
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"
    conn.close()
    return {
        "project_id": project["id"],
        "campaign_id": campaign_id,
        "candidate_id": cand_id,
        "regression_id": regression["id"],
        "test_run_id": "tr-backup-1",
    }


def _assert_lineage(db_path: Path, ids: dict[str, str]) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        assert (
            conn.execute(
                "SELECT name FROM projects WHERE id = ?", (ids["project_id"],)
            ).fetchone()[0]
            == "backup-proj"
        )
        assert (
            conn.execute(
                "SELECT id FROM campaigns WHERE id = ?", (ids["campaign_id"],)
            ).fetchone()
            is not None
        )
        assert (
            conn.execute(
                "SELECT id FROM candidates WHERE id = ?", (ids["candidate_id"],)
            ).fetchone()
            is not None
        )
        assert (
            conn.execute(
                "SELECT candidate_id FROM traces WHERE candidate_id = ?",
                (ids["candidate_id"],),
            ).fetchone()
            is not None
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM events WHERE campaign_id = ?",
                (ids["campaign_id"],),
            ).fetchone()[0]
            >= 1
        )
        assert (
            conn.execute(
                "SELECT id FROM regressions WHERE id = ?", (ids["regression_id"],)
            ).fetchone()
            is not None
        )
        assert (
            conn.execute(
                "SELECT id FROM test_runs WHERE id = ?", (ids["test_run_id"],)
            ).fetchone()
            is not None
        )
        version = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()[0]
        assert version == SCHEMA_VERSION
    finally:
        conn.close()


def test_01_backup_produces_valid_sqlite(tmp_path: Path) -> None:
    src = tmp_path / "live.sqlite"
    ids = _seed_lineage(src)
    out = tmp_path / "backups" / "copy.sqlite"
    backup_database(src, out)
    result = validate_database(out)
    assert result.integrity_ok
    assert result.schema_version == SCHEMA_VERSION
    _assert_lineage(out, ids)
    assert src.is_file()  # never delete source


def test_02_backup_while_open_with_wal_and_commits(tmp_path: Path) -> None:
    src = tmp_path / "wal_live.sqlite"
    ids = _seed_lineage(src)
    # Keep a live connection open; write more committed txs while backing up.
    live = sqlite3.connect(str(src), timeout=30.0)
    live.execute("PRAGMA journal_mode = WAL")
    live.execute(
        "INSERT INTO events (campaign_id, ts, type, payload_json) VALUES (?, ?, ?, ?)",
        (ids["campaign_id"], "2026-01-02T00:00:00+00:00", "tick", "{}"),
    )
    live.commit()
    live.execute(
        "INSERT INTO events (campaign_id, ts, type, payload_json) VALUES (?, ?, ?, ?)",
        (ids["campaign_id"], "2026-01-03T00:00:00+00:00", "tick2", "{}"),
    )
    live.commit()

    out = tmp_path / "wal_backup.sqlite"
    backup_database(src, out)
    live.close()

    conn = sqlite3.connect(str(out))
    types = {
        r[0]
        for r in conn.execute(
            "SELECT type FROM events WHERE campaign_id = ?", (ids["campaign_id"],)
        ).fetchall()
    }
    conn.close()
    assert "tick" in types
    assert "tick2" in types
    validate_database(out)


def test_03_overwrite_refused_without_flag(tmp_path: Path) -> None:
    src = tmp_path / "src.sqlite"
    _seed_lineage(src)
    out = tmp_path / "out.sqlite"
    backup_database(src, out)
    with pytest.raises(BackupError, match="already exists"):
        backup_database(src, out, overwrite=False)


def test_04_overwrite_flag_replaces(tmp_path: Path) -> None:
    src = tmp_path / "src.sqlite"
    _seed_lineage(src)
    out = tmp_path / "out.sqlite"
    backup_database(src, out)
    # mutate source and overwrite backup
    conn = connect(src)
    Repository(conn).append_event("camp-backup-1", "later", {"n": 1})
    conn.close()
    backup_database(src, out, overwrite=True)
    conn = sqlite3.connect(str(out))
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM events WHERE type = 'later'"
        ).fetchone()[0]
        == 1
    )
    conn.close()


def test_05_failed_backup_leaves_no_partial_dest(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "src.sqlite"
    _seed_lineage(src)
    out = tmp_path / "dest.sqlite"

    def boom(*_a, **_k):
        raise BackupError("simulated incomplete backup")

    monkeypatch.setattr(backup_mod, "_online_backup", boom)
    with pytest.raises(BackupError, match="simulated"):
        backup_database(src, out)
    assert not out.exists()
    leftovers = list(tmp_path.glob(".dest.sqlite.mutiny-backup-*.tmp"))
    assert leftovers == []


def test_06_validate_integrity_and_schema(tmp_path: Path) -> None:
    src = tmp_path / "ok.sqlite"
    _seed_lineage(src)
    result = validate_database(src)
    assert result.schema_version in COMPATIBLE_SCHEMA_VERSIONS
    assert "campaigns" in result.tables

    junk = tmp_path / "junk.sqlite"
    junk.write_text("not-sqlite", encoding="utf-8")
    with pytest.raises(BackupValidationError):
        validate_database(junk)


def test_07_incompatible_schema_version_refused(tmp_path: Path) -> None:
    src = tmp_path / "future.sqlite"
    _seed_lineage(src)
    conn = sqlite3.connect(str(src))
    conn.execute(
        "UPDATE schema_meta SET value = ? WHERE key = 'version'",
        ("999",),
    )
    conn.commit()
    conn.close()
    with pytest.raises(BackupValidationError, match="incompatible"):
        validate_database(src)
    out = tmp_path / "nope.sqlite"
    with pytest.raises(BackupValidationError, match="incompatible"):
        backup_database(src, out)
    assert not out.exists()


def test_08_restore_preserves_lineage_tables(tmp_path: Path) -> None:
    src = tmp_path / "src.sqlite"
    ids = _seed_lineage(src)
    bak = tmp_path / "bak.sqlite"
    backup_database(src, bak)

    dest = tmp_path / "fresh" / "mutiny.sqlite"
    restore_database(bak, dest, force=False)
    _assert_lineage(dest, ids)


def test_09_restore_requires_force_when_dest_exists(tmp_path: Path) -> None:
    src = tmp_path / "src.sqlite"
    _seed_lineage(src)
    bak = tmp_path / "bak.sqlite"
    backup_database(src, bak)
    dest = tmp_path / "dest.sqlite"
    _seed_lineage(dest)
    with pytest.raises(RestoreError, match="refusing silent overwrite"):
        restore_database(bak, dest, force=False)


def test_10_restore_force_keeps_rollback_backup(tmp_path: Path) -> None:
    original = tmp_path / "active.sqlite"
    ids_old = _seed_lineage(original)
    # Distinct second DB
    newer = tmp_path / "newer.sqlite"
    conn = connect(newer)
    Repository(conn).create_project(
        name="newer-only",
        path="local_key:newer-only",
        adapter="openai_agents",
    )
    conn.close()
    bak = tmp_path / "newer.bak.sqlite"
    backup_database(newer, bak)

    dest, rollback = restore_database(bak, original, force=True)
    assert dest == original
    assert rollback is not None and rollback.is_file()
    # New content present
    conn = sqlite3.connect(str(original))
    assert (
        conn.execute(
            "SELECT name FROM projects WHERE name = 'newer-only'"
        ).fetchone()
        is not None
    )
    conn.close()
    # Rollback holds prior lineage
    _assert_lineage(rollback, ids_old)


def test_11_path_precedence_explicit_over_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_db = tmp_path / "from_env.sqlite"
    explicit = tmp_path / "from_cli.sqlite"
    monkeypatch.setenv(DB_PATH_ENV, str(env_db))
    monkeypatch.setenv("MUTINY_API_TOKEN", "should-not-select-db")
    assert resolve_operator_db_path(explicit) == explicit
    assert resolve_operator_db_path(None) == env_db


def test_12_cli_backup_restore_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    src = tmp_path / "cli_src.sqlite"
    ids = _seed_lineage(src)
    out = tmp_path / "cli_out.sqlite"
    monkeypatch.delenv(DB_PATH_ENV, raising=False)

    code = main(["db", "backup", "--db", str(src), "--out", str(out)])
    assert code == 0
    assert out.is_file()

    dest = tmp_path / "restored.sqlite"
    code = main(
        ["db", "restore", "--from", str(out), "--db", str(dest)]
    )
    assert code == 0
    _assert_lineage(dest, ids)

    # overwrite without --overwrite → non-zero
    code = main(["db", "backup", "--db", str(src), "--out", str(out)])
    assert code == 2

    # restore without --force when dest exists → non-zero
    code = main(
        ["db", "restore", "--from", str(out), "--db", str(dest)]
    )
    assert code == 2

    code = main(
        [
            "db",
            "restore",
            "--from",
            str(out),
            "--db",
            str(dest),
            "--force",
        ]
    )
    assert code == 0


def test_13_cli_help_lists_db_commands() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["db", "--help"])
    assert exc.value.code == 0

    with pytest.raises(SystemExit) as exc:
        main(["db", "backup", "--help"])
    assert exc.value.code == 0

    with pytest.raises(SystemExit) as exc:
        main(["db", "restore", "--help"])
    assert exc.value.code == 0


def test_14_cli_honors_mutiny_db_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "env_src.sqlite"
    _seed_lineage(src)
    monkeypatch.setenv(DB_PATH_ENV, str(src))
    monkeypatch.setenv("MUTINY_API_TOKEN", "token-not-a-path")
    out = tmp_path / "from_env_backup.sqlite"
    code = main(["db", "backup", "--out", str(out)])
    assert code == 0
    captured = capsys.readouterr()
    assert str(src) in captured.out
    assert out.is_file()


def test_15_missing_source_fails_clearly(tmp_path: Path) -> None:
    missing = tmp_path / "nope.sqlite"
    with pytest.raises(BackupError, match="does not exist"):
        backup_database(missing, tmp_path / "out.sqlite")
    code = main(
        [
            "db",
            "backup",
            "--db",
            str(missing),
            "--out",
            str(tmp_path / "out.sqlite"),
        ]
    )
    assert code == 2


def test_16_redact_secrets_not_weakened() -> None:
    # Behavioral: still redacts credential keys
    assert redact_secrets({"api_key": "sk-secret"})["api_key"] == "[REDACTED]"
    # Backup module must not disable or bypass redaction helpers
    backup_src = inspect.getsource(backup_mod)
    assert "MUTINY_DISABLE_SECRET_REDACTION" not in backup_src
    assert "redact_secrets" not in backup_src  # physical backup; no secret dump path


def test_17_no_http_db_backup_routes() -> None:
    from mutiny_api.app import create_app

    app = create_app()
    paths = {getattr(r, "path", "") for r in app.routes}
    for forbidden in (
        "/api/db/backup",
        "/api/db/export",
        "/api/db/restore",
        "/api/backup",
        "/api/restore",
    ):
        assert forbidden not in paths


def test_18_backup_does_not_mutate_source_schema_meta(tmp_path: Path) -> None:
    src = tmp_path / "src.sqlite"
    _seed_lineage(src)
    before = sqlite3.connect(str(src)).execute(
        "SELECT value FROM schema_meta WHERE key='version'"
    ).fetchone()[0]
    backup_database(src, tmp_path / "out.sqlite")
    after = sqlite3.connect(str(src)).execute(
        "SELECT value FROM schema_meta WHERE key='version'"
    ).fetchone()[0]
    assert before == after == SCHEMA_VERSION
