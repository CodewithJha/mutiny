"""P0-1 / P0-4: non-loopback Hosted binds require MUTINY_API_TOKEN."""

from __future__ import annotations

from typing import Any

import pytest

from mutiny_api.auth import API_TOKEN_ENV
from mutiny_api.bind_security import (
    BindSecurityError,
    is_loopback_bind_host,
    require_token_for_non_loopback_bind,
)
from mutiny_api.serve import main, run_server

VALID_TOKEN = "test-mutiny-bind-token-p0-not-real"


@pytest.fixture
def no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(API_TOKEN_ENV, raising=False)


@pytest.fixture
def valid_token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv(API_TOKEN_ENV, VALID_TOKEN)
    return VALID_TOKEN


# —— Cases 1–4: loopback may start without token ——


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "localhost", "::1", "  127.0.0.1  ", "[::1]"],
)
def test_loopback_hosts_recognized(host: str) -> None:
    assert is_loopback_bind_host(host) is True


def test_01_default_loopback_no_token_ok(no_token: None) -> None:
    require_token_for_non_loopback_bind("127.0.0.1")


def test_02_127_0_0_1_no_token_ok(no_token: None) -> None:
    require_token_for_non_loopback_bind("127.0.0.1")


def test_03_localhost_no_token_ok(no_token: None) -> None:
    require_token_for_non_loopback_bind("localhost")


def test_04_ipv6_loopback_no_token_ok(no_token: None) -> None:
    require_token_for_non_loopback_bind("::1")
    require_token_for_non_loopback_bind("[::1]")


# —— Cases 5–10: non-loopback without usable token fails ——


@pytest.mark.parametrize(
    "host",
    [
        "0.0.0.0",
        "::",
        "[::]",
        "192.168.1.10",
        "10.0.0.5",
        "8.8.8.8",
        "2001:db8::1",
        "example.com",
    ],
)
def test_non_loopback_hosts_recognized(host: str) -> None:
    assert is_loopback_bind_host(host) is False


def test_05_all_interfaces_no_token_fails(no_token: None) -> None:
    with pytest.raises(BindSecurityError, match=API_TOKEN_ENV):
        require_token_for_non_loopback_bind("0.0.0.0")


def test_06_ipv6_unspecified_no_token_fails(no_token: None) -> None:
    with pytest.raises(BindSecurityError, match=API_TOKEN_ENV):
        require_token_for_non_loopback_bind("::")


def test_07_lan_ip_no_token_fails(no_token: None) -> None:
    with pytest.raises(BindSecurityError, match="192.168.1.10"):
        require_token_for_non_loopback_bind("192.168.1.10")


def test_08_public_ip_no_token_fails(no_token: None) -> None:
    with pytest.raises(BindSecurityError, match="8.8.8.8"):
        require_token_for_non_loopback_bind("8.8.8.8")


def test_09_empty_token_fails_non_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_TOKEN_ENV, "")
    with pytest.raises(BindSecurityError, match=API_TOKEN_ENV):
        require_token_for_non_loopback_bind("0.0.0.0")


def test_10_whitespace_token_fails_non_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(API_TOKEN_ENV, "   \t  ")
    with pytest.raises(BindSecurityError, match=API_TOKEN_ENV):
        require_token_for_non_loopback_bind("0.0.0.0")


# —— Case 11: non-loopback + valid token ok ——


def test_11_non_loopback_valid_token_ok(valid_token: str) -> None:
    require_token_for_non_loopback_bind("0.0.0.0")
    require_token_for_non_loopback_bind("::")
    require_token_for_non_loopback_bind("192.168.0.2")


# —— Fail before listen ——


def test_misconfigured_non_loopback_never_calls_uvicorn(
    no_token: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(*args: Any, **kwargs: Any) -> None:
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr("uvicorn.run", fake_run)
    with pytest.raises(BindSecurityError, match=API_TOKEN_ENV):
        run_server(host="0.0.0.0", port=8000)
    assert calls == []


def test_cli_main_exits_2_before_listen(
    no_token: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[Any] = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: calls.append(True))
    code = main(["--host", "0.0.0.0", "--port", "9"])
    assert code == 2
    assert calls == []
    err = capsys.readouterr().err
    assert API_TOKEN_ENV in err
    assert "0.0.0.0" in err


def test_loopback_serve_reaches_uvicorn(
    no_token: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(*args: Any, **kwargs: Any) -> None:
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr("uvicorn.run", fake_run)
    run_server(host="127.0.0.1", port=8000)
    assert len(calls) == 1
    assert calls[0]["kwargs"]["host"] == "127.0.0.1"
    assert calls[0]["kwargs"]["port"] == 8000


def test_non_loopback_serve_reaches_uvicorn_with_token(
    valid_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(*args: Any, **kwargs: Any) -> None:
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr("uvicorn.run", fake_run)
    run_server(host="0.0.0.0", port=9000)
    assert len(calls) == 1
    assert calls[0]["kwargs"]["host"] == "0.0.0.0"
    assert calls[0]["kwargs"]["port"] == 9000
