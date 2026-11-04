from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import validate_provenance as vp  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
WORKLOADS = ("doc_usage_dashboard", "doc_search_api", "churn_model")


def _doc(workload: str = "doc_usage_dashboard") -> dict:
    return vp.load(ROOT / "workloads" / workload / "provenance.yaml")


@pytest.mark.parametrize("workload", WORKLOADS)
def test_committed_provenance_files_are_valid(workload: str) -> None:
    path = ROOT / "workloads" / workload / "provenance.yaml"
    assert vp.validate(vp.load(path), path) == []


def test_every_indexed_workload_has_provenance() -> None:
    import yaml

    index = yaml.safe_load((ROOT / "workloads" / "index.yaml").read_text())
    assert sorted(w["name"] for w in index["workloads"]) == sorted(WORKLOADS)


def test_schema_is_valid_draft_2020_12() -> None:
    vp.jsonschema.Draft202012Validator.check_schema(vp.schema())


def _errors(mutate) -> list[str]:
    doc = copy.deepcopy(_doc())
    mutate(doc)
    return vp.validate(doc, ROOT / "workloads" / "doc_usage_dashboard" / "provenance.yaml")


def _object(doc: dict, kind: str) -> dict:
    return next(item for item in doc["deployed_objects"] if item["type"] == kind)


def test_unreported_usage_must_be_pending_not_zero_or_null() -> None:
    def zero(d):
        d["usage"]["credits_runtime"] = 0  # noqa: E704

    def null(d):
        d["usage"]["credits_dev"] = None  # noqa: E704

    def missing(d):
        del d["usage"]["credits_idle"]  # noqa: E704

    assert any("pending" in e for e in _errors(zero))
    assert _errors(null)
    assert _errors(missing)


def test_reported_usage_accepts_real_zero() -> None:
    def reported(d):
        d["usage"].update(
            reported_through="2026-11-30T23:59:59Z",
            credits_dev=0.42,
            credits_runtime=0,
            credits_idle=0.1,
            query_count_dev=12,
            query_count_runtime=0,
        )

    assert _errors(reported) == []

    def partly(d):
        d["usage"].update(reported_through="2026-11-30T23:59:59Z", credits_idle="pending")

    assert _errors(partly) == []


def test_pending_ai_credits_are_valid_when_usage_is_unreported() -> None:
    def pending(d):
        d["usage"].update(credits_ai_dev="pending", credits_ai_runtime="pending")

    assert _errors(pending) == []


def test_unreported_ai_credits_must_be_pending() -> None:
    def reported_ai(d):
        d["usage"]["credits_ai_dev"] = 0.25

    assert any("credits_ai_dev" in e for e in _errors(reported_ai))


def test_reported_ai_credits_accept_numeric_values() -> None:
    def reported(d):
        d["usage"].update(
            reported_through="2026-11-30T23:59:59Z",
            credits_dev=0.42,
            credits_runtime=0.3,
            credits_ai_dev=0.25,
            credits_ai_runtime=0.1,
            credits_idle=0.1,
            query_count_dev=12,
            query_count_runtime=3,
        )

    assert _errors(reported) == []


def test_unknown_ai_credit_key_is_rejected_by_schema() -> None:
    def unknown(d):
        d["usage"]["credits_cortex"] = 0

    assert any("credits_cortex" in e for e in _errors(unknown))


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda d: d["warehouse"].update(name="SFNFR_20261104_WH_OTHER"), "warehouse/name"),
        (lambda d: d["warehouse"].update(auto_suspend_seconds=300), "auto_suspend_seconds"),
        (lambda d: d["warehouse"].update(size="SMALL"), "size"),
        (lambda d: d["warehouse"]["resource_monitor"].update(name="SFNFR_20261104_RM_SHARED"), "resource_monitor"),
        (lambda d: d["endpoints"][0].update(service_user="SFNFR_20261104_SVC_CS_DOC_USAGE_DASHBOARD"), "service_user"),
        (lambda d: d["endpoints"][0].update(application="other"), "application"),
        (lambda d: d["endpoints"][0].update(csid="cs_doc_usage_dashboard_other"), "csids"),
        (lambda d: d["source"].update(commit="63afed1"), "commit"),
        (lambda d: d["source"].update(session="https://example.com/x"), "session"),
        (lambda d: d.update(run_token="SFNFR_20250101"), "run_token"),
        (lambda d: d.update(workload="churn_model"), "workload"),
        (lambda d: _object(d, "warehouse").pop("devin_csid"), "devin_csid"),
        (lambda d: _object(d, "warehouse").update(devin_csid="cs_other"), "devin_csid"),
        (lambda d: _object(d, "schema").update(devin_csid=d["endpoints"][0]["csid"]), "does not carry"),
        (lambda d: d["deployed_objects"].remove(_object(d, "database")), "database"),
        (lambda d: (_object(d, "database").update(state="deployed"), _object(d, "database").pop("deployed_at", None)), "deployed_at"),
        (lambda d: _object(d, "task").update(name="SFNFR_20261104_DB_OTHER.ANALYTICS.REFRESH_X"), "expected at most one task"),
        (
            lambda d: _object(d, "task").update(name="SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.RAW.OTHER_REFRESH"),
            "named SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.ANALYTICS.REFRESH_DOC_USAGE_DASHBOARD",
        ),
        (lambda d: _object(d, "streamlit").update(name="SFNFR_20261104_DB_DOC_USAGE_DASHBOARD.ANALYTICS.APP"), "streamlit"),
        (lambda d: d["deployed_objects"].append(dict(_object(d, "task"))), "expected at most one task"),
        (lambda d: d.update(extra=1), "extra"),
    ],
)
def test_validator_rejects_rule_breaks(mutate, needle: str) -> None:
    errors = _errors(mutate)
    assert errors, "expected a validation error"
    assert any(needle in e for e in errors), errors


def test_deployed_object_needs_timestamp_and_commit() -> None:
    def deployed(d):
        _object(d, "database").update(state="deployed", deployed_at="2026-11-05T10:00:00Z", deployed_commit="a" * 40)

    assert _errors(deployed) == []


def test_unquoted_numeric_commit_is_rejected(tmp_path: Path) -> None:
    text = (ROOT / "workloads" / "doc_usage_dashboard" / "provenance.yaml").read_text()
    lines = [
        "  commit: 1234567890123456789012345678901234567890" if line.startswith("  commit:") else line
        for line in text.splitlines()
    ]
    target = tmp_path / "doc_usage_dashboard" / "provenance.yaml"
    target.parent.mkdir()
    target.write_text("\n".join(lines) + "\n")
    assert any("commit" in e for e in vp.validate(vp.load(target), target, root=ROOT))


def test_timestamps_stay_strings() -> None:
    import yaml

    doc = yaml.load("reported_through: 2026-11-30T23:59:59Z\n", Loader=vp._StringTimestampLoader)
    assert doc == {"reported_through": "2026-11-30T23:59:59Z"}


def test_cli_reports_each_file(capsys) -> None:
    assert vp.main([]) == 0
    out = capsys.readouterr().out
    assert out.count("ok   workloads/") == 3
