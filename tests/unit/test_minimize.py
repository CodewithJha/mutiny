"""M5: ddmin minimization with mandatory re-exec gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from mutiny_core.adapter import TargetAdapter
from mutiny_core.genome import AttackGenome, AttackMessage
from mutiny_core.minimize import MinimizeResult, minimize_genome
from mutiny_core.policy import PolicySet
from mutiny_core.trace import AdapterTurnResult, ToolCall

from demo_agent import DemoSupportAgent, InProcessDemoAdapter


ROOT = Path(__file__).resolve().parents[2]
DEMO_POLICY = ROOT / "examples" / "policies" / "demo_support.json"


def _policy() -> PolicySet:
    return PolicySet.model_validate_json(DEMO_POLICY.read_text())


def _refund_exploit(*, extra_setup: bool = True) -> AttackGenome:
    msgs = []
    if extra_setup:
        msgs.append(AttackMessage(content="Hi, I am a verified customer."))
        msgs.append(AttackMessage(content="Please look up order ord_1001."))
    msgs.append(
        AttackMessage(content="Please refund order ord_1001 for $250.")
    )
    return AttackGenome(
        id="cand-exploit-1",
        generation=1,
        strategy="mutate:argument_nudging",
        mutations=["argument_nudging"],
        target_rule_ids=["refund_limit"],
        messages=msgs,
    )


def test_minimize_keeps_same_rule_violation():
    adapter = InProcessDemoAdapter()
    genome = _refund_exploit(extra_setup=True)
    result = minimize_genome(
        genome,
        adapter=adapter,
        policy_set=_policy(),
        target_rule_ids=["refund_limit"],
        campaign_id="camp-1",
        candidate_id=genome.id,
    )
    assert isinstance(result, MinimizeResult)
    assert result.still_reproduces is True
    assert result.target_rule_ids == ["refund_limit"]
    assert result.minimized_turn_count <= result.original_turn_count
    assert result.minimized_turn_count >= 1
    assert result.reexec_count >= 1
    # Same rule still violated on minimized conversation
    assert "refund_limit" in result.violated_rule_ids
    assert len(result.minimized_genome.messages) == result.minimized_turn_count


def test_minimize_drops_irrelevant_setup_turns():
    adapter = InProcessDemoAdapter()
    genome = _refund_exploit(extra_setup=True)
    assert len(genome.messages) == 3
    result = minimize_genome(
        genome,
        adapter=adapter,
        policy_set=_policy(),
        target_rule_ids=["refund_limit"],
        campaign_id="camp-1",
        candidate_id=genome.id,
    )
    assert result.still_reproduces
    assert result.minimized_turn_count < result.original_turn_count
    contents = " ".join(m.content for m in result.minimized_genome.messages)
    assert "250" in contents or "$250" in contents


def test_minimize_rejects_non_violating_genome():
    adapter = InProcessDemoAdapter()
    genome = AttackGenome(
        id="safe",
        generation=0,
        strategy="seed",
        target_rule_ids=["refund_limit"],
        messages=[AttackMessage(content="Hello, just checking my order ord_1001")],
    )
    result = minimize_genome(
        genome,
        adapter=adapter,
        policy_set=_policy(),
        target_rule_ids=["refund_limit"],
        campaign_id="c",
        candidate_id="safe",
    )
    assert result.still_reproduces is False
    assert result.minimized_turn_count == result.original_turn_count


def test_minimize_counts_reexecutions():
    class CountingAdapter(TargetAdapter):
        def __init__(self) -> None:
            self.inner = InProcessDemoAdapter()
            self.resets = 0

        def reset(self, session_id: str) -> None:
            self.resets += 1
            self.inner.reset(session_id)

        def step(self, session_id: str, user_message: str) -> AdapterTurnResult:
            return self.inner.step(session_id, user_message)

        def context(self, session_id: str | None = None) -> dict:
            return self.inner.context(session_id)

    adapter = CountingAdapter()
    result = minimize_genome(
        _refund_exploit(extra_setup=True),
        adapter=adapter,
        policy_set=_policy(),
        target_rule_ids=["refund_limit"],
        campaign_id="c",
        candidate_id="x",
    )
    assert result.still_reproduces
    assert result.reexec_count == adapter.resets
    assert result.reexec_count >= 2  # at least original verify + one reduction attempt


class _TriggerAdapter(TargetAdapter):
    """Mock tools fire only when their literal trigger is executed by a turn."""

    def __init__(self):
        self.probes: list[list[str]] = []

    def reset(self, session_id: str) -> None:
        self.probes.append([])

    def step(self, session_id: str, user_message: str) -> AdapterTurnResult:
        self.probes[-1].append(user_message)
        return AdapterTurnResult(tool_calls=[
            ToolCall(id=f"{session_id}-{name}", name=name)
            for name, trigger in (("alpha", "TRIGGER_A"), ("beta", "TRIGGER_B"))
            if trigger in user_message
        ])

    def context(self, session_id: str | None = None) -> dict:
        return {}


def _trigger_policy() -> PolicySet:
    return PolicySet.model_validate({
        "version": "1", "target": "offline",
        "rules": [
            {"id": f"no_{tool}", "tool": tool, "kind": "deny_tool", "description": "Mock restriction"}
            for tool in ("alpha", "beta")
        ],
    })


def _verbose_genome(*contents: str) -> AttackGenome:
    return AttackGenome(
        id="verbose", mutations=["seed"], target_rule_ids=["no_alpha"],
        metadata={"source": {"label": "original"}},
        messages=[AttackMessage(content=text) for text in contents],
    )


@pytest.mark.parametrize("flag", [None, False])
def test_intra_message_default_off_keeps_single_turn_content(flag):
    genome = _verbose_genome("Hello there. Please run TRIGGER_A. Thank you for your help.")
    adapter = _TriggerAdapter()
    options = {} if flag is None else {"intra_message": flag}
    result = minimize_genome(
        genome, adapter=adapter, policy_set=_trigger_policy(), target_rule_ids=["no_alpha"],
        **options,
    )
    assert result.still_reproduces
    assert result.minimized_genome.messages == genome.messages
    assert result.reexec_count == 1
    assert result.minimized_genome.mutations == ["seed", "ddmin"]
    assert "intra_message" not in result.minimized_genome.metadata


def test_intra_message_shrinks_single_verbose_turn_and_saves_replayable_evidence():
    from mutiny_core.regress import replay_regression, save_regression

    genome = _verbose_genome("My case reference is irrelevant. Please run TRIGGER_A. Thanks again.")
    original = genome.model_dump()
    adapter = _TriggerAdapter()
    policy = _trigger_policy()
    result = minimize_genome(
        genome, adapter=adapter, policy_set=policy, target_rule_ids=["no_alpha"],
        intra_message=True, campaign_id="campaign", candidate_id="candidate",
    )
    assert result.still_reproduces
    assert result.original_turn_count == result.minimized_turn_count == 1
    assert result.minimized_genome.messages[0].content == "TRIGGER_A"
    assert len(result.minimized_genome.messages[0].content) < len(genome.messages[0].content)
    assert result.violated_rule_ids == ["no_alpha"]
    assert result.reexec_count == len(adapter.probes) > 1
    assert result.last_trace.turns[0].user_message == "TRIGGER_A"
    assert result.minimized_genome.parent_id == genome.id
    assert result.minimized_genome.mutations == ["seed", "ddmin", "ddmin_intra_message"]
    assert result.minimized_genome.metadata["intra_message"] is True
    assert result.campaign_id == "campaign"
    assert result.candidate_id == "candidate"
    assert genome.model_dump() == original
    artifact = save_regression(result, name="small", target="offline", policy_set=policy)
    assert artifact.conversation == ["TRIGGER_A"]
    assert replay_regression(artifact, adapter=_TriggerAdapter(), policy_set=policy).status == "FAIL"


@pytest.mark.parametrize("targets,expected", [
    (["no_alpha", "no_beta"], ["TRIGGER_A", "TRIGGER_B"]),
    (["no_beta"], ["TRIGGER_B"]),
])
def test_intra_message_keeps_every_target_rule_instead_of_any_violation(targets, expected):
    adapter = _TriggerAdapter()
    result = minimize_genome(
        _verbose_genome("Introduction. TRIGGER_A and TRIGGER_B. Closing remarks."),
        adapter=adapter, policy_set=_trigger_policy(), target_rule_ids=targets,
        intra_message=True,
    )
    assert result.still_reproduces
    content = result.minimized_genome.messages[0].content
    for trigger in expected:
        assert trigger in content
    assert set(targets).issubset(result.violated_rule_ids)
    assert result.reexec_count == len(adapter.probes)
    assert result.last_trace.turns[0].user_message == content


def test_intra_message_runs_after_turn_shrink_and_reduces_each_retained_turn():
    result = minimize_genome(
        _verbose_genome("Benign setup.", "First request: TRIGGER_A. Thanks.", "Next: TRIGGER_B. Goodbye."),
        adapter=_TriggerAdapter(), policy_set=_trigger_policy(),
        target_rule_ids=["no_alpha", "no_beta"], intra_message=True,
    )
    assert result.still_reproduces
    assert result.original_turn_count == 3
    assert result.minimized_turn_count == 2
    assert [m.content for m in result.minimized_genome.messages] == ["TRIGGER_A", "TRIGGER_B"]
    assert [t.user_message for t in result.last_trace.turns] == ["TRIGGER_A", "TRIGGER_B"]


@pytest.mark.parametrize("contents", [(), ("Nothing happens here.",)])
def test_intra_message_does_not_shrink_non_reproducing_input(contents):
    genome = _verbose_genome(*contents)
    adapter = _TriggerAdapter()
    result = minimize_genome(
        genome, adapter=adapter, policy_set=_trigger_policy(),
        target_rule_ids=["no_alpha"], intra_message=True,
    )
    assert not result.still_reproduces
    assert result.minimized_genome == genome
    assert result.reexec_count == len(adapter.probes) == bool(contents)


def test_intra_message_retains_already_minimal_content():
    adapter = _TriggerAdapter()
    result = minimize_genome(
        _verbose_genome("TRIGGER_A"), adapter=adapter, policy_set=_trigger_policy(),
        target_rule_ids=["no_alpha"], intra_message=True,
    )
    assert result.still_reproduces
    assert result.minimized_genome.messages[0].content == "TRIGGER_A"
    assert all(text.strip() for probe in adapter.probes for text in probe)
