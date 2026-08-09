"""Featherless OpenAI-compatible client (thin adapter; optional openai SDK).

Business rules do not import this module — campaigns depend on ``LLMClient``.
"""

from __future__ import annotations

from typing import Any

from mutiny_core.llm.config import LLMConfig, load_llm_config_from_env
from mutiny_core.llm.port import LLMClient, LLMError, LLMResponse


class FeatherlessClient(LLMClient):
    """OpenAI-compatible chat completions against Featherless (or compatible)."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or load_llm_config_from_env()
        if not self.config.api_key:
            raise LLMError(
                "Featherless API key not configured "
                "(set MUTINY_FEATHERLESS_API_KEY)"
            )
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMError(
                "openai package required for FeatherlessClient; "
                "install mutiny-core[llm] or pip install openai"
            ) from exc
        self._client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
        )
        return self._client

    def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        client = self._get_client()
        try:
            resp = client.chat.completions.create(
                model=self.config.model,
                temperature=(
                    self.config.temperature if temperature is None else temperature
                ),
                max_tokens=self.config.max_tokens if max_tokens is None else max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # noqa: BLE001 — normalize to LLMError
            raise LLMError(f"Featherless completion failed: {exc}") from exc

        try:
            content = resp.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError) as exc:
            raise LLMError(f"malformed Featherless response: {exc}") from exc

        return LLMResponse(
            content=content,
            model=getattr(resp, "model", None) or self.config.model,
            raw={"id": getattr(resp, "id", None)},
        )


def try_featherless_from_env() -> FeatherlessClient | None:
    """Return a client if API key is present; otherwise None (template-only)."""
    cfg = load_llm_config_from_env()
    if not cfg.configured:
        return None
    try:
        return FeatherlessClient(cfg)
    except LLMError:
        return None
