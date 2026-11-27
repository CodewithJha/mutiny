"""``mutiny run`` must not read as a clean result when nothing was tested."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mutiny_cli import run_cmd
from mutiny_cli.main import main
from mutiny_core import CampaignConfig, load_project_policy

POLICY = """\
version: "1"
target: untested_probe
rules:
  - id: refund_limit
    description: Refunds over $200 require approval
    tool: issue_refund
    kind: require_args
    when:
      amount:
        gt: 200
    require:
      approved:
        eq: true
"""

ADAPTER_SLOW_AFTER = '''\
import time

from demo_agent import DemoSupportAgent, InProcessDemoAdapter


class SlowAfter(InProcessDemoAdapter):
    """Answers in time for the first FAST conversations, then stalls."""

    FAST = {fast}

    def __init__(self):
        super().__init__(agent=DemoSupportAgent(enforce_refund_policy=True))
        self.conversations = 0

    def reset(self, session_id):
        self.conversations += 1
        super().reset(session_id)

    def step(self, session_id, user_message):
        if self.conversations > self.FAST:
            time.sleep(0.3)
        return super().step(session_id, user_message)


def create_adapter():
    return SlowAfter()
'''


def _project(tmp: Path, *, fast: int) -> Path:
    (tmp / ".mutiny").mkdir(parents=True)
    (tmp / ".mutiny" / "adapter.py").write_text(
        ADAPTER_SLOW_AFTER.format(fast=fast), encoding="utf-8"
    )
    (tmp / "policy.yaml").write_text(POLICY, encoding="utf-8")
    (tmp / "mutiny.yaml").write_text(
        yaml.dump({"population_size": 3, "max_generations": 1, "elite_count": 1}),
        encoding="utf-8",
    )
    return tmp


def _run(root: Path) -> run_cmd.LocalRunOutcome:
    run_cmd.ensure_project_on_path(root)
    policy, _ = load_project_policy(root)
    return run_cmd._run_local(
        root,
        {},
        policy,
        core_cfg=CampaignConfig(
            population_size=3,
            max_generations=1,
            elite_count=1,
            step_timeout_seconds=0.05,
        ),
    )


def test_run_fails_when_every_candidate_timed_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outcome = _run(_project(tmp_path, fast=0))

    captured = capsys.readouterr()
    assert outcome.exit_code == 1
    assert captured.out.count("DID NOT FINISH (adapter_step_timeout:") == 3
    assert "3 of 3 candidate(s) did not finish" in captured.err
    assert "no candidate finished" in captured.err
    assert "No violation this run" not in captured.out


def test_run_warns_but_passes_when_only_some_candidates_timed_out(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outcome = _run(_project(tmp_path, fast=2))

    captured = capsys.readouterr()
    assert outcome.exit_code == 0
    assert captured.out.count("DID NOT FINISH") == 1
    assert "1 of 3 candidate(s) did not finish" in captured.err
    assert "no candidate finished" not in captured.err
    assert "No violation this run" in captured.out


def test_run_without_timeouts_prints_no_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outcome = _run(_project(tmp_path, fast=99))

    captured = capsys.readouterr()
    assert outcome.exit_code == 0
    assert "DID NOT FINISH" not in captured.out
    assert "did not finish" not in captured.err


@pytest.mark.parametrize("rules", ["rules: []\n", ""])
def test_run_rejects_a_policy_without_rules(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], rules: str
) -> None:
    root = _project(tmp_path, fast=99)
    (root / "policy.yaml").write_text(
        f'version: "1"\ntarget: untested_probe\n{rules}', encoding="utf-8"
    )

    assert main(["run", "--path", str(root)]) == 2
    captured = capsys.readouterr()
    assert "policy.yaml has no rules" in captured.err
    assert "Local campaign" not in captured.out
