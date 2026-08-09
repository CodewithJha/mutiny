"""Generational campaign engine — headless evolutionary search loop."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from mutiny_core.adapter.port import TargetAdapter, ToolsNotObservableError
from mutiny_core.adapter.runner import execute_conversation
from mutiny_core.campaign.config import CampaignConfig, default_refund_seeds
from mutiny_core.campaign.selection import select_elites, select_parents
from mutiny_core.events import EventType, MutinyEvent
from mutiny_core.fitness import FitnessResult, score_fitness
from mutiny_core.genome.models import AttackGenome
from mutiny_core.llm.port import LLMClient
from mutiny_core.mutate import MutationEngine, derive_attack_focus
from mutiny_core.policy.evaluator import PolicyEvaluator
from mutiny_core.policy.models import PolicyHit, PolicySet
from mutiny_core.trace.models import ExecutionTrace

EventCallback = Callable[[MutinyEvent], None]


class ScoredCandidate(BaseModel):
    genome: AttackGenome
    trace: ExecutionTrace
    fitness: float
    violated: bool
    hits: list[PolicyHit] = Field(default_factory=list)
    signals: dict[str, float] = Field(default_factory=dict)


class CampaignResult(BaseModel):
    status: Literal["completed", "violation", "error"]
    reason: str
    generations_completed: int
    candidates: list[ScoredCandidate] = Field(default_factory=list)
    best: ScoredCandidate | None = None
    violated: bool = False
    events_emitted: int = 0


class CampaignEngine:
    """Evaluate → select → mutate loop over a TargetAdapter."""

    def __init__(
        self,
        *,
        adapter: TargetAdapter,
        policy_set: PolicySet,
        config: CampaignConfig | None = None,
        seeds: list[AttackGenome] | None = None,
        on_event: EventCallback | None = None,
        rng_seed: int = 0,
        mutator: MutationEngine | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.adapter = adapter
        self.policy_set = policy_set
        self.config = config or CampaignConfig()
        self.on_event = on_event
        self.rng_seed = rng_seed
        self._evaluator = PolicyEvaluator()
        self._mutator = mutator or MutationEngine(
            llm=llm,
            rng_seed=rng_seed,
            max_turns=self.config.max_turns,
        )
        self._focus = derive_attack_focus(policy_set)
        self._seeds = seeds
        self._events_emitted = 0

    def run(self) -> CampaignResult:
        cfg = self.config
        started = time.monotonic()
        all_scored: list[ScoredCandidate] = []
        self._emit(
            EventType.CAMPAIGN_STARTED,
            {
                "population_size": cfg.population_size,
                "max_generations": cfg.max_generations,
                "elite_count": cfg.elite_count,
            },
        )

        try:
            population = self._initial_population()
            generations_done = 0

            for gen in range(cfg.max_generations):
                if self._budget_exceeded(started):
                    best = (
                        max(all_scored, key=lambda c: c.fitness) if all_scored else None
                    )
                    self._emit(
                        EventType.CAMPAIGN_COMPLETED,
                        {"reason": "budget", "generations": generations_done},
                    )
                    return CampaignResult(
                        status="completed",
                        reason="budget",
                        generations_completed=generations_done,
                        candidates=all_scored,
                        best=best,
                        violated=any(c.violated for c in all_scored),
                        events_emitted=self._events_emitted,
                    )

                self._emit(
                    EventType.GENERATION_STARTED,
                    {"generation": gen, "population": len(population)},
                )

                scored: list[ScoredCandidate] = []
                for genome in population:
                    candidate = self._evaluate_genome(genome)
                    scored.append(candidate)
                    all_scored.append(candidate)

                    if candidate.violated and cfg.stop_on_first_violation:
                        self._emit(
                            EventType.VIOLATION_DETECTED,
                            {
                                "candidate_id": genome.id,
                                "fitness": candidate.fitness,
                                "generation": gen,
                            },
                        )
                        self._emit(
                            EventType.CAMPAIGN_COMPLETED,
                            {"reason": "violation", "generations": gen + 1},
                        )
                        return CampaignResult(
                            status="violation",
                            reason="violation",
                            generations_completed=gen + 1,
                            candidates=all_scored,
                            best=candidate,
                            violated=True,
                            events_emitted=self._events_emitted,
                        )

                generations_done = gen + 1

                if gen >= cfg.max_generations - 1:
                    break

                population = self._next_generation(scored, generation=gen + 1)

            best = max(all_scored, key=lambda c: c.fitness) if all_scored else None
            violated = any(c.violated for c in all_scored)
            status: Literal["completed", "violation"] = (
                "violation" if violated else "completed"
            )
            self._emit(
                EventType.CAMPAIGN_COMPLETED,
                {
                    "reason": "gmax" if not violated else "violation_at_end",
                    "generations": generations_done,
                },
            )
            return CampaignResult(
                status=status,
                reason="gmax" if not violated else "violation_at_end",
                generations_completed=generations_done,
                candidates=all_scored,
                best=best,
                violated=violated,
                events_emitted=self._events_emitted,
            )

        except ToolsNotObservableError as exc:
            self._emit(EventType.CAMPAIGN_ERROR, {"error": str(exc)})
            return CampaignResult(
                status="error",
                reason="tools_not_observable",
                generations_completed=0,
                candidates=all_scored,
                best=None,
                violated=False,
                events_emitted=self._events_emitted,
            )

    def _initial_population(self) -> list[AttackGenome]:
        seeds = self._seeds or default_refund_seeds(
            target_rule_ids=list(self._focus.rule_ids)
        )
        n = self.config.population_size
        pop: list[AttackGenome] = []
        i = 0
        while len(pop) < n:
            g = seeds[i % len(seeds)].model_copy(deep=True)
            if i >= len(seeds):
                g.id = f"{g.id}-pad-{i}"
            g.generation = 0
            pop.append(g)
            self._emit(
                EventType.CANDIDATE_CREATED,
                {
                    "candidate_id": g.id,
                    "generation": 0,
                    "strategy": g.strategy,
                },
            )
            i += 1
        return pop[:n]

    def _evaluate_genome(self, genome: AttackGenome) -> ScoredCandidate:
        self._emit(
            EventType.CANDIDATE_EXECUTING,
            {"candidate_id": genome.id, "generation": genome.generation},
        )
        messages = [m.content for m in genome.messages]
        session_id = f"camp-{genome.id}"
        trace = execute_conversation(
            self.adapter,
            messages,
            candidate_id=genome.id,
            session_id=session_id,
        )
        context = self.adapter.context(session_id)
        hits = self._evaluator.evaluate(self.policy_set, trace, context)
        fitness_result: FitnessResult = score_fitness(self.policy_set, trace, hits)
        trace.policy_hits = hits
        trace.fitness = fitness_result.fitness
        if fitness_result.violated:
            trace.status = "violator"

        candidate = ScoredCandidate(
            genome=genome,
            trace=trace,
            fitness=fitness_result.fitness,
            violated=fitness_result.violated,
            hits=hits,
            signals=fitness_result.signals,
        )
        self._emit(
            EventType.CANDIDATE_SCORED,
            {
                "candidate_id": genome.id,
                "generation": genome.generation,
                "fitness": candidate.fitness,
                "violated": candidate.violated,
                "parent_id": genome.parent_id,
                "mutations": list(genome.mutations),
                "strategy": genome.strategy,
                "target_rule_ids": list(genome.target_rule_ids),
                "genome": genome.model_dump(),
                "trace": trace.model_dump(mode="json"),
                "hits": [h.model_dump(mode="json") for h in hits],
                "signals": dict(fitness_result.signals),
            },
        )
        return candidate

    def _next_generation(
        self, scored: list[ScoredCandidate], *, generation: int
    ) -> list[AttackGenome]:
        cfg = self.config
        pairs = [(c.genome, c.fitness) for c in scored]
        elites = [g for g, _ in select_elites(pairs, elite_count=cfg.elite_count)]

        next_pop: list[AttackGenome] = []
        for e in elites:
            carried = e.model_copy(deep=True)
            carried.metadata = {
                **carried.metadata,
                "elite": True,
                "from_gen": e.generation,
            }
            next_pop.append(carried)

        n_children = cfg.population_size - len(next_pop)
        parents = select_parents(
            pairs,
            count=max(n_children, 0),
            rng_seed=self.rng_seed + generation * 17,
        )
        for parent, _ in parents[:n_children]:
            child = self._mutator.mutate(parent, self._focus, generation=generation)
            next_pop.append(child)
            self._emit(
                EventType.CANDIDATE_CREATED,
                {
                    "candidate_id": child.id,
                    "generation": generation,
                    "parent_id": child.parent_id,
                    "strategy": child.strategy,
                    "mutations": list(child.mutations),
                },
            )
        return next_pop[: cfg.population_size]

    def _budget_exceeded(self, started: float) -> bool:
        limit = self.config.wall_clock_seconds
        if limit is None:
            return False
        return (time.monotonic() - started) >= limit

    def _emit(self, event_type: EventType, payload: dict[str, Any]) -> None:
        self._events_emitted += 1
        if self.on_event is None:
            return
        self.on_event(MutinyEvent(type=event_type, payload=payload))
