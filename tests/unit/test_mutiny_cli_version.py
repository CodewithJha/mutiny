"""Unit tests for ``mutiny --version`` / ``mutiny -V`` (Issue #26)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import pytest

from mutiny_cli.main import get_version, main


def test_version_flag_prints_version_and_exits(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "mutiny" in out
    assert get_version() in out


def test_short_version_flag_prints_version_and_exits(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["-V"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "mutiny" in out
    assert get_version() in out


def test_get_version_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_name: str) -> str:
        raise PackageNotFoundError("mutiny-ai")

    import importlib.metadata

    monkeypatch.setattr(importlib.metadata, "version", _raise)
    ver = get_version()
    assert "source" in ver or "0.2.0" in ver


def test_help_includes_version_option(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "--version" in out
    assert "-V" in out
