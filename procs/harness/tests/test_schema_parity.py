from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parents[3]))

import procs.harness.schema_parity as schema_parity


def transcript(**overrides):
    base = {
        "scenario": "RATING-001",
        "module": "rating",
        "entrypoint": "billing.fn_rate_preview",
        "inputs": {"tenant_id": "t1"},
        "business_fields": {"billable_units": 10, "overage_amount": "0.55"},
        "probes": {"rows": 1},
    }
    base.update(overrides)
    return base


def test_identical_replay_has_no_differences() -> None:
    assert schema_parity.differences(transcript(), transcript()) == []


def test_field_probe_and_missing_values_are_differences() -> None:
    actual = transcript(business_fields={"billable_units": 11}, probes={"rows": 1, "extra": 2})
    found = {(item["kind"], item["name"]): item for item in schema_parity.differences(transcript(), actual)}
    assert found[("field", "billable_units")]["actual"] == 11
    assert found[("field", "overage_amount")]["actual"] == "<absent>"
    assert found[("probe", "extra")]["expected"] == "<absent>"
    assert ("probe", "rows") not in found


def test_changed_inputs_are_a_difference() -> None:
    found = schema_parity.differences(transcript(), transcript(inputs={"tenant_id": "t2"}))
    assert [item["kind"] for item in found] == ["inputs"]


def write_corpus(tmp_path: Path, monkeypatch, modules: dict[str, list[str]], recorded: list[str]) -> None:
    scenarios = tmp_path / "scenarios"
    transcripts = tmp_path / "transcripts"
    for module, ids in modules.items():
        (scenarios / module).mkdir(parents=True)
        (transcripts / module).mkdir(parents=True)
        for scenario_id in ids:
            (scenarios / module / f"{scenario_id}.yaml").write_text(
                yaml.safe_dump({"id": scenario_id, "module": module})
            )
            if scenario_id in recorded:
                (transcripts / module / f"{scenario_id}.json").write_text(
                    json.dumps({"scenario": scenario_id, "module": module})
                )
    routes = tmp_path / "routes.yaml"
    routes.write_text(yaml.safe_dump({"modules": {name: {"status": "pending"} for name in modules}}))
    monkeypatch.setattr(schema_parity.record, "SCENARIOS", scenarios)
    monkeypatch.setattr(schema_parity, "TRANSCRIPTS", transcripts)
    monkeypatch.setattr(schema_parity, "ROUTES", routes)


def test_module_without_recordings_is_reported_not_skipped(tmp_path, monkeypatch) -> None:
    write_corpus(tmp_path, monkeypatch, {"plans": ["PLANS-001"], "dunning": ["DUNNING-001"]}, ["PLANS-001"])
    pairs, missing = schema_parity.load_pairs(None, None)
    assert [scenario["id"] for scenario, _ in pairs] == ["PLANS-001"]
    assert "DUNNING-001: scenario has no transcript" in missing
    assert "dunning: module has no recorded transcripts" in missing


def test_complete_corpus_has_no_coverage_errors(tmp_path, monkeypatch) -> None:
    write_corpus(tmp_path, monkeypatch, {"plans": ["PLANS-001"], "rating": ["RATING-001"]}, ["PLANS-001", "RATING-001"])
    pairs, missing = schema_parity.load_pairs(None, None)
    assert missing == []
    assert [scenario["id"] for scenario, _ in pairs] == ["PLANS-001", "RATING-001"]


def test_migrations_match_the_recorded_sources() -> None:
    assert schema_parity.migration_drift() == []


def test_migration_drift_is_detected(tmp_path, monkeypatch) -> None:
    (tmp_path / "migrations").mkdir()
    (tmp_path / "procs").mkdir()
    for migration, source in schema_parity.MIGRATION_SOURCES.items():
        (tmp_path / source).write_text("CREATE TABLE x ();\n")
        (tmp_path / "migrations" / migration).write_text("CREATE TABLE x ();\n")
    (tmp_path / "migrations" / "0003_rating.sql").write_text("CREATE TABLE y ();\n")
    monkeypatch.setattr(schema_parity, "DB_DIR", tmp_path)
    assert schema_parity.migration_drift() == [
        "migration 0003_rating.sql differs from procs/rating.sql (recordings came from procs/rating.sql)"
    ]


def test_identity_must_be_app_role_over_tls() -> None:
    identity = {"current_user": "billing_owner", "rolsuper": False, "ssl": False}
    assert schema_parity.identity_errors(identity, "billing_app", True) == [
        "connected as billing_owner, expected billing_app",
        "connection is not using TLS",
    ]
    assert schema_parity.identity_errors({**identity, "current_user": "billing_app", "ssl": True}, "billing_app", True) == []
