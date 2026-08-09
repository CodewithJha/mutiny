"""Selection: elitism + fitness-proportional parent sampling."""

from __future__ import annotations

from random import Random
from typing import TypeVar

T = TypeVar("T")

_EPS = 1e-3
_ALPHA = 2.0


def select_elites(
    scored: list[tuple[T, float]],
    *,
    elite_count: int,
) -> list[tuple[T, float]]:
    ordered = sorted(scored, key=lambda x: x[1], reverse=True)
    return ordered[: max(0, elite_count)]


def select_parents(
    scored: list[tuple[T, float]],
    *,
    count: int,
    rng_seed: int = 0,
    epsilon: float = _EPS,
    alpha: float = _ALPHA,
) -> list[tuple[T, float]]:
    """Sample parents with probability ∝ (fitness + ε)^α."""
    if not scored or count <= 0:
        return []
    rng = Random(rng_seed)
    weights = [(f + epsilon) ** alpha for _, f in scored]
    total = sum(weights)
    if total <= 0:
        return [rng.choice(scored) for _ in range(count)]
    out: list[tuple[T, float]] = []
    for i in range(count):
        # Independent draws with fresh sub-seed for stability across counts
        r = Random(rng_seed + i * 9973).random() * total
        acc = 0.0
        chosen = scored[-1]
        for item, w in zip(scored, weights):
            acc += w
            if r <= acc:
                chosen = item
                break
        out.append(chosen)
    return out
