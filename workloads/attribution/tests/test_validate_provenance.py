import copy
from pathlib import Path

import pytest
import validate_provenance as vp

WORKLOADS = ("doc_usage_dashboard", "doc_search_api", "churn_model")


def _quality():
    return {
        "suite": "tag:dq_any_workload",
        "ran_at": "2026-11-05T12:00:00Z",
        "commit": "a" * 40,
        "refresh_task_run": {
            "query_id": "query-id",
            "graph_run_group_id": "group-id",
            "scheduled_time": "2026-11-05T11:00:00+00:00",
        },
        "tests": [{"name": "freshness", "check": "freshness", "status": "pass", "failing_rows": 0, "cause": ""}],
    }


@pytest.mark.parametrize("workload", WORKLOADS)
@pytest.mark.parametrize("status,rows,cause", [("pass", 0, ""), ("fail", 1, "missing export")])
def test_optional_quality_is_reusable(workload, status, rows, cause):
    doc = _doc(workload)
    doc["data_quality"] = _quality()
    doc["data_quality"]["tests"][0].update(status=status, failing_rows=rows, cause=cause)
    assert vp.validate(doc) == []


@pytest.mark.parametrize("field,value", [
    ("suite", "dq_bad"), ("commit", "pending"), ("ran_at", "2026-11-05"),
    ("ran_at", "2026-11-05T12:00:00+01:00"), ("ran_at", "2026-02-30T12:00:00Z"),
    ("refresh_task_run", {}), ("tests", []),
])
def test_quality_rejects_invalid_metadata(field, value):
    doc = _doc()
    doc["data_quality"] = _quality()
    doc["data_quality"][field] = value
    assert vp.validate(doc)


@pytest.mark.parametrize("change", [
    {"status": "fail"}, {"status": "fail", "failing_rows": 1},
    {"status": "fail", "failing_rows": 1, "cause": "   "},
    {"failing_rows": 1}, {"failing_rows": -1}, {"failing_rows": 0.5},
    {"status": "unknown"}, {"check": "other"}, {"name": ""},
])
def test_quality_rejects_invalid_test_result(change):
    doc = _doc()
    doc["data_quality"] = _quality()
    doc["data_quality"]["tests"][0].update(change)
    assert vp.validate(doc)


def _path(workload):
    return vp.ROOT / "workloads" / workload / "provenance.yaml"


def _doc(workload="doc_usage_dashboard"):
    return vp.load(_path(workload))


def _obj(doc, kind):
    return next(o for o in doc["objects"] if o["type"] == kind)


@pytest.mark.parametrize("workload", WORKLOADS)
def test_starting_provenance_is_valid(workload):
    assert vp.validate(_doc(workload), _path(workload)) == []


@pytest.mark.parametrize("size,seconds,valid", [
    ("LARGE", 900, True), ("LARGE", 60, True), ("XSMALL", 60, True),
    ("XSMALL", 900, False), ("LARGE", 300, False),
])
def test_warehouse_suspend_policy(size, seconds, valid):
    doc = _doc()
    doc["warehouse"].update(size=size, auto_suspend_seconds=seconds)
    assert (vp.validate(doc) == []) is valid


def test_configuration_changes_can_be_empty_or_absent():
    doc = _doc("doc_search_api")
    doc["configuration_changes"] = []
    assert vp.validate(doc) == []
    doc.pop("configuration_changes")
    assert vp.validate(doc) == []


@pytest.mark.parametrize("field,value", [
    ("status", "pending"), ("reason", " "), ("environment", ""),
    ("migration", "workloads/doc_search_api/migrations/V9.0.0__missing.sql"),
    ("migration", "workloads/churn_model/migrations/V1.0.0__foundation.sql"),
    ("object", "WH_UNKNOWN"), ("evidence", [{}]), ("from", None),
])
def test_invalid_configuration_changes(field, value):
    doc = _doc("doc_search_api")
    doc["configuration_changes"][0][field] = value
    assert vp.validate(doc)


def test_configuration_evidence_requires_valid_utc_time():
    doc = _doc("doc_search_api")
    doc["configuration_changes"][0]["evidence"][0]["time"] = "2026-02-30T12:00:00Z"
    assert vp.validate(doc)


def _deployment():
    return {
        "attempted": {"commit": "a" * 40, "mode": "deploy", "run_id": "run", "started_at": "2026-11-05T12:00:00Z",
                      "finished_at": "2026-11-05T12:01:00Z", "status": "succeeded", "failed_step": None,
                      "gate": None, "failing_tests": []},
        "deployed": None,
    }


def test_optional_deployment_valid():
    doc = _doc()
    doc["deployment"] = _deployment()
    assert vp.validate(doc) == []
    doc["deployment"]["deployed"] = dict(commit="a" * 40, mode="rollback", run_id="run",
                                         deployed_at="2026-11-05T12:01:00Z", objects=[
                                             dict(type="model", name="old_model", detail="built")])
    assert vp.validate(doc) == []


@pytest.mark.parametrize("field,value", [("commit", "main"), ("status", "pending"),
                                        ("mode", "train"), ("run_id", ""), ("started_at", "yesterday"),
                                        ("status", "failed"), ("failing_tests", [""]),
                                        ("finished_at", "2026-02-30T12:00:00Z")])
def test_invalid_deployment_attempt(field, value):
    doc = _doc()
    doc["deployment"] = _deployment()
    doc["deployment"]["attempted"][field] = value
    assert vp.validate(doc)


