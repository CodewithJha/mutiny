"""M8 reliability gate — ≥2/3 pinned campaigns find refund_limit with tool proof."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_smoke_gate_script_passes():
    script = ROOT / "scripts" / "smoke_reliability.py"
    env_pythonpath = (
        f"{ROOT / 'apps' / 'api' / 'src'}:"
        f"{ROOT / 'apps' / 'demo_agent' / 'src'}:"
        f"{ROOT / 'packages' / 'mutiny_core' / 'src'}"
    )
    import os

    env = {**os.environ, "PYTHONPATH": env_pythonpath}
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "SMOKE GATE PASSED" in proc.stdout


def test_demo_pin_shape():
    pin = json.loads((ROOT / "config" / "demo_pin.json").read_text())
    assert pin["smoke_trials"] == 3
    assert pin["smoke_required_hits"] == 2
    assert len(pin["smoke_seeds"]) == 3
    assert pin["use_boundary_seeds"] is True
    assert pin["target"] == "in_process_demo"
