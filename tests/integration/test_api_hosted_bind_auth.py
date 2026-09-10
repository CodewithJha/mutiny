"""P0-1 / P0-4 integration: bind fail-closed + Bearer + P0-3 / M-PR8E intact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app
from mutiny_api.auth import API_TOKEN_ENV
from mutiny_api.bind_security import BindSecurityError, require_token_for_non_loopback_bind
from mutiny_api.ingest_schemas import INGEST_SCHEMA_VERSION
from mutiny_api.serve import run_server
from mutiny_cli import run_cmd
from mutiny_core import __version__ as MUTINY_CORE_VERSION

FAKE_TOKEN = "test-mutiny-bind-auth-p0-not-real"
WRONG_TOKEN = "wrong-mutiny-bind-auth-p0"
MARKER_NAME = "MUTINY_P0_BIND_MARKER"
MARKER_VALUE = "untouched"


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "bind_auth.sqlite"


@pytest.fixture
def auth_on(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv(API_TOKEN_ENV, FAKE_TOKEN)
    return FAKE_TOKEN


@pytest.fixture
def client(api_db: Path, auth_on: str):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


def _auth(token: str = FAKE_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _hostile_project(root: Path) -> Path:
    project = root / "hostile"
    mutiny = project / ".mutiny"
    mutiny.mkdir(parents=True)
    (mutiny / "adapter.py").write_text(
        "def create_adapter():\n"
        f"    open({MARKER_NAME!r}, 'w').write('executed')\n"
        "    raise RuntimeError('should not run')\n",
        encoding="utf-8",
    )
    (project / "policy.yaml").write_text(
        "version: '1'\ntarget: t\nrules: []\n",
        encoding="utf-8",
    )
    (project / MARKER_NAME).write_text(MARKER_VALUE, encoding="utf-8")
    return project


# —— Cases 12–14: Bearer still protects; health/meta public ——


def test_12_valid_token_protects_endpoint(client: TestClient) -> None:
    denied = client.get("/api/campaigns")
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "unauthorized"
    ok = client.get("/api/campaigns", headers=_auth())
    assert ok.status_code == 200
    assert "campaigns" in ok.json()


def test_13_invalid_token_rejected(client: TestClient) -> None:
    r = client.get("/api/campaigns", headers=_auth(WRONG_TOKEN))
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    blob = json.dumps(r.json())
    assert FAKE_TOKEN not in blob
    assert WRONG_TOKEN not in blob


def test_14_health_and_meta_public(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["api"] is True
    meta = client.get("/api/meta")
    assert meta.status_code == 200
    safety = meta.json()["safety"]
    assert safety["auth_required"] is True
    assert safety["auth_env"] == API_TOKEN_ENV
    blob = json.dumps(meta.json())
    assert FAKE_TOKEN not in blob


# —— Cases 15–16: P0-3 / exec removal still hold with valid token ——


def test_15_p0_3_fs_removed_with_valid_token(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    r = client.get(
        "/api/policies/content",
        params={"project_path": str(project)},
        headers=_auth(),
    )
    assert r.status_code == 410
    assert r.json()["error"]["code"] == "hosted_filesystem_access_removed"
    assert marker.read_text(encoding="utf-8") == MARKER_VALUE


def test_16_allow_project_exec_ignored_with_valid_token(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    r = client.post(
        "/api/campaigns",
        headers=_auth(),
        json={
            "population_size": 2,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": str(project),
        },
    )
    assert r.status_code == 410
    assert r.json()["error"]["code"] == "hosted_customer_execution_removed"
    assert marker.read_text(encoding="utf-8") == MARKER_VALUE


# —— Case 17: ingest still works with valid auth ——


def test_17_ingest_works_with_valid_auth(client: TestClient) -> None:
    body = {
        "schema_version": INGEST_SCHEMA_VERSION,
        "mutiny_version": MUTINY_CORE_VERSION,
        "execution_mode": "local_cli",
        "redaction": {"applied": True, "marker": "[REDACTED]"},
        "campaign_id": "camp-bind-auth-17",
        "local_project_key": "cli:bind-auth",
        "attestation": True,
        "config": {"population_size": 2, "max_generations": 1},
    }
    denied = client.post("/api/ingest/v1/campaigns", json=body)
    assert denied.status_code == 401
    created = client.post(
        "/api/ingest/v1/campaigns", headers=_auth(), json=body
    )
    assert created.status_code == 201, created.text
    assert created.json()["created"] is True
    assert created.json()["campaign"]["id"] == "camp-bind-auth-17"


# —— Case 18: local CLI unaffected ——


def test_18_local_cli_unaffected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(API_TOKEN_ENV, raising=False)
    (tmp_path / ".mutiny").mkdir()
    (tmp_path / ".mutiny" / "adapter.py").write_text(
        "def create_adapter():\n    raise RuntimeError('not called')\n",
        encoding="utf-8",
    )
    (tmp_path / "policy.yaml").write_text(
        'version: "1"\ntarget: t\nrules:\n'
        "  - id: r1\n    description: d\n    tool: t\n    kind: deny_tool\n",
        encoding="utf-8",
    )
    (tmp_path / "mutiny.yaml").write_text(
        "population_size: 2\nmax_generations: 1\nelite_count: 1\n"
        "max_turns: 2\nrng_seed: 0\nuse_boundary_seeds: false\n"
        "hosted:\n  api_url: http://127.0.0.1:8000\n",
        encoding="utf-8",
    )

    from mutiny_core.campaign.engine import CampaignResult

    sync = MagicMock(return_value=0)
    local = MagicMock(
        return_value=run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="local-bind",
            result=CampaignResult(
                status="completed",
                reason="gmax",
                generations_completed=0,
                candidates=[],
            ),
        )
    )
    monkeypatch.setattr(run_cmd, "_run_local_with_hosted_sync", sync)
    monkeypatch.setattr(run_cmd, "_run_local", local)

    code = run_cmd.run_campaign(project_root=tmp_path)
    out = capsys.readouterr().out
    assert code == 0
    assert "Execution mode: local" in out
    sync.assert_not_called()
    local.assert_called_once()


# —— Startup boundary still enforced under integration import path ——


def test_non_loopback_startup_fails_before_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(API_TOKEN_ENV, raising=False)
    calls: list[Any] = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: calls.append(True))
    with pytest.raises(BindSecurityError):
        run_server(host="0.0.0.0", port=8000)
    assert calls == []
    # Validation helper itself is the contract boundary used by serve.
    with pytest.raises(BindSecurityError):
        require_token_for_non_loopback_bind("10.1.2.3")