def test_starting_usage_is_pending_and_cortex_is_separate():
    for workload in WORKLOADS:
        usage = _doc(workload)["usage"]
        for phase in ("dev", "runtime"):
            assert set(usage[phase].values()) == {"pending"}
            assert not any("cortex" in k for k in usage[phase])
            assert set(usage["cortex"][phase].values()) == {"pending"}


def test_main_checks_every_workload(capsys):
    assert vp.main([]) == 0
    out = capsys.readouterr().out
    for workload in WORKLOADS:
        assert f"ok   workloads/{workload}/provenance.yaml" in out


def _errors(mutate, workload="doc_usage_dashboard"):
    doc = copy.deepcopy(_doc(workload))
    mutate(doc)
    return vp.validate(doc, _path(workload))


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda d: d["endpoints"][0].update(service_user="SVC_SOMEONE_ELSE"), "service_user"),
        (lambda d: d["endpoints"][0].update(csid="cs_churn_model_account_score"), "not an endpoint"),
        (lambda d: d["endpoints"][0].update(auth="password"), "key_pair"),
        (lambda d: d["application"].update(registration="registered"), "unregistered"),
        (lambda d: d["application"].update(name="OtterWorks"), "Devin_Demo"),
        (lambda d: _obj(d, "streamlit").pop("devin_csid"), "must carry DEVIN_CSID"),
        (lambda d: _obj(d, "task").update(devin_csid="cs_churn_model_account_score"), "should be"),
        (lambda d: d.update(objects=[o for o in d["objects"] if o["type"] != "task"]), "missing the workload task"),
        (lambda d: d.update(objects=[o for o in d["objects"] if o["type"] != "user"]), "missing service user"),
        (lambda d: _obj(d, "schema").update(name="DB_DOC_USAGE_DASHBOARD.WRONG"), "schema should be named"),
        (lambda d: d.update(objects=[o for o in d["objects"] if o["type"] != "schema"]), "missing the workload schema"),
        (lambda d: _obj(d, "database").update(comment='{"run_token":"SFEXT_20261105A"}'), "expiry"),
        (lambda d: _obj(d, "user").pop("comment"), "run token"),
        (lambda d: _obj(d, "resource_monitor").update(name="RM_DOC_USAGE_DASHBOARD"), "run token"),
        (lambda d: d["warehouse"].update(size="SMALL"), "XSMALL"),
        (lambda d: d["warehouse"].update(auto_suspend_seconds=300), "60"),
        (lambda d: d["warehouse"]["resource_monitor"].update(name="RM_X"), "resource_monitor/name"),
        (lambda d: d["usage"]["dev"].update(compute_credits=-1), "compute_credits"),
        (lambda d: d["usage"]["dev"].update(compute_credits=None), "compute_credits"),
        (lambda d: d["usage"]["runtime"].update(cortex_credits=1.0), "cortex_credits"),
        (lambda d: d["usage"].pop("cortex"), "cortex"),
        (lambda d: (d["source"].update(commit="pending"), _obj(d, "database").update(state="provisioned")), "source/commit"),
        (lambda d: d.update(run_token="SFNFR_20261104"), "run_token"),
        (lambda d: d.update(expires="2026-12-01"), "expires"),
        (lambda d: d["query_tag"].update(task_phase="dev"), "runtime"),
        (lambda d: d["source"].update(session_url="https://example.com"), "session_url"),
    ],
)
def test_rule_violations_are_reported(mutate, expected):
    errors = _errors(mutate)
    assert errors, "expected a validation error"
    assert any(expected in e for e in errors), errors


def test_numbers_replace_pending_once_reported():
    def report(d):
        d["usage"]["reported_through"] = "2026-11-06T00:00:00Z"
        d["usage"]["dev"].update(compute_credits=0.0123, query_acceleration_credits=0, query_count=14)
        d["usage"]["cortex"]["dev"].update(cortex_credits=0.4, cortex_tokens=1200)
        d["source"]["commit"] = "a271367cd476545f60e8982458d616c5dc7151bb"
        _obj(d, "database")["state"] = "provisioned"

    assert _errors(report) == []


def test_directory_must_match_workload(tmp_path):
    doc = _doc()
    errors = vp.validate(doc, Path(tmp_path / "churn_model" / "provenance.yaml"))
    assert any("does not match its directory" in e for e in errors)


def test_self_consistent_unregistered_workload_is_rejected(tmp_path):
    path = tmp_path / "new_demo" / "provenance.yaml"
    path.parent.mkdir()
    text = _path("doc_usage_dashboard").read_text()
    path.write_text(text.replace("doc_usage_dashboard", "new_demo").replace("DOC_USAGE_DASHBOARD", "NEW_DEMO"))
    assert vp.validate(vp.load(path), path) == [
        "workload 'new_demo' has no registered endpoints in sf_attribution.ENDPOINTS"
    ]


def test_raw_schema_allowed_but_wrong_database_rejected():
    doc = _doc()
    raw = next(obj for obj in doc["objects"] if obj["type"] == "schema" and obj["name"].endswith(".RAW"))
    assert vp.validate(doc) == []
    raw["name"] = "DB_OTHER_SFEXT_20261105A.RAW"
    assert any("schema should be named" in error for error in vp.validate(doc))


def test_main_reports_failures(tmp_path, capsys):
    bad = tmp_path / "doc_usage_dashboard" / "provenance.yaml"
    bad.parent.mkdir()
    bad.write_text(_path("doc_usage_dashboard").read_text().replace("registration: unregistered", "registration: yes"))
    assert vp.main([str(bad)]) == 1
    assert "FAIL" in capsys.readouterr().out
