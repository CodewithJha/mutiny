"""P1-2: in-process Hosted API rate limiter (unit)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from mutiny_api.auth import API_TOKEN_ENV
from mutiny_api.rate_limit import (
    ENABLED_ENV,
    MAX_KEYS_ENV,
    NORMAL_BURST_ENV,
    NORMAL_RPM_ENV,
    RateLimitCategory,
    RateLimitConfigError,
    RateLimiter,
    classify_endpoint,
    load_rate_limit_config,
    retry_after_header_seconds,
)


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def _cfg(**overrides: object):
    base = {
        ENABLED_ENV: "1",
        NORMAL_RPM_ENV: "60",
        NORMAL_BURST_ENV: "3",
        "MUTINY_RATE_LIMIT_EXPENSIVE_RPM": "30",
        "MUTINY_RATE_LIMIT_EXPENSIVE_BURST": "2",
        "MUTINY_RATE_LIMIT_INGEST_RPM": "30",
        "MUTINY_RATE_LIMIT_INGEST_BURST": "2",
        "MUTINY_RATE_LIMIT_HEALTH_RPM": "600",
        "MUTINY_RATE_LIMIT_HEALTH_BURST": "10",
        MAX_KEYS_ENV: "8",
        "MUTINY_RATE_LIMIT_IDLE_SECONDS": "10",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return load_rate_limit_config(base)


def test_classify_endpoint_categories() -> None:
    assert classify_endpoint("GET", "/api/health") is RateLimitCategory.HEALTH
    assert classify_endpoint("GET", "/api/meta") is RateLimitCategory.HEALTH
    assert classify_endpoint("GET", "/api/campaigns") is RateLimitCategory.NORMAL
    assert classify_endpoint("POST", "/api/projects") is RateLimitCategory.NORMAL
    assert classify_endpoint("POST", "/api/campaigns") is RateLimitCategory.EXPENSIVE
    assert (
        classify_endpoint("POST", "/api/campaigns/abc/start")
        is RateLimitCategory.EXPENSIVE
    )
    assert (
        classify_endpoint("POST", "/api/candidates/c1/minimize")
        is RateLimitCategory.EXPENSIVE
    )
    assert (
        classify_endpoint("POST", "/api/candidates/c1/regression")
        is RateLimitCategory.EXPENSIVE
    )
    assert classify_endpoint("POST", "/api/tests/run") is RateLimitCategory.EXPENSIVE
    assert (
        classify_endpoint("POST", "/api/ingest/v1/campaigns")
        is RateLimitCategory.INGEST
    )
    assert (
        classify_endpoint("POST", "/api/ingest/v1/campaigns/x/batch")
        is RateLimitCategory.INGEST
    )


def test_config_defaults_and_disable() -> None:
    # No auth token → local demo default is disabled.
    cfg = load_rate_limit_config({})
    assert cfg.enabled is False
    assert cfg.normal.rpm == 600
    assert cfg.expensive.burst == 15

    # Auth configured → rate limits on by default.
    on = load_rate_limit_config({API_TOKEN_ENV: "secret-token"})
    assert on.enabled is True

    off = load_rate_limit_config({ENABLED_ENV: "0", API_TOKEN_ENV: "secret-token"})
    assert off.enabled is False

    forced = load_rate_limit_config({ENABLED_ENV: "1"})
    assert forced.enabled is True


def test_19_invalid_config_fails_closed() -> None:
    with pytest.raises(RateLimitConfigError, match="> 0"):
        load_rate_limit_config({NORMAL_RPM_ENV: "0"})
    with pytest.raises(RateLimitConfigError, match="positive integer"):
        load_rate_limit_config({NORMAL_RPM_ENV: "nope"})
    with pytest.raises(RateLimitConfigError, match="boolean"):
        load_rate_limit_config({ENABLED_ENV: "maybe"})


def test_allow_under_limit_and_exhaust() -> None:
    clock = FakeClock()
    limiter = RateLimiter(_cfg(), time_fn=clock)
    for _ in range(3):
        d = limiter.allow("ip:1.1.1.1", RateLimitCategory.NORMAL)
        assert d.allowed is True
    denied = limiter.allow("ip:1.1.1.1", RateLimitCategory.NORMAL)
    assert denied.allowed is False
    assert denied.retry_after > 0
    assert retry_after_header_seconds(denied.retry_after) >= 1


def test_05_refill_after_window() -> None:
    clock = FakeClock()
    limiter = RateLimiter(
        _cfg(**{NORMAL_BURST_ENV: "2", NORMAL_RPM_ENV: "60"}), time_fn=clock
    )
    assert limiter.allow("ip:a", RateLimitCategory.NORMAL).allowed
    assert limiter.allow("ip:a", RateLimitCategory.NORMAL).allowed
    assert limiter.allow("ip:a", RateLimitCategory.NORMAL).allowed is False
    # 60 rpm => 1 token/sec; advance 1s for one token.
    clock.advance(1.0)
    assert limiter.allow("ip:a", RateLimitCategory.NORMAL).allowed is True


def test_09_categories_do_not_share_buckets() -> None:
    clock = FakeClock()
    limiter = RateLimiter(
        _cfg(**{NORMAL_BURST_ENV: "1", "MUTINY_RATE_LIMIT_EXPENSIVE_BURST": "1"}),
        time_fn=clock,
    )
    assert limiter.allow("tenant", RateLimitCategory.NORMAL).allowed
    assert limiter.allow("tenant", RateLimitCategory.NORMAL).allowed is False
    assert limiter.allow("tenant", RateLimitCategory.EXPENSIVE).allowed is True
    assert limiter.allow("tenant", RateLimitCategory.INGEST).allowed is True
    assert limiter.allow("tenant", RateLimitCategory.HEALTH).allowed is True


def test_17_bounded_keys_under_many_identities() -> None:
    clock = FakeClock()
    limiter = RateLimiter(_cfg(**{MAX_KEYS_ENV: "5"}), time_fn=clock)
    for i in range(50):
        limiter.allow(f"ip:{i}", RateLimitCategory.NORMAL)
    assert limiter.bucket_count <= 5


def test_18_stale_cleanup() -> None:
    clock = FakeClock()
    limiter = RateLimiter(
        _cfg(**{MAX_KEYS_ENV: "100", "MUTINY_RATE_LIMIT_IDLE_SECONDS": "5"}),
        time_fn=clock,
    )
    limiter.allow("ip:old", RateLimitCategory.NORMAL)
    assert limiter.bucket_count == 1
    clock.advance(6.0)
    limiter.allow("ip:new", RateLimitCategory.NORMAL)
    assert limiter.bucket_count == 1


def test_23_retry_after_non_negative() -> None:
    assert retry_after_header_seconds(0) == 0
    assert retry_after_header_seconds(-1) == 0
    assert retry_after_header_seconds(0.1) == 1
    assert retry_after_header_seconds(2.2) == 3


def test_24_concurrent_requests_respect_burst() -> None:
    clock = FakeClock()
    burst = 10
    limiter = RateLimiter(
        _cfg(**{NORMAL_BURST_ENV: str(burst), NORMAL_RPM_ENV: "600"}),
        time_fn=clock,
    )
    results: list[bool] = []

    def hit() -> bool:
        return limiter.allow("ip:race", RateLimitCategory.NORMAL).allowed

    with ThreadPoolExecutor(max_workers=32) as pool:
        futs = [pool.submit(hit) for _ in range(40)]
        for fut in as_completed(futs):
            results.append(fut.result())

    assert sum(1 for ok in results if ok) == burst
    assert sum(1 for ok in results if not ok) == 40 - burst


def test_disabled_limiter_allows_all() -> None:
    limiter = RateLimiter(_cfg(**{ENABLED_ENV: "0"}))
    for _ in range(100):
        assert limiter.allow("ip:x", RateLimitCategory.NORMAL).allowed
