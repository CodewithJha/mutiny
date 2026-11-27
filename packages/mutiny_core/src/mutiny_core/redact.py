"""Deterministic secret redaction for durable / user-visible Mutiny surfaces.

Redacts common credential field values, inline Authorization Bearer tokens and
OpenAI-style ``sk-`` API keys. This is not a general secret scanner — unusual
formats may slip through.
"""

from __future__ import annotations

import os
import re
from typing import Any

REDACTED = "[REDACTED]"

# Normalized (snake_case, lower) credential field names. A key is sensitive when
# it equals one of these or ends with ``_<name>`` (``openai_api_key``,
# ``client_secret``, ``github_token``, ``db_password``).
_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "token",
        "password",
        "passwd",
        "secret",
        "secret_key",
        "private_key",
        "access_token",
        "refresh_token",
        "authorization",
    }
)
_SENSITIVE_SUFFIXES = tuple(
    f"_{name}" for name in sorted(_SENSITIVE_KEYS - {"authorization"})
)

# Authorization: Bearer <token> (case-insensitive header name / scheme).
_AUTH_BEARER_RE = re.compile(
    r"(Authorization\s*:\s*Bearer\s+)\S+",
    re.IGNORECASE,
)

# OpenAI-style keys in free text: ``sk-…`` / ``sk-proj-…``. Requiring 20+ key
# characters with at least one digit keeps prose such as "sk-learn" intact.
_SK_API_KEY_RE = re.compile(r"\bsk-(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{20,}")


def redaction_enabled() -> bool:
    """Rollback switch: set MUTINY_DISABLE_SECRET_REDACTION=1 to skip redaction."""
    flag = os.environ.get("MUTINY_DISABLE_SECRET_REDACTION", "").strip().lower()
    return flag not in {"1", "true", "yes", "on"}


def _normalize_key(key: str) -> str:
    """Case-insensitive key normalize: apiKey / API-KEY / x.api.key → api_key."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    return re.sub(r"[^a-z0-9]+", "_", spaced.lower()).strip("_")


def _is_sensitive_key(key: str) -> bool:
    normalized = _normalize_key(key)
    return normalized in _SENSITIVE_KEYS or normalized.endswith(_SENSITIVE_SUFFIXES)


def _redact_string(value: str) -> str:
    value = _AUTH_BEARER_RE.sub(rf"\1{REDACTED}", value)
    return _SK_API_KEY_RE.sub(REDACTED, value)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[Any, Any] = {}
        for key, child in value.items():
            if isinstance(key, str) and _is_sensitive_key(key):
                out[key] = REDACTED
            else:
                out[key] = _redact(child)
        return out
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    if isinstance(value, str):
        return _redact_string(value)
    return value


def redact_secrets(value: Any) -> Any:
    """Return a sanitized deep copy. Never mutates ``value``.

    Replaces values of known credential keys with ``[REDACTED]`` and rewrites
    inline ``Authorization: Bearer …`` and ``sk-…`` API key substrings. Ordinary
    prose containing
    words like ``token`` / ``password`` / ``secret`` is left intact.
    """
    if not redaction_enabled():
        return _deepcopy_plain(value)
    return _redact(value)


def _deepcopy_plain(value: Any) -> Any:
    """Structural copy without redaction (disable-flag path)."""
    if isinstance(value, dict):
        return {k: _deepcopy_plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deepcopy_plain(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_deepcopy_plain(v) for v in value)
    return value
