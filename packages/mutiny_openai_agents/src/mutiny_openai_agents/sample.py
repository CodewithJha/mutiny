"""Hosted / CLI helpers for the sample OpenAI Agents SDK project."""

from __future__ import annotations

from pathlib import Path

from mutiny_openai_agents.adapter import OpenAIAgentsAdapter
from mutiny_openai_agents.loader import load_adapter_factory


def sample_project_root(repo_root: Path | None = None) -> Path:
    """Locate ``examples/openai_support_agent`` from the Mutiny repo root."""
    if repo_root is None:
        # packages/mutiny_openai_agents/src/mutiny_openai_agents/sample.py
        repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "examples" / "openai_support_agent"


def make_openai_support_adapter(
    *,
    repo_root: Path | None = None,
    project_root: Path | None = None,
    enforce_refund_policy: bool = False,
) -> OpenAIAgentsAdapter:
    """Build adapter from the sample project's ``.mutiny/adapter.py``.

    Same loader Hosted uses for any customer OpenAI Agents SDK project.
    Always returns ``OpenAIAgentsAdapter`` — never the legacy in-process demo.
    """
    root = project_root or sample_project_root(repo_root)
    if not root.exists():
        raise FileNotFoundError(f"sample project not found: {root}")
    factory = load_adapter_factory(root)
    return factory(enforce_refund_policy=enforce_refund_policy)
