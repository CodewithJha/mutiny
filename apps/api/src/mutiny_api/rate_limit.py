"""In-process Hosted API rate limiting (P1-2).

Single-process token-bucket limits for the Hosted control plane.
Not distributed — each API process has its own buckets.

Identity: authenticated Bearer traffic uses a fixed single-tenant key
(never the raw token). Unauthenticated traffic uses ``request.client.host``
only — ``X-Forwarded-For`` is ignored.
"""

from __future__ import annotations

import math
import os
import re
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from starlette.requests import Request

from mutiny_api.auth import (
    API_TOKEN_ENV,
    configured_api_token,
    extract_bearer_token,
    tokens_match,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ENABLED_ENV = "MUTINY_RATE_LIMIT_ENABLED"
HEALTH_RPM_ENV = "MUTINY_RATE_LIMIT_HEALTH_RPM"
HEALTH_BURST_ENV = "MUTINY_RATE_LIMIT_HEALTH_BURST"
NORMAL_RPM_ENV = "MUTINY_RATE_LIMIT_NORMAL_RPM"
NORMAL_BURST_ENV = "MUTINY_RATE_LIMIT_NORMAL_BURST"
EXPENSIVE_RPM_ENV = "MUTINY_RATE_LIMIT_EXPENSIVE_RPM"
EXPENSIVE_BURST_ENV = "MUTINY_RATE_LIMIT_EXPENSIVE_BURST"
INGEST_RPM_ENV = "MUTINY_RATE_LIMIT_INGEST_RPM"
INGEST_BURST_ENV = "MUTINY_RATE_LIMIT_INGEST_BURST"
MAX_KEYS_ENV = "MUTINY_RATE_LIMIT_MAX_KEYS"
IDLE_SECONDS_ENV = "MUTINY_RATE_LIMIT_IDLE_SECONDS"

# Production-oriented defaults (per process, not cluster-wide).
# Normal defaults are high enough for SSE/poll-friendly single-operator use;
# tighten via env for public exposure. Burst is the immediate ceiling.
DEFAULT_HEALTH_RPM = 1200
DEFAULT_HEALTH_BURST = 120
DEFAULT_NORMAL_RPM = 600
DEFAULT_NORMAL_BURST = 120
DEFAULT_EXPENSIVE_RPM = 60
DEFAULT_EXPENSIVE_BURST = 15
DEFAULT_INGEST_RPM = 300
DEFAULT_INGEST_BURST = 60
DEFAULT_MAX_KEYS = 4096
DEFAULT_IDLE_SECONDS = 300

_FALSEY = frozenset({"0", "false", "no", "off", "disabled"})
_TRUTHY = frozenset({"1", "true", "yes", "on", "enabled"})


class RateLimitConfigError(ValueError):
    """Invalid rate-limit configuration (fail closed)."""


class RateLimitCategory(str, Enum):
    HEALTH = "health"
    NORMAL = "normal"
    EXPENSIVE = "expensive"
    INGEST = "ingest"


@dataclass(frozen=True)
class CategoryLimit:
    rpm: int
    burst: int

    @property
    def refill_per_sec(self) -> float:
        return self.rpm / 60.0


@dataclass(frozen=True)
class RateLimitConfig:
    enabled: bool
    health: CategoryLimit
    normal: CategoryLimit
    expensive: CategoryLimit
    ingest: CategoryLimit
    max_keys: int
    idle_seconds: float

    def limit_for(self, category: RateLimitCategory) -> CategoryLimit:
        return {
            RateLimitCategory.HEALTH: self.health,
            RateLimitCategory.NORMAL: self.normal,
            RateLimitCategory.EXPENSIVE: self.expensive,
            RateLimitCategory.INGEST: self.ingest,
        }[category]


def _parse_enabled(raw: str | None) -> bool | None:
    """Return explicit bool, or None when the env var is unset (use default)."""
    if raw is None or not str(raw).strip():
        return None
    value = str(raw).strip().lower()
    if value in _TRUTHY:
        return True
    if value in _FALSEY:
        return False
    raise RateLimitConfigError(
        f"{ENABLED_ENV} must be a boolean-like value, got {raw!r}"
    )


def _default_enabled(environ: dict[str, str] | None) -> bool:
    """Enable by default only when Hosted auth is configured.

    Loopback demo without ``MUTINY_API_TOKEN`` stays unlimited for local UX/tests.
    Non-loopback binds already require a token (P0-1/P0-4), so public Hosted
    gets rate limits by default. Set ``MUTINY_RATE_LIMIT_ENABLED`` explicitly
    to override.
    """
    if environ is None:
        return configured_api_token() is not None
    raw = environ.get(API_TOKEN_ENV)
    return bool(raw and str(raw).strip())


def _parse_positive_int(name: str, raw: str | None, default: int) -> int:
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip(), 10)
    except ValueError as exc:
        raise RateLimitConfigError(
            f"{name} must be a positive integer, got {raw!r}"
        ) from exc
    if value <= 0:
        raise RateLimitConfigError(
            f"{name} must be > 0 (got {value}); "
            f"set {ENABLED_ENV}=0 to disable rate limiting explicitly"
        )
    return value


