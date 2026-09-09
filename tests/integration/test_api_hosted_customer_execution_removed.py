"""M-PR8E security: Hosted customer execution permanently removed (410 Gone)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app


MARKER_NAME = "MUTINY_MPR8E_EXECUTED"


@pytest.fixture
def api_db(tmp_path: Path) -> Path:
    return tmp_path / "test_mutiny.sqlite"


@pytest.fixture
def client(api_db: Path):
    app = create_app(api_db)
    with TestClient(app) as c:
        yield c


def _hostile_project(tmp_path: Path, *, name: str = "hostile") -> Path:
    root = tmp_path / name
    mutiny = root / ".mutiny"
    mutiny.mkdir(parents=True)
    marker = root / MARKER_NAME
    (mutiny / "adapter.py").write_text(
        f"""\
from pathlib import Path
Path({str(marker)!r}).write_text("executed", encoding="utf-8")

def create_adapter():
    raise RuntimeError("hostile adapter must never run on Hosted")
""",
        encoding="utf-8",
    )
    (root / "policy.yaml").write_text(
        "version: '1'\ntarget: mpr8e_probe\nrules: []\n",
        encoding="utf-8",
    )
    return root


def _assert_removed(resp, marker: Path | None = None) -> None:
    assert resp.status_code == 410, resp.text
    body = resp.json()
    assert body["error"]["code"] == "hosted_customer_execution_removed"
    assert body["error"]["status"] == 410
    assert "removed" in body["error"]["message"].lower()
    if marker is not None:
        assert not marker.exists(), "adapter.py must not have been executed"


# —— 1–6: customer execution removed ——


def test_01_create_campaign_rejects_customer_start(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MUTINY_ALLOW_PROJECT_EXEC", raising=False)
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    r = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": str(project),
        },
    )
    _assert_removed(r, marker)


def test_02_project_path_cannot_trigger_execution(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    with patch(
        "mutiny_openai_agents.loader.load_adapter_factory",
        side_effect=AssertionError("load_adapter_factory"),
    ) as load_mock:
        with patch.object(
            Path, "write_text", wraps=Path.write_text
        ):
            r = client.post(
                "/api/campaigns",
                json={
                    "population_size": 2,
                    "max_generations": 1,
                    "target": "openai_agents",
                    "project_path": str(project),
                },
            )
        _assert_removed(r, marker)
        load_mock.assert_not_called()


def test_03_allow_project_exec_cannot_restore(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    r = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": str(project),
        },
    )
    _assert_removed(r, marker)
    meta = client.get("/api/meta").json()["safety"]
    assert meta["hosted_customer_adapter_exec"] is False
    assert meta["hosted_customer_execution"] == "removed"
    assert meta["hosted_customer_adapter_exec_env_effect"] == "ignored"


def test_04_load_adapter_factory_not_called_on_customer_path(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    project = _hostile_project(tmp_path)
    with patch(
        "mutiny_openai_agents.loader.load_adapter_factory",
        side_effect=AssertionError("must not call"),
    ) as mocked:
        r = client.post(
            "/api/campaigns",
            json={
                "population_size": 2,
                "max_generations": 1,
                "target": "openai_agents",
                "project_path": str(project),
            },
        )
        _assert_removed(r)
        mocked.assert_not_called()


def test_05_exec_module_not_reached(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "true")
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    with patch(
        "importlib.util.spec_from_file_location",
        side_effect=AssertionError("spec_from_file_location"),
    ):
        r = client.post(
            "/api/campaigns",
            json={
                "population_size": 2,
                "max_generations": 1,
                "target": "openai_agents",
                "project_path": str(project),
            },
        )
    _assert_removed(r, marker)


def test_06_project_id_cannot_bypass_supervisor(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    created = client.post(
        "/api/projects",
        json={"path": str(project), "name": "Hostile"},
    )
    assert created.status_code == 201, created.text
    assert not marker.exists()
    via_id = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "target": "openai_agents",
            "project_id": created.json()["id"],
        },
    )
    _assert_removed(via_id, marker)


# —— 7–10: path safety ——


def test_07_absolute_path_rejected_without_execution(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    r = client.post(
        "/api/campaigns",
        json={
            "population_size": 2,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": str(project.resolve()),
        },
    )
    _assert_removed(r, marker)


def test_08_traversal_path_cannot_access_fs_via_exec(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    traversal = str(tmp_path / ".." / tmp_path.name / project.name)
    r = client.post(
        "/api/campaigns",
        json={
            "population_size": 2,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": traversal,
        },
    )
    _assert_removed(r, marker)


def test_09_relative_module_style_path_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    r = client.post(
        "/api/campaigns",
        json={
            "population_size": 2,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": "examples/openai_support_agent",
        },
    )
    _assert_removed(r)


def test_10_path_like_payload_without_adapter_still_gone(
    client: TestClient, tmp_path: Path
) -> None:
    empty = tmp_path / "empty_dir"
    empty.mkdir()
    r = client.post(
        "/api/campaigns",
        json={
            "population_size": 2,
            "max_generations": 1,
            "target": "openai_agents",
            "project_path": str(empty),
        },
    )
    # Retired before path validation / adapter existence checks.
    _assert_removed(r)


# —— 11–13: CLI regressions covered elsewhere; Hosted meta here ——


def test_11_meta_and_health_advertise_removal(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    meta = client.get("/api/meta").json()["safety"]
    assert meta["hosted_customer_adapter_exec"] is False
    assert meta["hosted_customer_execution"] == "removed"
    assert meta["hosted_customer_filesystem"] == "removed"
    health = client.get("/api/health").json()
    assert health["adapter_loading"] == "trusted_demo_only"


# —— 14: trusted demo ——


def test_14_trusted_demo_campaign_still_works(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 4,
            "max_generations": 1,
            "elite_count": 1,
            "stop_on_first_violation": True,
            "max_turns": 2,
            "rng_seed": 0,
            "target": "in_process_demo",
        },
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    started = client.post(
        f"/api/campaigns/{cid}/start", json={"attestation": True}
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"

    deadline = time.time() + 30.0
    while time.time() < deadline:
        body = client.get(f"/api/campaigns/{cid}").json()
        if body["status"] not in {"created", "running"}:
            assert body["status"] in {"violation", "completed", "failed"}
            return
        time.sleep(0.05)
    raise AssertionError("demo campaign did not finish")


# —— 15–17: ingestion / auth / redaction smoke on same app ——


def test_15_ingest_open_still_works_without_exec(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    with patch(
        "mutiny_openai_agents.loader.load_adapter_factory",
        side_effect=AssertionError("ingest must not load adapters"),
    ):
        r = client.post(
            "/api/ingest/v1/campaigns",
            json={
                "schema_version": 1,
                "mutiny_version": "0.1.0",
                "execution_mode": "local_cli",
                "redaction": {"applied": True, "marker": "[REDACTED]"},
                "campaign_id": "camp-mpr8e-15",
                "local_project_key": "lk-mpr8e-15",
                "config": {
                    "population_size": 2,
                    "max_generations": 1,
                    "target": "openai_agents",
                },
            },
        )
    assert r.status_code == 201, r.text
    assert r.json()["campaign"]["id"] == "camp-mpr8e-15"
    assert not marker.exists()


def test_16_auth_still_gates_campaigns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_API_TOKEN", "secret-mpr8e")
    app = create_app(tmp_path / "auth.sqlite")
    with TestClient(app) as c:
        denied = c.post(
            "/api/campaigns",
            json={
                "population_size": 2,
                "max_generations": 1,
                "target": "in_process_demo",
            },
        )
        assert denied.status_code == 401
        ok = c.post(
            "/api/campaigns",
            headers={"Authorization": "Bearer secret-mpr8e"},
            json={
                "population_size": 2,
                "max_generations": 1,
                "target": "in_process_demo",
            },
        )
        assert ok.status_code == 201, ok.text
        # Customer path still 410 even with valid auth + ALLOW flag
        monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
        project = _hostile_project(tmp_path / "auth_proj")
        gone = c.post(
            "/api/campaigns",
            headers={"Authorization": "Bearer secret-mpr8e"},
            json={
                "population_size": 2,
                "max_generations": 1,
                "target": "openai_agents",
                "project_path": str(project),
            },
        )
        _assert_removed(gone, project / MARKER_NAME)


def test_17_sse_still_works_for_demo(client: TestClient) -> None:
    import time

    created = client.post(
        "/api/campaigns",
        json={
            "population_size": 2,
            "max_generations": 1,
            "elite_count": 1,
            "max_turns": 2,
            "rng_seed": 0,
            "target": "in_process_demo",
        },
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    assert (
        client.post(
            f"/api/campaigns/{cid}/start", json={"attestation": True}
        ).status_code
        == 200
    )
    deadline = time.time() + 30.0
    while time.time() < deadline:
        if client.get(f"/api/campaigns/{cid}").json()["status"] not in {
            "created",
            "running",
        }:
            break
        time.sleep(0.05)
    with client.stream("GET", f"/api/campaigns/{cid}/events") as stream:
        assert stream.status_code == 200
        blob = ""
        for chunk in stream.iter_text():
            blob += chunk
            if "ready" in blob or "campaign." in blob or "candidate." in blob:
                break
            if len(blob) > 50_000:
                break
    assert blob, "SSE should emit at least one event for demo campaign"
