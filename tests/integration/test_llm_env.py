"""Bad mutation settings must not break liveness or an offline sample run."""

import shutil
from pathlib import Path

import pytest
from agents import RunConfig, Runner
from fastapi.testclient import TestClient

from mutiny_api.app import create_app
from mutiny_cli.main import main
from mutiny_core.llm import FeatherlessClient


@pytest.fixture(autouse=True)
def isolated_mutation_env(monkeypatch):
    for name in (
        "MUTINY_FEATHERLESS_API_KEY",
        "FEATHERLESS_API_KEY",
        "OPENAI_API_KEY",
        "MUTINY_FEATHERLESS_BASE_URL",
        "MUTINY_MUTATION_MODEL",
        "MUTINY_LLM_TIMEOUT",
        "MUTINY_LLM_TEMPERATURE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MUTINY_SAMPLE_OFFLINE", "1")

    def unexpected_client(self):
        pytest.fail("these tests must never create a remote LLM client")

    monkeypatch.setattr(FeatherlessClient, "_get_client", unexpected_client)


@pytest.mark.parametrize(
    "settings,configured",
    [
        ({"OPENAI_API_KEY": "target-key"}, False),
        ({"MUTINY_FEATHERLESS_API_KEY": "mutation-key"}, True),
        (
            {
                "MUTINY_FEATHERLESS_API_KEY": "mutation-key",
                "MUTINY_LLM_TIMEOUT": "not-a-float",
            },
            False,
        ),
        (
            {
                "MUTINY_FEATHERLESS_API_KEY": "mutation-key",
                "MUTINY_LLM_TEMPERATURE": "not-a-float",
            },
            False,
        ),
        ({"MUTINY_LLM_TIMEOUT": "not-a-float"}, False),
    ],
)
def test_health_stays_available(tmp_path, monkeypatch, settings, configured):
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    with TestClient(create_app(tmp_path / "health.sqlite")) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is configured
    assert body["mutator_mode"] == ("featherless" if configured else "template")
    assert "target-key" not in response.text and "mutation-key" not in response.text


@pytest.mark.parametrize(
    "settings",
    [
        {"OPENAI_API_KEY": "target-key"},
        {
            "MUTINY_FEATHERLESS_API_KEY": "mutation-key",
            "MUTINY_LLM_TIMEOUT": "not-a-float",
        },
        {
            "MUTINY_FEATHERLESS_API_KEY": "mutation-key",
            "MUTINY_LLM_TEMPERATURE": "not-a-float",
        },
    ],
)
def test_sample_cli_falls_back_to_templates(tmp_path, monkeypatch, capsys, settings):
    source = Path(__file__).resolve().parents[2] / "examples/openai_support_agent"
    project = tmp_path / "sample"
    shutil.copytree(
        source, project, ignore=shutil.ignore_patterns("__pycache__", "tests", "runs")
    )
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    # Exercise the real SDK runner and scripted model without trace uploads.
    run_sync = Runner.run_sync

    def run_without_tracing(*args, **kwargs):
        kwargs["run_config"] = RunConfig(tracing_disabled=True)
        return run_sync(*args, **kwargs)

    monkeypatch.setattr(Runner, "run_sync", run_without_tracing)
    assert main(["run", "--path", str(project), "--no-hosted"]) == 0
    captured = capsys.readouterr()
    assert "mutator: template" in captured.out
    assert "Traceback" not in captured.out + captured.err
    assert "target-key" not in captured.out + captured.err
    assert "mutation-key" not in captured.out + captured.err
