"""Mutation / LLM config from environment (no secrets committed)."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass


DEFAULT_FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"
DEFAULT_MUTATION_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class LLMConfig:
    api_key: str | None
    base_url: str
    model: str
    timeout_seconds: float
    temperature: float = 0.7
    max_tokens: int = 1024

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


def load_llm_config_from_env() -> LLMConfig:
    """Read Featherless / OpenAI-compatible settings from env.

    Env vars:
      MUTINY_FEATHERLESS_API_KEY or FEATHERLESS_API_KEY
      MUTINY_FEATHERLESS_BASE_URL (default Featherless; an explicit non-empty
        value opts into using OPENAI_API_KEY when no dedicated key is set)
      MUTINY_MUTATION_MODEL
      MUTINY_LLM_TIMEOUT
      MUTINY_LLM_TEMPERATURE

    Invalid numeric settings disable the optional mutator. CLI and health callers
    can then use their existing template/unconfigured path without raising.
    """
    explicit_base_url = os.environ.get("MUTINY_FEATHERLESS_BASE_URL", "").strip()
    api_key = (
        os.environ.get("MUTINY_FEATHERLESS_API_KEY", "").strip()
        or os.environ.get("FEATHERLESS_API_KEY", "").strip()
        or (os.environ.get("OPENAI_API_KEY", "").strip() if explicit_base_url else None)
        or None
    )
    base_url = explicit_base_url or DEFAULT_FEATHERLESS_BASE_URL
    model = os.environ.get("MUTINY_MUTATION_MODEL", DEFAULT_MUTATION_MODEL)
    try:
        timeout = float(os.environ.get("MUTINY_LLM_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)))
        temperature = float(os.environ.get("MUTINY_LLM_TEMPERATURE", "0.7"))
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        if not math.isfinite(temperature) or temperature < 0:
            raise ValueError("temperature must be non-negative and finite")
    except ValueError:
        api_key = None
        timeout = DEFAULT_TIMEOUT_SECONDS
        temperature = 0.7
    return LLMConfig(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
        timeout_seconds=timeout,
        temperature=temperature,
    )
