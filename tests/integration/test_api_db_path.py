"""M-PR4: API startup honors MUTINY_DB_PATH (integration)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app
from mutiny_api.db import DB_PATH_ENV, DEFAULT_DB_PATH
from mutiny_api.repository import Repository


@pytest.fixture
def _isolate_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep default-relative paths away from the real developer checkout DB."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(DB_PATH_ENV, raising=False)
    return tmp_path


def test_g_api_startup_honors_mutiny_db_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "api_from_env.sqlite"
    monkeypatch.setenv(DB_PATH_ENV, str(configured))

    app = create_app()
    with TestClient(app) as client:
        assert Path(app.state.db_path) == configured
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["db"] is True
        assert configured.is_file()

        repo: Repository = app.state.repo
        created = repo.create_project(
            name="env-path-api",
            path="/tmp/mutiny-env-path-api",
        )
        assert repo.get_project(created["id"]) is not None


def test_e_api_explicit_path_does_not_touch_default(
    _isolate_cwd: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests must not write into the operator's real default DB file."""
    explicit = tmp_path / "isolated_test.sqlite"
    # Even if env points elsewhere, explicit create_app arg wins.
    monkeypatch.setenv(DB_PATH_ENV, str(tmp_path / "should_not_use.sqlite"))

    app = create_app(explicit)
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        assert Path(app.state.db_path) == explicit
        assert explicit.is_file()
        assert not (tmp_path / "should_not_use.sqlite").exists()
        assert not DEFAULT_DB_PATH.exists()


def test_b_api_env_path_no_default_sidecar(
    _isolate_cwd: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured = tmp_path / "only_here.sqlite"
    monkeypatch.setenv(DB_PATH_ENV, str(configured))

    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/health").json()["db"] is True
        assert configured.is_file()
        assert not (_isolate_cwd / "data" / "mutiny.sqlite").exists()
