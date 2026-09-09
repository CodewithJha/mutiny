"""P1-2: Hosted API rate limiting + abuse controls (integration)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app
from mutiny_api.auth import API_TOKEN_ENV
from mutiny_api.ingest_schemas import INGEST_SCHEMA_VERSION
from mutiny_api.rate_limit import (
    ENABLED_ENV,
    EXPENSIVE_BURST_ENV,
    EXPENSIVE_RPM_ENV,
    HEALTH_BURST_ENV,
    HEALTH_RPM_ENV,
    INGEST_BURST_ENV,
    INGEST_RPM_ENV,
    NORMAL_BURST_ENV,
    NORMAL_RPM_ENV,
    RateLimiter,
    load_rate_limit_config,
)

ROOT = Path(__file__).resolve().parents[2]
FAKE_TOKEN = "test-mutiny-rate-limit-token-p12-not-real"
WRONG_TOKEN = "wrong-mutiny-rate-limit-token-p12"


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "rate_limit.sqlite"


@pytest.fixture
def tight_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENABLED_ENV, "1")
    monkeypatch.setenv(NORMAL_RPM_ENV, "60")
    monkeypatch.setenv(NORMAL_BURST_ENV, "3")
    monkeypatch.setenv(EXPENSIVE_RPM_ENV, "60")
    monkeypatch.setenv(EXPENSIVE_BURST_ENV, "2")
    monkeypatch.setenv(INGEST_RPM_ENV, "60")
    monkeypatch.setenv(INGEST_BURST_ENV, "2")
    monkeypatch.setenv(HEALTH_RPM_ENV, "600")
    monkeypatch.setenv(HEALTH_BURST_ENV, "50")
    monkeypatch.setenv(API_TOKEN_ENV, FAKE_TOKEN)


@pytest.fixture
def client(api_db: Path, tight_limits: None):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


def _auth(token: str = FAKE_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ingest_open(external_suffix: str) -> dict[str, Any]:
    return {
        "schema_version": INGEST_SCHEMA_VERSION,
        "mutiny_version": "0.1.0",
        "execution_mode": "local_cli",
        "redaction": {"applied": True, "marker": "[REDACTED]"},
        "campaign_id": str(uuid.uuid4()),
        "local_project_key": f"proj-{external_suffix}",
        "project_name": "demo",
        "project_label": "/tmp/never-open-me",
        "attestation": True,
        "status": "created",
        "config": {"population_size": 1, "max_generations": 1, "rng_seed": 1},
    }


def _assert_429(r: Any) -> None:
    assert r.status_code == 429, r.text
    body = r.json()
    assert body["error"]["code"] == "rate_limit_exceeded"
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) >= 0
    blob = json.dumps(body) + json.dumps(dict(r.headers))
    assert FAKE_TOKEN not in blob
    assert WRONG_TOKEN not in blob


# —— 1–4: normal limit + 429 shape ——


def test_01_under_normal_limit_succeeds(client: TestClient) -> None:
    for _ in range(3):
        r = client.get("/api/campaigns", headers=_auth())
        assert r.status_code == 200, r.text


def test_02_03_04_exceed_normal_limit_429_code_retry_after(
    client: TestClient,
) -> None:
    for _ in range(3):
        assert client.get("/api/campaigns", headers=_auth()).status_code == 200
    r = client.get("/api/campaigns", headers=_auth())
    _assert_429(r)
    assert int(r.headers["Retry-After"]) >= 1


def test_05_limit_recovers_with_fake_time(
    api_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENABLED_ENV, "1")
    monkeypatch.setenv(NORMAL_RPM_ENV, "60")
    monkeypatch.setenv(NORMAL_BURST_ENV, "1")
    monkeypatch.setenv(API_TOKEN_ENV, FAKE_TOKEN)
    app = create_app(api_db)

    class Clock:
        def __init__(self) -> None:
            self.t = 100.0

        def __call__(self) -> float:
            return self.t

    clock = Clock()
    cfg = load_rate_limit_config()
    app.state.rate_limiter = RateLimiter(cfg, time_fn=clock)

    with TestClient(app) as c:
        assert c.get("/api/campaigns", headers=_auth()).status_code == 200
        _assert_429(c.get("/api/campaigns", headers=_auth()))
        clock.t += 1.1
        assert c.get("/api/campaigns", headers=_auth()).status_code == 200


# —— 6–7: expensive stricter ——


def test_06_07_expensive_stricter_than_normal(client: TestClient) -> None:
    bodies = {
        "target": "in_process_demo",
        "rng_seed": 1,
        "population_size": 1,
        "max_generations": 1,
    }
    assert client.post("/api/campaigns", headers=_auth(), json=bodies).status_code == 201
    assert client.post("/api/campaigns", headers=_auth(), json=bodies).status_code == 201
    r_exp = client.post("/api/campaigns", headers=_auth(), json=bodies)
    _assert_429(r_exp)
    r_norm = client.get("/api/projects", headers=_auth())
    assert r_norm.status_code == 200


# —— 8: ingest limited ——


def test_08_ingest_rate_limited(client: TestClient) -> None:
    codes = []
    for i in range(4):
        codes.append(
            client.post(
                "/api/ingest/v1/campaigns",
                headers=_auth(),
                json=_ingest_open(str(i)),
            ).status_code
        )
    assert 429 in codes
    assert 201 in codes


# —— 9: categories isolated (HTTP) ——


def test_09_categories_isolated_http(client: TestClient) -> None:
    for _ in range(3):
        assert client.get("/api/campaigns", headers=_auth()).status_code == 200
    _assert_429(client.get("/api/campaigns", headers=_auth()))
    assert client.get("/api/health").status_code == 200
    r = client.post(
        "/api/ingest/v1/campaigns",
        headers=_auth(),
        json=_ingest_open("isol"),
    )
    assert r.status_code == 201, r.text


# —— 10–11: health/meta under normal exhaustion ——


def test_10_11_health_and_meta_under_normal_exhaustion(client: TestClient) -> None:
    for _ in range(3):
        client.get("/api/campaigns", headers=_auth())
    _assert_429(client.get("/api/campaigns", headers=_auth()))
    assert client.get("/api/health").status_code == 200
    meta = client.get("/api/meta")
    assert meta.status_code == 200
    safety = meta.json()["safety"]
    assert safety["rate_limits"] == "in_process"
    assert safety["rate_limits_distributed"] is False


# —— 12–14: auth interaction ——


def test_12_protected_still_requires_auth(client: TestClient) -> None:
    r = client.get("/api/campaigns")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_13_invalid_auth_does_not_bypass_rate_limit(client: TestClient) -> None:
    for _ in range(3):
        r = client.get("/api/campaigns", headers=_auth(WRONG_TOKEN))
        assert r.status_code in {401, 429}
    r = client.get("/api/campaigns", headers=_auth(WRONG_TOKEN))
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limit_exceeded"


def test_14_valid_auth_does_not_bypass_rate_limit(client: TestClient) -> None:
    for _ in range(3):
        assert client.get("/api/campaigns", headers=_auth()).status_code == 200
    _assert_429(client.get("/api/campaigns", headers=_auth()))


# —— 15–16: P0 regressions with limiter active ——


def test_15_p0_3_filesystem_protection_intact(client: TestClient) -> None:
    r = client.get(
        "/api/policies",
        headers=_auth(),
        params={"project_path": "examples/openai_support_agent"},
    )
    assert r.status_code == 410
    assert r.json()["error"]["code"] == "hosted_filesystem_access_removed"


def test_16_customer_execution_still_removed(client: TestClient) -> None:
    r = client.post(
        "/api/campaigns",
        headers=_auth(),
        json={
            "target": "openai_agents",
            "project_path": "examples/openai_support_agent",
            "rng_seed": 1,
            "population_size": 1,
            "max_generations": 1,
        },
    )
    assert r.status_code == 410
    assert r.json()["error"]["code"] == "hosted_customer_execution_removed"


# —— 20: local CLI unaffected ——


def test_20_local_cli_unaffected() -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{ROOT / 'packages' / 'mutiny_cli' / 'src'}:"
            f"{ROOT / 'packages' / 'mutiny_core' / 'src'}:"
            f"{ROOT / 'packages' / 'mutiny_openai_agents' / 'src'}"
        ),
    }
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from mutiny_cli.main import main; raise SystemExit(main(['--help']))",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "usage" in proc.stdout.lower() or "mutiny" in proc.stdout.lower()
    import mutiny_core

    src = Path(mutiny_core.__file__).resolve().parent
    assert not (src / "rate_limit.py").exists()


# —— 21–22: ingest contract + campaign under limit ——


def test_21_22_ingest_and_campaign_under_limit(
    api_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENABLED_ENV, "1")
    monkeypatch.setenv(NORMAL_BURST_ENV, "50")
    monkeypatch.setenv(EXPENSIVE_BURST_ENV, "20")
    monkeypatch.setenv(INGEST_BURST_ENV, "20")
    monkeypatch.setenv(API_TOKEN_ENV, FAKE_TOKEN)
    app = create_app(api_db)
    with TestClient(app) as c:
        open_r = c.post(
            "/api/ingest/v1/campaigns",
            headers=_auth(),
            json=_ingest_open("under-limit"),
        )
        assert open_r.status_code == 201, open_r.text

        camp = c.post(
            "/api/campaigns",
            headers=_auth(),
            json={
                "target": "in_process_demo",
                "rng_seed": 1,
                "population_size": 2,
                "max_generations": 1,
            },
        )
        assert camp.status_code == 201, camp.text
        assert camp.json()["status"] == "created"


# —— X-Forwarded-For not trusted for bypass ——


def test_xff_does_not_create_separate_bypass_bucket(client: TestClient) -> None:
    for _ in range(3):
        assert client.get("/api/campaigns", headers=_auth()).status_code == 200
    _assert_429(client.get("/api/campaigns", headers=_auth()))
    r = client.get(
        "/api/campaigns",
        headers={**_auth(), "X-Forwarded-For": "203.0.113.99"},
    )
    _assert_429(r)


def test_create_app_rejects_zero_rpm(
    api_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(NORMAL_RPM_ENV, "0")
    with pytest.raises(Exception, match="> 0"):
        create_app(api_db)
