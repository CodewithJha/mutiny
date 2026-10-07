"""Issue #65: campaign knobs must not silently disable mutation."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from mutiny_api.schemas import CampaignCreateRequest
from mutiny_cli.init_cmd import MUTINY_YAML
from mutiny_core.campaign import CampaignConfig


@pytest.mark.parametrize("model", [CampaignConfig, CampaignCreateRequest])
@pytest.mark.parametrize("population_size,elite_count", [(1, 1), (3, 3), (3, 4), (8, 8)])
def test_elites_must_leave_room_for_mutation(model, population_size, elite_count):
    with pytest.raises(ValidationError, match="elite_count must be less than population_size"):
        model(population_size=population_size, elite_count=elite_count)


@pytest.mark.parametrize("model", [CampaignConfig, CampaignCreateRequest])
@pytest.mark.parametrize("population_size,elite_count", [(1, 0), (3, 0), (3, 2)])
def test_valid_elite_counts(model, population_size, elite_count):
    config = model(population_size=population_size, elite_count=elite_count)
    assert config.elite_count == elite_count


def test_product_seed_flag_removed_from_scaffold_sample_and_schema():
    sample = Path(__file__).resolve().parents[2] / "examples/openai_support_agent/mutiny.yaml"
    for document in [MUTINY_YAML, sample.read_text(encoding="utf-8")]:
        config = yaml.safe_load(document)
        assert "use_boundary_seeds" not in config
        CampaignConfig.model_validate(config)
    assert "use_boundary_seeds" not in CampaignCreateRequest.model_json_schema()["properties"]
