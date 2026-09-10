"""P0-3 security: Hosted customer project_path is filesystem-inert (410 Gone)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from mutiny_api.app import create_app
from mutiny_core import __version__ as MUTINY_CORE_VERSION


MARKER_NAME = "MUTINY_P03_MARKER"
MARKER_VALUE = "untouched-p0-3"
HOSTILE_ADAPTER_BODY = """\
from pathlib import Path
Path({marker!r}).write_text("executed", encoding="utf-8")

def create_adapter():
    raise RuntimeError("hostile adapter must never run on Hosted")
"""


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
    marker.write_text(MARKER_VALUE, encoding="utf-8")
    (mutiny / "adapter.py").write_text(
        HOSTILE_ADAPTER_BODY.format(marker=str(marker)),
        encoding="utf-8",
    )
    (root / "policy.yaml").write_text(
        "version: '1'\ntarget: p03_probe\nrules: []\n",
        encoding="utf-8",
    )
    return root


def _assert_fs_removed(resp, marker: Path | None = None) -> None:
    assert resp.status_code == 410, resp.text
    body = resp.json()
    assert body["error"]["code"] == "hosted_filesystem_access_removed"
    assert body["error"]["status"] == 410
    msg = body["error"]["message"].lower()
    assert "filesystem" in msg or "removed" in msg
    assert "mutiny run" in msg or "local" in msg
    if marker is not None:
        assert marker.read_text(encoding="utf-8") == MARKER_VALUE


def _assert_exec_removed(resp, marker: Path | None = None) -> None:
    assert resp.status_code == 410, resp.text
    body = resp.json()
    assert body["error"]["code"] == "hosted_customer_execution_removed"
    if marker is not None:
        assert marker.read_text(encoding="utf-8") == MARKER_VALUE


# —— 1–2: policy content GET/PUT ——


def test_01_get_policy_content_cannot_read_customer_fs(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    secret = project / "policy.yaml"
    before = secret.read_text(encoding="utf-8")
    r = client.get("/api/policies/content", params={"project_path": str(project)})
    _assert_fs_removed(r, marker)
    assert secret.read_text(encoding="utf-8") == before
    assert "p03_probe" not in r.text


def test_02_put_policy_content_cannot_write_customer_fs(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    policy = project / "policy.yaml"
    before = policy.read_text(encoding="utf-8")
    r = client.put(
        "/api/policies/content",
        params={"project_path": str(project)},
        json={"content": "version: '9'\ntarget: hijacked\nrules: []\n"},
    )
    _assert_fs_removed(r, marker)
    assert policy.read_text(encoding="utf-8") == before


# —— 3–7: valid / traversal / absolute ——


def test_03_valid_existing_project_path_cannot_be_read(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path, name="valid_existing")
    marker = project / MARKER_NAME
    r = client.get(
        "/api/policies",
        params={"project_path": str(project.resolve())},
    )
    _assert_fs_removed(r, marker)


def test_04_traversal_path_cannot_be_read(
    client: TestClient, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / MARKER_NAME
    marker.write_text(MARKER_VALUE, encoding="utf-8")
    (outside / "policy.yaml").write_text("version: '1'\ntarget: x\nrules: []\n")
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    traversal = str(decoy / ".." / "outside")
    r = client.get("/api/policies/content", params={"project_path": traversal})
    _assert_fs_removed(r, marker)


def test_05_traversal_path_cannot_be_written(
    client: TestClient, tmp_path: Path
) -> None:
    outside = tmp_path / "outside_w"
    outside.mkdir()
    marker = outside / MARKER_NAME
    marker.write_text(MARKER_VALUE, encoding="utf-8")
    policy = outside / "policy.yaml"
    policy.write_text("version: '1'\ntarget: keep\nrules: []\n", encoding="utf-8")
    before = policy.read_text(encoding="utf-8")
    traversal = str(tmp_path / "nested" / ".." / "outside_w")
    r = client.put(
        "/api/policies/content",
        params={"project_path": traversal},
        json={"content": "version: '2'\ntarget: stolen\nrules: []\n"},
    )
    _assert_fs_removed(r, marker)
    assert policy.read_text(encoding="utf-8") == before


def test_06_absolute_path_cannot_be_read(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    r = client.get(
        "/api/policies/content",
        params={"project_path": str(project.resolve())},
    )
    _assert_fs_removed(r, marker)


def test_07_absolute_path_cannot_be_written(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    policy = project / "policy.yaml"
    before = policy.read_text(encoding="utf-8")
    r = client.put(
        "/api/policies/content",
        params={"project_path": str(project.resolve())},
        json={"content": "version: '3'\ntarget: abs\nrules: []\n"},
    )
    _assert_fs_removed(r, marker)
    assert policy.read_text(encoding="utf-8") == before


# —— 8–9: marker files untouched ——


def test_08_marker_under_project_path_untouched(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    for method, path, kwargs in (
        ("get", "/api/policies", {"params": {"project_path": str(project)}}),
        (
            "get",
            "/api/policies/content",
            {"params": {"project_path": str(project)}},
        ),
        (
            "put",
            "/api/policies/content",
            {
                "params": {"project_path": str(project)},
                "json": {"content": "version: '1'\ntarget: t\nrules: []\n"},
            },
        ),
        (
            "get",
            f"/api/policies/{project.name}",
            {"params": {"project_path": str(project)}},
        ),
    ):
        r = getattr(client, method)(path, **kwargs)
        _assert_fs_removed(r, marker)


def test_09_marker_under_parent_traversal_target_untouched(
    client: TestClient, tmp_path: Path
) -> None:
    parent_marker = tmp_path / MARKER_NAME
    parent_marker.write_text(MARKER_VALUE, encoding="utf-8")
    child = tmp_path / "child"
    child.mkdir()
    traversal = str(child / "..")
    r = client.get("/api/policies/content", params={"project_path": traversal})
    _assert_fs_removed(r, parent_marker)


# —— 10–11: adapter.py / exec ——


def test_10_cannot_access_mutiny_adapter_py(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    adapter = project / ".mutiny" / "adapter.py"
    before = adapter.read_text(encoding="utf-8")
    read_hits: list[str] = []
    real_read_text = Path.read_text

    def tracking_read_text(self: Path, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        if "adapter.py" in str(self):
            read_hits.append(str(self))
        return real_read_text(self, *args, **kwargs)

    # Policy APIs must not open .mutiny/adapter.py as a side effect.
    with patch.object(Path, "read_text", tracking_read_text):
        r = client.get(
            "/api/policies/content",
            params={"project_path": str(project)},
        )
    _assert_fs_removed(r, marker)
    assert read_hits == [], f"opened adapter.py: {read_hits}"
    assert adapter.read_text(encoding="utf-8") == before


def test_11_cannot_import_or_execute_customer_adapter(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    with patch(
        "mutiny_openai_agents.loader.load_adapter_factory",
        side_effect=AssertionError("load_adapter_factory"),
    ) as load_mock:
        r = client.post(
            "/api/campaigns",
            json={
                "population_size": 2,
                "max_generations": 1,
                "target": "openai_agents",
                "project_path": str(project),
            },
        )
        _assert_exec_removed(r, marker)
        load_mock.assert_not_called()
    # Policy FS path also refuses without exec.
    r2 = client.get("/api/policies", params={"project_path": str(project)})
    _assert_fs_removed(r2, marker)


# —— 12: ALLOW env ——


def test_12_allow_project_exec_does_not_restore_fs(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MUTINY_ALLOW_PROJECT_EXEC", "1")
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    policy = project / "policy.yaml"
    before = policy.read_text(encoding="utf-8")
    got = client.get(
        "/api/policies/content", params={"project_path": str(project)}
    )
    _assert_fs_removed(got, marker)
    put = client.put(
        "/api/policies/content",
        params={"project_path": str(project)},
        json={"content": "version: '4'\ntarget: allow\nrules: []\n"},
    )
    _assert_fs_removed(put, marker)
    assert policy.read_text(encoding="utf-8") == before
    listed = client.get("/api/policies", params={"project_path": str(project)})
    _assert_fs_removed(listed, marker)


# —— 13: opaque project metadata ——


def test_13_project_metadata_apis_keep_opaque_path(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    opaque = f"opaque-label://{project.name}"
    created = client.post(
        "/api/projects",
        json={"path": opaque, "name": "Opaque Probe"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["path"] == opaque
    assert created.json()["name"] == "Opaque Probe"
    assert marker.read_text(encoding="utf-8") == MARKER_VALUE

    # Real FS path also stored opaquely without reading the tree.
    created2 = client.post(
        "/api/projects",
        json={"path": str(project), "name": "Hostile Meta"},
    )
    assert created2.status_code == 201, created2.text
    assert created2.json()["path"] == str(project)
    assert marker.read_text(encoding="utf-8") == MARKER_VALUE

    detail = client.get(f"/api/projects/{created2.json()['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["path"] == str(project)
    assert body["policies"]["code"] == "hosted_filesystem_access_removed"
    assert body["policies"]["filesystem_access"] == "removed"
    assert marker.read_text(encoding="utf-8") == MARKER_VALUE


# —— 14: ingest opaque ——


def test_14_ingest_does_not_open_local_project_key(
    client: TestClient, tmp_path: Path
) -> None:
    project = _hostile_project(tmp_path)
    marker = project / MARKER_NAME
    read_hits: list[str] = []
    real_read_text = Path.read_text

    def tracking_read_text(self: Path, *args, **kwargs) -> str:  # type: ignore[no-untyped-def]
        text = str(self)
        if MARKER_NAME in text or str(project) in text or "adapter.py" in text:
            read_hits.append(text)
        return real_read_text(self, *args, **kwargs)

    with (
        patch.object(Path, "read_text", tracking_read_text),
        patch(
            "mutiny_openai_agents.loader.load_adapter_factory",
            side_effect=AssertionError("ingest must not load adapters"),
        ),
        patch("mutiny_api.supervisor.resolve_project_root") as resolve_mock,
    ):
        r = client.post(
            "/api/ingest/v1/campaigns",
            json={
                "schema_version": 1,
                "mutiny_version": MUTINY_CORE_VERSION,
                "execution_mode": "local_cli",
                "redaction": {"applied": True, "marker": "[REDACTED]"},
                "campaign_id": "camp-p03-14",
                "local_project_key": str(project),
                "project_label": str(project),
                "config": {
                    "population_size": 2,
                    "max_generations": 1,
                    "target": "openai_agents",
                },
            },
        )
    assert r.status_code == 201, r.text
    resolve_mock.assert_not_called()
    assert read_hits == [], f"ingest opened customer paths: {read_hits}"
    assert marker.read_text(encoding="utf-8") == MARKER_VALUE


# —— 15: trusted demo ——


def test_15_trusted_in_process_demo_still_works(
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

    deadline = time.time() + 30.0
    while time.time() < deadline:
        body = client.get(f"/api/campaigns/{cid}").json()
        if body["status"] not in {"created", "running"}:
            assert body["status"] in {"violation", "completed", "failed"}
            # Harness policy fixture still available.
            demo = client.get("/api/policies/demo_support")
            assert demo.status_code == 200
            assert demo.json()["id"] == "demo_support"
            return
        time.sleep(0.05)
    raise AssertionError("demo campaign did not finish")