def _parse_positive_float(name: str, raw: str | None, default: float) -> float:
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except ValueError as exc:
        raise RateLimitConfigError(
            f"{name} must be a positive number, got {raw!r}"
        ) from exc
    if value <= 0:
        raise RateLimitConfigError(
            f"{name} must be > 0 (got {value}); "
            f"set {ENABLED_ENV}=0 to disable rate limiting explicitly"
        )
    return value


def load_rate_limit_config(
    environ: dict[str, str] | None = None,
) -> RateLimitConfig:
    """Load rate-limit config from the environment (fail closed on invalid)."""
    env = os.environ if environ is None else environ
    parsed = _parse_enabled(env.get(ENABLED_ENV))
    enabled = _default_enabled(environ) if parsed is None else parsed
    return RateLimitConfig(
        enabled=enabled,
        health=CategoryLimit(
            rpm=_parse_positive_int(
                HEALTH_RPM_ENV, env.get(HEALTH_RPM_ENV), DEFAULT_HEALTH_RPM
            ),
            burst=_parse_positive_int(
                HEALTH_BURST_ENV, env.get(HEALTH_BURST_ENV), DEFAULT_HEALTH_BURST
            ),
        ),
        normal=CategoryLimit(
            rpm=_parse_positive_int(
                NORMAL_RPM_ENV, env.get(NORMAL_RPM_ENV), DEFAULT_NORMAL_RPM
            ),
            burst=_parse_positive_int(
                NORMAL_BURST_ENV, env.get(NORMAL_BURST_ENV), DEFAULT_NORMAL_BURST
            ),
        ),
        expensive=CategoryLimit(
            rpm=_parse_positive_int(
                EXPENSIVE_RPM_ENV,
                env.get(EXPENSIVE_RPM_ENV),
                DEFAULT_EXPENSIVE_RPM,
            ),
            burst=_parse_positive_int(
                EXPENSIVE_BURST_ENV,
                env.get(EXPENSIVE_BURST_ENV),
                DEFAULT_EXPENSIVE_BURST,
            ),
        ),
        ingest=CategoryLimit(
            rpm=_parse_positive_int(
                INGEST_RPM_ENV, env.get(INGEST_RPM_ENV), DEFAULT_INGEST_RPM
            ),
            burst=_parse_positive_int(
                INGEST_BURST_ENV, env.get(INGEST_BURST_ENV), DEFAULT_INGEST_BURST
            ),
        ),
        max_keys=_parse_positive_int(
            MAX_KEYS_ENV, env.get(MAX_KEYS_ENV), DEFAULT_MAX_KEYS
        ),
        idle_seconds=_parse_positive_float(
            IDLE_SECONDS_ENV, env.get(IDLE_SECONDS_ENV), DEFAULT_IDLE_SECONDS
        ),
    )


# ---------------------------------------------------------------------------
# Route classification
# ---------------------------------------------------------------------------

