"""Mutiny Core — deterministic domain kernel.

AI proposes; code proves. No LLM acceptance oracles live here.
"""

from mutiny_core.adapter import (
    TargetAdapter,
    ToolsNotObservableError,
    execute_conversation,
)
from mutiny_core.campaign import (
    CampaignConfig,
    CampaignEngine,
    CampaignResult,
    ScoredCandidate,
    boundary_refund_seeds,
    default_refund_seeds,
)
from mutiny_core.events import EventType, MutinyEvent
from mutiny_core.fitness import FitnessResult, score_fitness
from mutiny_core.genome import AttackGenome, AttackMessage
from mutiny_core.llm import (
    DEFAULT_MUTATION_MODEL,
    FeatherlessClient,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMResponse,
    load_llm_config_from_env,
    try_featherless_from_env,
)
from mutiny_core.minimize import MinimizeResult, minimize_genome
from mutiny_core.mutate import (
    AttackFocus,
    MutationEngine,
    MutationProposal,
    TemplateMutator,
    derive_attack_focus,
)
from mutiny_core.policy import (
    ArgConstraint,
    PolicyEvaluator,
    PolicyEvidence,
    PolicyHit,
    PolicyRule,
    PolicySet,
    PolicyValidationError,
    RuleKind,
    explain_rule,
    load_policy_file,
    load_project_policy,
    parse_policy_text,
    policy_set_to_public,
    resolve_policy_path,
    validate_policy_data,
)
from mutiny_core.regress import (
    RegressionNotReproducibleError,
    RegressionTest,
    ReplayResult,
    build_regression,
    replay_regression,
    save_regression,
)
from mutiny_core.trace import (
    AdapterTurnResult,
    ExecutionTrace,
    ToolCall,
    TraceTurn,
)

__all__ = [
    "AdapterTurnResult",
    "ArgConstraint",
    "AttackFocus",
    "AttackGenome",
    "AttackMessage",
    "CampaignConfig",
    "CampaignEngine",
    "CampaignResult",
    "DEFAULT_MUTATION_MODEL",
    "EventType",
    "ExecutionTrace",
    "FeatherlessClient",
    "FitnessResult",
    "LLMClient",
    "LLMConfig",
    "LLMError",
    "LLMResponse",
    "MinimizeResult",
    "MutationEngine",
    "MutationProposal",
    "MutinyEvent",
    "PolicyEvaluator",
    "PolicyEvidence",
    "PolicyHit",
    "PolicyRule",
    "PolicySet",
    "PolicyValidationError",
    "RegressionNotReproducibleError",
    "RegressionTest",
    "ReplayResult",
    "RuleKind",
    "ScoredCandidate",
    "TargetAdapter",
    "TemplateMutator",
    "ToolCall",
    "ToolsNotObservableError",
    "TraceTurn",
    "boundary_refund_seeds",
    "build_regression",
    "default_refund_seeds",
    "derive_attack_focus",
    "execute_conversation",
    "explain_rule",
    "load_llm_config_from_env",
    "load_policy_file",
    "load_project_policy",
    "minimize_genome",
    "parse_policy_text",
    "policy_set_to_public",
    "replay_regression",
    "resolve_policy_path",
    "save_regression",
    "score_fitness",
    "try_featherless_from_env",
    "validate_policy_data",
]

__version__ = "0.1.0"
