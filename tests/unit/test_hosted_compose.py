"""Default Hosted ports must stay local to the operator machine."""

from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize("service,port", [("api", 8000), ("web", 3000)])
def test_compose_publishes_only_loopback(service: str, port: int) -> None:
    root = Path(__file__).resolve().parents[2]
    compose = yaml.safe_load((root / "docker-compose.yml").read_text(encoding="utf-8"))
    assert compose["services"][service]["ports"] == [f"127.0.0.1:{port}:{port}"]