_EXPENSIVE_POST = (
    re.compile(r"^/api/campaigns$"),
    re.compile(r"^/api/campaigns/[^/]+/start$"),
    re.compile(r"^/api/candidates/[^/]+/minimize$"),
    re.compile(r"^/api/candidates/[^/]+/regression$"),
    re.compile(r"^/api/tests/run$"),
)


def classify_endpoint(method: str, path: str) -> RateLimitCategory:
    """Map an HTTP method+path to a rate-limit category."""
    if path in {"/api/health", "/api/meta"}:
        return RateLimitCategory.HEALTH
    if path.startswith("/api/ingest/v1/"):
        return RateLimitCategory.INGEST
    if method.upper() == "POST":
        for pattern in _EXPENSIVE_POST:
            if pattern.match(path):
                return RateLimitCategory.EXPENSIVE
    return RateLimitCategory.NORMAL


def rate_limit_identity(request: Request) -> str:
    """Stable limiter identity. Never returns or logs the Bearer secret."""
    expected = configured_api_token()
    if expected is not None:
        provided = extract_bearer_token(request.headers.get("authorization"))
        if provided is not None and tokens_match(
            provided=provided, expected=expected
        ):
            # Single-tenant: one shared bucket for the configured operator.
            return "tenant"
    host = "unknown"
    if request.client is not None and request.client.host:
        # Direct peer address only — do not trust X-Forwarded-For.
        host = request.client.host.strip()[:128] or "unknown"
    return f"ip:{host}"


# ---------------------------------------------------------------------------
# Token bucket (monotonic time, bounded keys, thread-safe)
# ---------------------------------------------------------------------------


@dataclass
class _BucketState:
    tokens: float
    updated: float


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: float
    category: RateLimitCategory


class RateLimiter:
    """Thread-safe in-process multi-bucket token limiter."""

    def __init__(
        self,
        config: RateLimitConfig,
        *,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._config = config
        self._time = time_fn or time.monotonic
        self._lock = threading.Lock()
        self._buckets: OrderedDict[str, _BucketState] = OrderedDict()

    @property
    def config(self) -> RateLimitConfig:
        return self._config

    @property
    def bucket_count(self) -> int:
        with self._lock:
            return len(self._buckets)

    def allow(
        self,
        identity: str,
        category: RateLimitCategory,
        *,
        cost: float = 1.0,
    ) -> RateLimitDecision:
        """Consume ``cost`` tokens from ``identity:category`` if available."""
        if not self._config.enabled:
            return RateLimitDecision(
                allowed=True, retry_after=0.0, category=category
            )
        if cost <= 0:
            return RateLimitDecision(
                allowed=True, retry_after=0.0, category=category
            )

        limit = self._config.limit_for(category)
        key = f"{identity}:{category.value}"
        now = self._time()

        with self._lock:
            self._cleanup_locked(now)
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self._config.max_keys:
                    self._evict_oldest_locked()
                bucket = _BucketState(tokens=float(limit.burst), updated=now)
                self._buckets[key] = bucket
            else:
                self._buckets.move_to_end(key)

            elapsed = max(0.0, now - bucket.updated)
            if elapsed > 0:
                bucket.tokens = min(
                    float(limit.burst),
                    bucket.tokens + elapsed * limit.refill_per_sec,
                )
                bucket.updated = now

            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return RateLimitDecision(
                    allowed=True, retry_after=0.0, category=category
                )

            deficit = cost - bucket.tokens
            retry = deficit / limit.refill_per_sec if limit.refill_per_sec > 0 else 60.0
            retry = max(0.0, retry)
            return RateLimitDecision(
                allowed=False, retry_after=retry, category=category
            )

    def _cleanup_locked(self, now: float) -> None:
        idle = self._config.idle_seconds
        stale = [
            key
            for key, bucket in self._buckets.items()
            if (now - bucket.updated) > idle
        ]
        for key in stale:
            del self._buckets[key]

    def _evict_oldest_locked(self) -> None:
        if self._buckets:
            self._buckets.popitem(last=False)


def retry_after_header_seconds(retry_after: float) -> int:
    """HTTP Retry-After as a non-negative whole-second delay."""
    if retry_after <= 0:
        return 0
    return max(1, int(math.ceil(retry_after)))
