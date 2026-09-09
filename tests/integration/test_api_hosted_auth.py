"""M-PR7: Hosted single-tenant Bearer authentication."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app
from mutiny_api.auth import (
    API_TOKEN_ENV,
    auth_required,
    configured_api_token,
    extract_bearer_token,
    tokens_match,
)
from mutiny_cli import run_cmd


FAKE_TOKEN = "test-mutiny-api-token-mpr7-not-real"
WRONG_TOKEN = "wrong-mutiny-api-token-mpr7"


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "auth_test.sqlite"


@pytest.fixture
def auth_on(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv(API_TOKEN_ENV, FAKE_TOKEN)
    return FAKE_TOKEN


@pytest.fixture
def auth_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(API_TOKEN_ENV, raising=False)


@pytest.fixture
def client(api_db: Path, auth_on: str):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_no_auth(api_db: Path, auth_off: None):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


def _auth_headers(token: str = FAKE_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _assert_unauthorized(r: Any) -> None:
    assert r.status_code == 401, r.text
    body = r.json()
    assert body["error"]["code"] == "unauthorized"
    assert "authentication required" in body["error"]["message"].lower()
    blob = json.dumps(body)
    assert FAKE_TOKEN not in blob
    assert WRONG_TOKEN not in blob


# —— Helpers ——


def test_token_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(API_TOKEN_ENV, raising=False)
    assert configured_api_token() is None
    assert auth_required() is False

    monkeypatch.setenv(API_TOKEN_ENV, f"  {FAKE_TOKEN}  ")
    assert configured_api_token() == FAKE_TOKEN
    assert auth_required() is True

    assert extract_bearer_token(f"Bearer {FAKE_TOKEN}") == FAKE_TOKEN
    assert extract_bearer_token(f"bearer {FAKE_TOKEN}") == FAKE_TOKEN
    assert extract_bearer_token("Basic abc") is None
    assert extract_bearer_token(None) is None
    assert tokens_match(provided=FAKE_TOKEN, expected=FAKE_TOKEN) is True
    assert tokens_match(provided=WRONG_TOKEN, expected=FAKE_TOKEN) is False


# —— Test A: protected without credentials ——


def test_a_protected_without_credentials(client: TestClient) -> None:
    r = client.get("/api/campaigns")
    _assert_unauthorized(r)


# —— Test B: protected with invalid credentials ——


def test_b_protected_with_invalid_credentials(client: TestClient) -> None:
    r = client.get("/api/campaigns", headers=_auth_headers(WRONG_TOKEN))
    _assert_unauthorized(r)


# —— Test C: protected with valid credentials ——


def test_c_protected_with_valid_credentials(client: TestClient) -> None:
    r = client.get("/api/campaigns", headers=_auth_headers())
    assert r.status_code == 200
    assert "campaigns" in r.json()


# —— Test D: health public ——


def test_d_health_public_with_auth_enabled(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["api"] is True
    assert FAKE_TOKEN not in json.dumps(body)


# —— Test E: meta public, no token leak ——


def test_e_meta_public_no_token_leak(client: TestClient) -> None:
    r = client.get("/api/meta")
    assert r.status_code == 200
    safety = r.json()["safety"]
    assert safety["auth_required"] is True
    assert safety["auth_env"] == API_TOKEN_ENV
    blob = json.dumps(r.json())
    assert FAKE_TOKEN not in blob
    assert "Bearer" not in blob


def test_e_meta_auth_disabled_flag(client_no_auth: TestClient) -> None:
    r = client_no_auth.get("/api/meta")
    assert r.status_code == 200
    assert r.json()["safety"]["auth_required"] is False


# —— Test F: campaign create/start unauthenticated ——


def test_f_campaign_control_unauthenticated(client: TestClient, api_db: Path) -> None:
    before = api_db.read_bytes() if api_db.exists() else b""
    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 2,
            "max_generations": 1,
            "elite_count": 1,
            "max_turns": 2,
            "target": "in_process_demo",
        },
    )
    _assert_unauthorized(created)
    # No successful campaign create side effect
    listed = client.get("/api/campaigns", headers=_auth_headers())
    assert listed.status_code == 200
    assert listed.json()["campaigns"] == []

    started = client.post(
        "/api/campaigns/nonexistent/start",
        json={"attestation": True},
    )
    _assert_unauthorized(started)
    # DB may have been opened by lifespan, but campaign table empty is enough.
    _ = before


# —— Test G: traces / evidence ——


def test_g_traces_unauthenticated(client: TestClient) -> None:
    _assert_unauthorized(client.get("/api/candidates/fake-id"))
    _assert_unauthorized(client.get("/api/campaigns/fake-id/candidates"))
    _assert_unauthorized(client.get("/api/campaigns/fake-id"))


# —— Test H: policies ——


def test_h_policies_unauthenticated(client: TestClient) -> None:
    _assert_unauthorized(client.get("/api/policies"))
    _assert_unauthorized(client.get("/api/policies/content"))
    _assert_unauthorized(
        client.put(
            "/api/policies/content",
            json={"content": "version: '1'\ntarget: t\nrules: []\n"},
        )
    )


# —— Test I: regressions ——


def test_i_regressions_unauthenticated(client: TestClient) -> None:
    _assert_unauthorized(client.get("/api/regressions"))
    _assert_unauthorized(client.get("/api/regressions/fake"))
    _assert_unauthorized(client.delete("/api/regressions/fake"))


# —— Test J: tests / minimization ——


def test_j_tests_and_minimize_unauthenticated(client: TestClient) -> None:
    _assert_unauthorized(client.get("/api/tests/summary"))
    _assert_unauthorized(client.get("/api/tests/runs"))
    _assert_unauthorized(
        client.post("/api/tests/run", json={"run_all": True})
    )
    _assert_unauthorized(
        client.post("/api/candidates/fake/minimize", json={})
    )


# —— Test K: SSE ——


def test_k_sse_requires_auth(client: TestClient) -> None:
    _assert_unauthorized(client.get("/api/campaigns/fake/events"))

    # Valid token reaches campaign lookup (404), proving auth passed.
    ok = client.get(
        "/api/campaigns/fake/events",
        headers=_auth_headers(),
    )
    assert ok.status_code == 404
    assert ok.json()["error"]["code"] == "campaign_not_found"


# —— Test L: CLI Hosted auth headers (M-PR8C ingest sync) ——


def test_l_cli_hosted_sends_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from mutiny_cli import hosted_sync

    monkeypatch.setenv(API_TOKEN_ENV, FAKE_TOKEN)
    headers = hosted_sync.auth_headers_from_env()
    assert headers == {"Authorization": f"Bearer {FAKE_TOKEN}"}

    seen: dict[str, Any] = {}

    class FakeResp:
        def __init__(self, status_code: int, body: dict[str, Any] | None = None):
            self.status_code = status_code
            self._body = body or {}
            self.text = json.dumps(self._body)

        def json(self) -> dict[str, Any]:
            return self._body

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            seen["headers"] = kwargs.get("headers") or {}

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def post(self, path: str, json: dict[str, Any] | None = None) -> FakeResp:
            seen["path"] = path
            return FakeResp(201, {"campaign_id": "camp-1", "created": True})

    import httpx

    monkeypatch.setattr(httpx, "Client", FakeClient)
    client = hosted_sync.HostedIngestClient(
        "http://127.0.0.1:8000", headers=headers
    )
    client.open_campaign(
        {
            "schema_version": 1,
            "redaction": {"applied": True},
            "campaign_id": "camp-1",
            "local_project_key": "cli:test",
            "attestation": True,
            "config": {},
        }
    )
    assert seen["headers"].get("Authorization") == f"Bearer {FAKE_TOKEN}"
    assert "ingest" in seen["path"]


def test_l_cli_hosted_missing_token_when_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """After local success, missing token yields sync failure (exit 3), not silent local-only."""
    from mutiny_cli.hosted_sync import SYNC_FAILED_EXIT, SyncOutcome
    from mutiny_core.campaign.engine import CampaignResult

    monkeypatch.delenv(API_TOKEN_ENV, raising=False)

    def fake_local(
        root: Path, config: dict[str, Any], policy: Any, **kwargs: Any
    ) -> run_cmd.LocalRunOutcome:
        return run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="camp-auth-miss",
            result=CampaignResult(
                status="completed",
                reason="gmax",
                generations_completed=1,
                candidates=[],
                best=None,
                violated=False,
                events_emitted=0,
            ),
            events=[],
        )

    monkeypatch.setattr(run_cmd, "_run_local", fake_local)
    monkeypatch.setattr(
        run_cmd,
        "sync_local_campaign",
        lambda *a, **k: SyncOutcome(
            ok=False,
            message="Hosted authentication failed (set a valid MUTINY_API_TOKEN)",
            error_code="unauthorized",
            http_status=401,
        ),
    )

    code = run_cmd._run_local_with_hosted_sync(
        root=tmp_path,
        config={},
        policy=MagicMock(version="1", target="t"),
        api_url="http://127.0.0.1:8000",
        ui_url="http://127.0.0.1:3000",
    )
    err = capsys.readouterr().err
    assert code == SYNC_FAILED_EXIT
    assert "MUTINY_API_TOKEN" in err or "authentication" in err.lower()
    assert "synchronization failed" in err.lower()


# —— Test M: CLI local unchanged ——


def test_m_cli_local_no_hosted_token(
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

    sync = MagicMock(return_value=0)
    from mutiny_core.campaign.engine import CampaignResult

    local = MagicMock(
        return_value=run_cmd.LocalRunOutcome(
            exit_code=0,
            campaign_id="local-only",
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


# —— Test N: auth does not bypass M-PR8E removal ——


def test_n_auth_does_not_bypass_kill_switch(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    project = tmp_path / "cust"
    project.mkdir()
    (project / ".mutiny").mkdir()
    marker = project / "ADAPTER_EXECUTED"
    (project / ".mutiny" / "adapter.py").write_text(
        f"from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        f"def create_adapter():\n"
        f"    raise RuntimeError('should not load')\n",
        encoding="utf-8",
    )
    (project / "policy.yaml").write_text(
        'version: "1"\ntarget: openai_agents_project\nrules:\n'
        "  - id: refund_limit\n    description: d\n    tool: issue_refund\n"
        "    kind: require_args\n    when:\n      amount: {gt: 200}\n"
        "    require:\n      approved: {eq: true}\n",
        encoding="utf-8",
    )

    r = client.post(
        "/api/campaigns",
        headers=_auth_headers(),
        json={
            "population_size": 2,
            "max_generations": 1,
            "elite_count": 1,
            "max_turns": 2,
            "target": "openai_agents",
            "project_path": str(project),
        },
    )
    assert r.status_code == 410, r.text
    assert r.json()["error"]["code"] == "hosted_customer_execution_removed"
    assert not marker.exists()


# —— E2E: unauthenticated reject / authenticated success ——


def test_e2e_campaign_auth_gate(client: TestClient) -> None:
    payload = {
        "population_size": 2,
        "max_generations": 1,
        "elite_count": 1,
        "max_turns": 2,
        "target": "in_process_demo",
        "rng_seed": 0,
    }
    denied = client.post("/api/campaigns", json=payload)
    _assert_unauthorized(denied)

    created = client.post("/api/campaigns", headers=_auth_headers(), json=payload)
    assert created.status_code == 201, created.text
    camp_id = created.json()["id"]
    assert camp_id

    # Still rejected without credentials after a campaign exists
    _assert_unauthorized(client.get(f"/api/campaigns/{camp_id}"))
    got = client.get(f"/api/campaigns/{camp_id}", headers=_auth_headers())
    assert got.status_code == 200
    assert got.json()["id"] == camp_id


def test_auth_disabled_allows_local_demo(client_no_auth: TestClient) -> None:
    r = client_no_auth.get("/api/campaigns")
    assert r.status_code == 200
