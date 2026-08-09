"""LLMClient port — provider-agnostic completion interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class LLMError(RuntimeError):
    """Provider/transport/validation failure for LLM calls."""


class LLMResponse(BaseModel):
    content: str
    model: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class LLMClient(ABC):
    """Port for mutation (and future) model calls. No provider SDKs here."""

    @abstractmethod
    def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Return model text. Raise LLMError on failure/timeout."""
