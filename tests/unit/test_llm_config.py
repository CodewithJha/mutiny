"""Mutation credentials and numeric configuration must fail closed (#58)."""

import math
from pathlib import Path

import pytest

from mutiny_core.llm import load_llm_config_from_env, try_featherless_from_env
from mutiny_core.llm.config import DEFAULT_FEATHERLESS_BASE_URL


@pytest.fixture(autouse=True)
def clean_llm_env(monkeypatch):
    for name in (
        "MUTINY_FEATHERLESS_API_KEY",
        "FEATHERLESS_API_KEY",
        "OPENAI_API_KEY",
        "MUTINY_FEATHERLESS_BASE_URL",
        "MUTINY_MUTATION_MODEL",
        "MUTINY_LLM_TIMEOUT",
        "MUTINY_LLM_TEMPERATURE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_example_env_does_not_opt_target_key_into_mutations(monkeypatch):
    example = Path(__file__).resolve().parents[2] / ".env.example"
    for line in example.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            name, value = line.split("=", 1)
            monkeypatch.setenv(name, value)
    monkeypatch.setenv("OPENAI_API_KEY", "target-key")
    assert try_featherless_from_env() is None


@pytest.mark.parametrize("base_url", [None, "", "   "])
def test_target_key_alone_does_not_configure_mutator(monkeypatch, base_url):
    monkeypatch.setenv("OPENAI_API_KEY", "target-key")
    if base_url is not None:
        monkeypatch.setenv("MUTINY_FEATHERLESS_BASE_URL", base_url)
    config = load_llm_config_from_env()
    assert not config.configured
    assert config.api_key is None
    assert try_featherless_from_env() is None


@pytest.mark.parametrize(
    "key_name", ["MUTINY_FEATHERLESS_API_KEY", "FEATHERLESS_API_KEY"]
)
def test_dedicated_mutation_key_still_configures_featherless(monkeypatch, key_name):
    monkeypatch.setenv(key_name, "mutation-key")
    monkeypatch.setenv("OPENAI_API_KEY", "target-key")
    client = try_featherless_from_env()
    assert client is not None
    assert client.config.api_key == "mutation-key"
    assert client.config.base_url == DEFAULT_FEATHERLESS_BASE_URL


def test_dedicated_key_precedence(monkeypatch):
    monkeypatch.setenv("MUTINY_FEATHERLESS_API_KEY", "mutiny-key")
    monkeypatch.setenv("FEATHERLESS_API_KEY", "provider-key")
    monkeypatch.setenv("OPENAI_API_KEY", "target-key")
    monkeypatch.setenv("MUTINY_FEATHERLESS_BASE_URL", "https://example.invalid/v1/")
    config = load_llm_config_from_env()
    assert config.api_key == "mutiny-key"
    assert config.base_url == "https://example.invalid/v1"


def test_explicit_endpoint_allows_compatible_key(monkeypatch):
    monkeypatch.setenv("MUTINY_FEATHERLESS_BASE_URL", "https://example.invalid/v1/")
    monkeypatch.setenv("OPENAI_API_KEY", "explicit-compatible-key")
    client = try_featherless_from_env()
    assert client is not None
    assert client.config.api_key == "explicit-compatible-key"
    assert client.config.base_url == "https://example.invalid/v1"


def test_endpoint_without_key_is_unconfigured(monkeypatch):
    monkeypatch.setenv("MUTINY_FEATHERLESS_BASE_URL", "https://example.invalid/v1")
    assert try_featherless_from_env() is None


@pytest.mark.parametrize(
    "key_name", ["MUTINY_FEATHERLESS_API_KEY", "FEATHERLESS_API_KEY"]
)
def test_whitespace_key_does_not_enable_mutator(monkeypatch, key_name):
    monkeypatch.setenv(key_name, "   ")
    monkeypatch.setenv("OPENAI_API_KEY", "target-key")
    assert try_featherless_from_env() is None


@pytest.mark.parametrize(
    "name,value",
    [
        ("MUTINY_LLM_TIMEOUT", "not-a-float"),
        ("MUTINY_LLM_TIMEOUT", ""),
        ("MUTINY_LLM_TIMEOUT", "nan"),
        ("MUTINY_LLM_TIMEOUT", "inf"),
        ("MUTINY_LLM_TIMEOUT", "0"),
        ("MUTINY_LLM_TIMEOUT", "-1"),
        ("MUTINY_LLM_TEMPERATURE", "not-a-float"),
        ("MUTINY_LLM_TEMPERATURE", ""),
        ("MUTINY_LLM_TEMPERATURE", "nan"),
        ("MUTINY_LLM_TEMPERATURE", "inf"),
        ("MUTINY_LLM_TEMPERATURE", "-1"),
    ],
)
@pytest.mark.parametrize("with_key", [False, True])
def test_invalid_numbers_disable_mutation_client(monkeypatch, name, value, with_key):
    if with_key:
        monkeypatch.setenv("MUTINY_FEATHERLESS_API_KEY", "mutation-key")
    monkeypatch.setenv(name, value)
    config = load_llm_config_from_env()
    assert not config.configured
    assert try_featherless_from_env() is None
    assert math.isfinite(config.timeout_seconds) and config.timeout_seconds > 0
    assert math.isfinite(config.temperature) and config.temperature >= 0


@pytest.mark.parametrize("temperature", ["0", "0.7", "1.5"])
def test_valid_numeric_settings_preserved(monkeypatch, temperature):
    monkeypatch.setenv("MUTINY_FEATHERLESS_API_KEY", "mutation-key")
    monkeypatch.setenv("MUTINY_MUTATION_MODEL", "configured-model")
    monkeypatch.setenv("MUTINY_LLM_TIMEOUT", "2.5")
    monkeypatch.setenv("MUTINY_LLM_TEMPERATURE", temperature)
    config = load_llm_config_from_env()
    assert config.configured
    assert config.model == "configured-model"
    assert config.timeout_seconds == 2.5
    assert config.temperature == float(temperature)
