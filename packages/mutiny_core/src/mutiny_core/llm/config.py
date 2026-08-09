"""Mutation / LLM config from environment (no secrets committed)."""

from __future__ import annotations

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
      MUTINY_FEATHERLESS_API_KEY or FEATHERLESS_API_KEY or OPENAI_API_KEY
      MUTINY_FEATHERLESS_BASE_URL (default Featherless)
      MUTINY_MUTATION_MODEL
      MUTINY_LLM_TIMEOUT
      MUTINY_LLM_TEMPERATURE
    """
    api_key = (
        os.environ.get("MUTINY_FEATHERLESS_API_KEY")
        or os.environ.get("FEATHERLESS_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    base_url = os.environ.get(
        "MUTINY_FEATHERLESS_BASE_URL", DEFAULT_FEATHERLESS_BASE_URL
    )
    model = os.environ.get("MUTINY_MUTATION_MODEL", DEFAULT_MUTATION_MODEL)
    timeout = float(os.environ.get("MUTINY_LLM_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)))
    temperature = float(os.environ.get("MUTINY_LLM_TEMPERATURE", "0.7"))
    return LLMConfig(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        model=model,
        timeout_seconds=timeout,
        temperature=temperature,
    )
