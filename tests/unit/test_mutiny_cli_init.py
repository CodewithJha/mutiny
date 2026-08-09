"""CLI scaffold tests for mutiny init."""

from __future__ import annotations

from pathlib import Path

from mutiny_cli.init_cmd import run_init
from mutiny_cli.main import main
from mutiny_core import PolicySet
import yaml


def test_mutiny_init_creates_artifacts(tmp_path: Path) -> None:
    assert run_init(project_root=tmp_path) == 0
    adapter = tmp_path / ".mutiny" / "adapter.py"
    policy = tmp_path / "policy.yaml"
    config = tmp_path / "mutiny.yaml"
    assert adapter.exists()
    assert policy.exists()
    assert config.exists()
    text = adapter.read_text()
    assert "OpenAIAgentsAdapter" in text
    assert "TODO" in text or "AGENT_REF" in text
    data = yaml.safe_load(policy.read_text())
    ps = PolicySet.model_validate(data)
    assert ps.version == "1"
    assert any(r.id == "refund_limit" for r in ps.rules)
    text = policy.read_text()
    assert "ONE source of truth" in text or "source of truth" in text
    assert "bump" in text.lower() or "version" in text
    cfg = yaml.safe_load(config.read_text())
    assert "api_url" in cfg["hosted"]
    assert "target" not in cfg["hosted"]  # Hosted uses cwd as project_path
    assert cfg["hosted"].get("policy_set_id") is None  # project policy.yaml, not demo_support
    assert "OpenAI Agents SDK" in adapter.read_text() or "OpenAIAgentsAdapter" in adapter.read_text()


def test_mutiny_init_cli_entrypoint(tmp_path: Path) -> None:
    assert main(["init", "--path", str(tmp_path)]) == 0
    assert (tmp_path / ".mutiny" / "adapter.py").exists()


def test_mutiny_init_skips_without_force(tmp_path: Path) -> None:
    assert run_init(project_root=tmp_path) == 0
    (tmp_path / "policy.yaml").write_text("version: '1'\ntarget: x\nrules: []\n")
    assert run_init(project_root=tmp_path, force=False) == 0
    # without force, existing policy.yaml is left alone
    assert "target: x" in (tmp_path / "policy.yaml").read_text()
