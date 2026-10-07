"""Static checks on the committed scenarios and goldens (no infra needed)."""

import json

import pytest

from harness import scenario, settings
from harness.normalize import normalize
from harness.snapshot import dumps

SURFACES = {
    "result.json",
    "s3.json",
    "dynamodb.json",
    "sqs.json",
    "postgres.json",
    "meilisearch.json",
}
SCENARIOS = scenario.discover("all")


def test_every_script_has_a_scenario():
    assert {s.script for s in SCENARIOS} == set(settings.SCRIPTS)


@pytest.mark.parametrize("scn", SCENARIOS, ids=lambda s: s.label)
def test_golden_is_complete_canonical_and_normalized(scn):
    files = {p.name: p.read_text() for p in scn.golden_dir.glob("*.json")}
    assert set(files) == SURFACES
    parsed = {name: json.loads(text) for name, text in files.items()}
    for name, text in files.items():
        assert dumps(parsed[name]) == text, name
    _, replaced = normalize(parsed)
    assert replaced == 0
