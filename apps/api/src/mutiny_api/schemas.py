"""HTTP request/response models for the Hosted API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    """Register a local customer project directory as a first-class entity."""

    path: str = Field(..., min_length=1)
    name: str | None = None
    adapter: Literal["openai_agents"] = "openai_agents"


class CampaignCreateRequest(BaseModel):
    population_size: int = Field(default=8, ge=1, le=12)
    max_generations: int = Field(default=6, ge=1, le=8)
    elite_count: int = Field(default=2, ge=0)
    max_turns: int = Field(default=4, ge=1, le=6)
    stop_on_first_violation: bool = True
    rng_seed: int = 0
    # Product path: openai_agents + project_path → load customer's .mutiny/adapter.py
    # Harness: in_process_demo (dev / reliability suite; no project_path required)
    # project_path required for openai_agents is enforced in the supervisor.
    target: Literal["in_process_demo", "openai_agents"] = "in_process_demo"
    project_path: str | None = None
    # Optional link to a registered project. When set, path is taken from the
    # project row (project_path may still be supplied and must match if both set).
    project_id: str | None = None
    # Harness-only fixture id. Product campaigns load policy.yaml from project_path.
    policy_set_id: str | None = None
    use_boundary_seeds: bool = True
    wall_clock_seconds: float | None = None


class PolicyContentSaveRequest(BaseModel):
    """Save raw YAML/JSON policy text to the project policy file."""

    content: str = Field(..., min_length=1)


class CampaignStartRequest(BaseModel):
    attestation: bool = False


class MinimizeRequest(BaseModel):
    target_rule_ids: list[str] | None = None


class RegressionSaveRequest(BaseModel):
    name: str = "refund_limit_regression"
    target_rule_ids: list[str] | None = None


class TestsRunRequest(BaseModel):
    """Run one or many regression replays.

    Back-compat: ``regression_id`` + ``fixed_agent`` still works.
    Batch: ``regression_ids``, ``run_all``, or ``failed_only``.
    """

    regression_id: str | None = None
    regression_ids: list[str] | None = None
    run_all: bool = False
    failed_only: bool = False
    fixed_agent: bool = False
    # When true (default for Hosted dashboard), store a test_runs row.
    persist: bool = True


class HealthResponse(BaseModel):
    status: str
    api: bool
    db: bool
    model: str
    version: str
    # Production-feel ops fields (M8+)
    mutator_mode: str = "template"
    llm_configured: bool = False
    db_latency_ms: float | None = None
    schema_version: str | None = None
    max_concurrent_campaigns: int = 1
    running_campaigns: int = 0
    demo_pin: str | None = "iris-demo-pin"
    # Supported campaign targets (openai_agents requires project_path)
    target_allowlist: list[str] = Field(
        default_factory=lambda: ["in_process_demo", "openai_agents"]
    )
    adapter_loading: str = "project_path"


class MetaResponse(BaseModel):
    name: str = "Mutiny Hosted API"
    version: str
    product: str = "hosted_behavioral_fuzzer"
    oracle: str = "deterministic_policy_evaluator"
    surfaces: list[str] = Field(
        default_factory=lambda: [
            "projects",
            "policies",
            "campaigns",
            "sse",
            "minimize",
            "regressions",
            "tests",
        ]
    )
    safety: dict[str, Any] = Field(
        default_factory=lambda: {
            "attestation_required": True,
            "targets": ["in_process_demo", "openai_agents"],
            "project_path_required_for": ["openai_agents"],
            "mock_tools": True,
            "open_proxy": False,
        }
    )
    pin: str = "config/demo_pin.json"
