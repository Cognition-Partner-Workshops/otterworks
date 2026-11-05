import json

import pytest

import ledger
import sf_attribution as sf


def query(qid="q1", **overrides):
    ep = sf.endpoint("cs_doc_usage_dashboard_account_usage")
    tag = sf.query_tag_json(ep, phase="runtime", commit="a" * 40,
                            run_id=sf.make_run_id(ep.workload, "runtime", nonce="1234abcd"))
    return {"QUERY_ID": qid, "QUERY_TAG": tag, "QUERY_TEXT": "select 1", "USER_NAME": "SYSTEM",
            "WAREHOUSE_NAME": ep.warehouse, **overrides}


def entry(result, csid="cs_doc_usage_dashboard_account_usage"):
    return next(r for r in result["ledger"] if r["csid"] == csid)


def test_registry_union_and_missing_figures_stay_pending():
    result = ledger.build_ledger({}, {"cs_mig_td_parity": {"status": "red/not run"}})
    row = entry(result, "cs_mig_td_parity")
    assert row["query_count"] == 0
    assert row["dev"]["compute_observed_credits"] == "pending"
    assert row["runtime"]["cortex_total_credits"] == "pending"
    assert row["acu"] == "pending"


def test_deduplicate_queries_include_system_preserve_run_ids():
    q = query()
    result = ledger.build_ledger({"query_history": [q], "recent_queries": [q]})
    assert entry(result)["query_count"] == 1
    assert entry(result)["system_query_count"] == 1
    assert entry(result)["run_ids"] == [json.loads(q["QUERY_TAG"])["run_id"]]


@pytest.mark.parametrize("older,newer,expected", [(None, "0.03", "0.03"), (None, 0, "0"),
                                                (0, "0.03", "0"), ("pending", "0.03", "0.03")])
def test_overlapping_exports_fill_missing_values_without_overwriting_reported_zero(older, newer, expected):
    result = ledger.build_ledger({
        "query_history": [query(CREDITS_USED_CLOUD_SERVICES=older)],
        "recent_queries": [query(CREDITS_USED_CLOUD_SERVICES=newer)],
    })
    assert entry(result)["query_count"] == 1
    assert result["timeline"][0]["cloud_services_credits"] == expected


@pytest.mark.parametrize("value,expected", [(None, "pending"), (0, "0"), ("0.125", "0.125")])
def test_zero_is_distinct_from_missing(value, expected):
    result = ledger.build_ledger({"query_history": [query()], "attribution": [
        {"QUERY_ID": "q1", "CREDITS_ATTRIBUTED_COMPUTE": value}]})
    assert entry(result)["runtime"]["compute_observed_credits"] == expected
    assert entry(result)["runtime"]["compute_total_credits"] == "pending"


def test_compute_cortex_and_cloud_services_never_mix():
    result = ledger.build_ledger({"query_history": [query(CREDITS_USED_CLOUD_SERVICES="0.03")],
        "attribution": [{"QUERY_ID": "q1", "CREDITS_ATTRIBUTED_COMPUTE": "0.2"}],
        "cortex": [{"QUERY_ID": "q1", "TOKEN_CREDITS": "0.1", "TOKENS": 20},
                   {"QUERY_ID": "q1", "TOKEN_CREDITS": "0.4", "TOKENS": 30}]})
    row = entry(result)["runtime"]
    assert row["compute_observed_credits"] == "0.2"
    assert row["cortex_observed_credits"] == "0.5"
    assert row["cortex_observed_tokens"] == "50"
    assert row["cloud_services_observed_credits"] == "0.03"


def test_verified_streamlit_trailing_comment_fallback():
    q = query()
    tag = q["QUERY_TAG"]
    q.update(QUERY_TAG='{"StreamlitEngine":"ExecuteStreamlit"}', QUERY_TEXT=f"select 1 /* {tag} */")
    result = ledger.build_ledger({"query_history": [q]})
    assert result["timeline"][0]["tag_source"] == "verified_streamlit_json_comment_fallback"


@pytest.mark.parametrize("bad", ["not_streamlit", "leading_comment", "invalid_commit", "dev_phase"])
def test_comment_fallback_requires_verified_runtime_tag(bad):
    q = query()
    tag = json.loads(q["QUERY_TAG"])
    if bad == "invalid_commit":
        tag["commit"] = "none"
    if bad == "dev_phase":
        tag["phase"] = "dev"
    q.update(QUERY_TAG='{}' if bad == "not_streamlit" else '{"StreamlitEngine":"ExecuteStreamlit"}',
             QUERY_TEXT=f"select 1 /* {json.dumps(tag)} */")
    if bad == "leading_comment":
        q["QUERY_TEXT"] = f"/* {json.dumps(tag)} */ select 1"
    assert ledger.build_ledger({"query_history": [q]})["timeline"] == []


def test_token_boundary_and_control_commit_none():
    tag = {"csid": "cs_golden_admin", "workload": "control", "phase": "dev", "commit": "none",
           "run_id": sf.RUN_TOKEN}
    result = ledger.build_ledger({"query_history": [query(QUERY_TAG=json.dumps(tag))]})
    assert result["timeline"][0]["commit"] == "none"
    assert result["timeline"][0]["attribution_limitations"] == "operator/control commit=none"
    tag["run_id"] += "B"
    assert ledger.build_ledger({"query_history": [query(QUERY_TAG=json.dumps(tag))]})["timeline"] == []


def test_schemachange_suffix_is_labelled():
    q = query()
    q["QUERY_TAG"] += ";schemachange 4.4.0;V1.0.0.sql"
    assert ledger.build_ledger({"query_history": [q]})["timeline"][0]["tag_source"] == "query_tag_schemachange_suffix"


def test_task_execution_id_and_lag_residual_not_assigned_to_idle():
    result = ledger.build_ledger({"query_history": [query()],
        "tasks": [{"QUERY_ID": "q1", "GRAPH_RUN_GROUP_ID": "task-run"}],
        "metering": [{"WAREHOUSE_NAME": "WH_DOC_USAGE_DASHBOARD", "CREDITS_USED_COMPUTE": 1,
                      "CREDITS_USED_CLOUD_SERVICES": "0.1"}]})
    assert result["timeline"][0]["task_execution_id"] == "task-run"
    wh = result["warehouse_reconciliation"][0]
    assert wh["unreconciled_difference_credits"] == "pending"
    assert wh["startup_idle_unrelated_credits"] == "pending"


def test_empty_cortex_export_does_not_prove_zero():
    result = ledger.build_ledger({"query_history": [query()], "cortex": []})
    assert result["timeline"][0]["cortex_credits"] == "pending"


def test_csv_heterogeneous_registrations_and_nested_values(tmp_path):
    path = tmp_path / "ledger.csv"
    ledger.write_csv(path, [{"csid": "cs_a_b", "registration": {"status": "pending"}}, {"csid": "cs_a_c"}])
    assert "pending" in path.read_text()
