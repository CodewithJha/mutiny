"""Hosted bind-host auth posture (P0-1 / P0-4).

Loopback binds may run without ``MUTINY_API_TOKEN`` for local demo use.
Non-loopback binds require a non-empty token and fail closed before listen.
"""

from __future__ import annotations

import ipaddress

from mutiny_api.auth import API_TOKEN_ENV, configured_api_token

# Literal names treated as loopback without DNS (no getaddrinfo).
_LOOPBACK_NAMES = frozenset({"localhost"})


class BindSecurityError(ValueError):
    """Non-loopback Hosted bind without a usable API token."""


def normalize_bind_host(host: str) -> str:
    """Normalize a bind host string for loopback checks (no DNS)."""
    raw = host.strip()
    if raw.startswith("[") and raw.endswith("]") and len(raw) > 2:
        raw = raw[1:-1]
    # Drop IPv6 zone id (e.g. fe80::1%lo0) without resolving.
    if "%" in raw:
        raw = raw.split("%", 1)[0]
    return raw.strip()


def is_loopback_bind_host(host: str) -> bool:
    """Return True when ``host`` is an explicit loopback bind target.

    Recognizes ``localhost``, ``127.0.0.1`` / ``127.0.0.0/8``, and ``::1``.
    Does **not** treat ``0.0.0.0``, ``::``, LAN, or public addresses as
    loopback. Non-IP hostnames other than ``localhost`` are non-loopback.
    Never performs DNS or network I/O.
    """
    normalized = normalize_bind_host(host)
    if not normalized:
        return False
    lowered = normalized.lower()
    if lowered in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(lowered).is_loopback
    except ValueError:
        return False


def require_token_for_non_loopback_bind(host: str) -> None:
    """Fail closed when binding non-loopback without ``MUTINY_API_TOKEN``.

    Empty / whitespace-only tokens are treated as missing (see
    ``configured_api_token``). Call this **before** uvicorn listens.
    """
    if is_loopback_bind_host(host):
        return
    if configured_api_token() is not None:
        return
    display = normalize_bind_host(host) or host.strip() or "<empty>"
    raise BindSecurityError(
        f"non-loopback Hosted bind host {display!r} requires a non-empty "
        f"{API_TOKEN_ENV}; unset/empty/whitespace tokens are not allowed "
        "for public or shared-network binds"
    )
