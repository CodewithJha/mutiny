"""Single-tenant Hosted API token authentication (M-PR7).

When ``MUTINY_API_TOKEN`` is set to a non-empty value, protected ``/api/*``
routes require ``Authorization: Bearer <token>``. When unset, auth is disabled
(local demo / tests only — not safe for shared or public networks).

This is identity for the Hosted control plane, not execution isolation (ADR-019 /
M-PR8E). A valid token does not enable customer ``project_path`` adapter exec.
"""

from __future__ import annotations

import hmac
import os
from typing import Annotated

from fastapi import Header, Request

from mutiny_api.errors import raise_api

API_TOKEN_ENV = "MUTINY_API_TOKEN"

# Liveness / discovery only — no customer data, no control-plane actions.
PUBLIC_API_PATHS = frozenset({"/api/health", "/api/meta"})


def configured_api_token() -> str | None:
    """Return the configured token, or None when auth is disabled."""
    raw = os.environ.get(API_TOKEN_ENV)
    if raw is None:
        return None
    token = raw.strip()
    return token or None


def auth_required() -> bool:
    """True when Hosted must enforce Bearer authentication."""
    return configured_api_token() is not None


def is_public_api_path(path: str) -> bool:
    """Return True for intentionally unauthenticated API paths."""
    return path in PUBLIC_API_PATHS


def extract_bearer_token(authorization: str | None) -> str | None:
    """Parse ``Authorization: Bearer <token>``. Never log the value."""
    if authorization is None:
        return None
    scheme, _, remainder = authorization.partition(" ")
    if scheme.lower() != "bearer" or not remainder:
        return None
    token = remainder.strip()
    return token or None


def tokens_match(*, provided: str, expected: str) -> bool:
    """Constant-time equality for UTF-8 token bytes."""
    return hmac.compare_digest(
        provided.encode("utf-8"),
        expected.encode("utf-8"),
    )


def enforce_hosted_auth(authorization: str | None) -> None:
    """Fail closed when auth is configured and the Bearer token is missing/wrong.

    Missing and invalid credentials both map to the same 401 body so callers
    cannot distinguish "almost correct" tokens.
    """
    expected = configured_api_token()
    if expected is None:
        return
    provided = extract_bearer_token(authorization)
    if provided is None or not tokens_match(provided=provided, expected=expected):
        raise_api(401, "unauthorized", "authentication required")


async def require_hosted_auth(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """FastAPI dependency: enforce Hosted bearer auth when configured."""
    path = request.url.path
    if not path.startswith("/api/") or is_public_api_path(path):
        return
    enforce_hosted_auth(authorization)
