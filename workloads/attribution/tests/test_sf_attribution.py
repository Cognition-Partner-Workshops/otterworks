from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sf_attribution as attr  # noqa: E402

COMMIT = "63afed16fa75e4cea44499e1567c3562543afaa7"
SESSION = "https://partner-workshops.devinenterprise.com/sessions/e69f745063454d4ba5274736ab6a6356"
RUN_ID = "SFNFR_20261104-doc_usage_dashboard-dev-20261104T201600Z"
RUNTIME_RUN_ID = "SFNFR_20261104-doc_usage_dashboard-runtime-20261104T201600Z"
EP = attr.Endpoint("doc_usage_dashboard", "account_usage")


def test_names_follow_the_rules() -> None:
    assert EP.csid == "cs_doc_usage_dashboard_account_usage"
    assert EP.service_user == "SVC_CS_DOC_USAGE_DASHBOARD_ACCOUNT_USAGE"
    assert EP.warehouse == "WH_DOC_USAGE_DASHBOARD"
    assert EP.database == "DB_DOC_USAGE_DASHBOARD"
    assert attr.resource_monitor_name("churn_model") == "RM_CHURN_MODEL"
    assert attr.task_name("churn_model") == "DB_CHURN_MODEL.ANALYTICS.REFRESH_CHURN_MODEL"
    assert attr.streamlit_name("doc_usage_dashboard") == "DB_DOC_USAGE_DASHBOARD.ANALYTICS.DOC_USAGE_DASHBOARD_APP"


@pytest.mark.parametrize("workload", ["Doc", "doc-usage", "1doc", "doc__usage", "", "doc_"])
def test_rejects_bad_identifiers(workload: str) -> None:
    with pytest.raises(attr.AttributionError):
        attr.csid(workload, "x")


def test_from_csid_round_trips_and_rejects_foreign_csids() -> None:
    assert attr.Endpoint.from_csid("cs_churn_model_account_score", "churn_model") == attr.Endpoint(
        "churn_model", "account_score"
    )
    with pytest.raises(attr.AttributionError):
        attr.Endpoint.from_csid("cs_churn_model_account_score", "doc_search_api")
    with pytest.raises(attr.AttributionError):
        attr.Endpoint.from_csid("cs_churn_model_", "churn_model")


def test_dev_tag_has_fixed_keys_and_session_url() -> None:
    tag = attr.query_tag(EP, phase="dev", commit=COMMIT, run_id=RUN_ID, session_url=SESSION)
    assert list(tag) == ["csid", "workload", "phase", "commit", "run_id", "session_url"]
    assert tag == {
        "csid": "cs_doc_usage_dashboard_account_usage",
        "workload": "doc_usage_dashboard",
        "phase": "dev",
        "commit": COMMIT,
        "run_id": RUN_ID,
        "session_url": SESSION,
    }


def test_runtime_tag_has_no_session_url() -> None:
    tag = attr.query_tag(EP, phase="runtime", commit=COMMIT, run_id=RUNTIME_RUN_ID)
    assert "session_url" not in tag
    with pytest.raises(attr.AttributionError, match="runtime"):
        attr.query_tag(EP, phase="runtime", commit=COMMIT, run_id=RUNTIME_RUN_ID, session_url=SESSION)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"phase": "prod"},
        {"phase": "dev", "session_url": None},
        {"phase": "dev", "session_url": "https://example.com/not-a-session"},
        {"commit": COMMIT[:7]},
        {"commit": COMMIT.upper()},
        {"run_id": "doc_usage_dashboard-dev-1"},
        {"run_id": "SFNFR_20261104"},
        {"run_id": "SFNFR_20261104-doc_usage_dashboard-dev-anything"},
        {"run_id": "SFNFR_20261104-churn_model-dev-20261104T201600Z"},
        {"run_id": RUNTIME_RUN_ID},
    ],
)
def test_tag_refuses_incomplete_labels(kwargs: dict) -> None:
    base = {"phase": "dev", "commit": COMMIT, "run_id": RUN_ID, "session_url": SESSION}
    with pytest.raises(attr.AttributionError):
        attr.query_tag(EP, **{**base, **kwargs})


def test_tag_refuses_run_id_of_another_workload_or_phase() -> None:
    churn = attr.Endpoint("churn_model", "account_score")
    with pytest.raises(attr.AttributionError, match="belongs to doc_usage_dashboard/dev"):
        attr.query_tag(churn, phase="runtime", commit=COMMIT, run_id=attr.make_run_id("doc_usage_dashboard", "dev"))
    with pytest.raises(attr.AttributionError, match="belongs to churn_model/dev"):
        attr.query_tag(churn, phase="runtime", commit=COMMIT, run_id=attr.make_run_id("churn_model", "dev"))
    tag = attr.query_tag(churn, phase="runtime", commit=COMMIT, run_id=attr.make_run_id("churn_model", "runtime"))
    assert tag["run_id"].startswith("SFNFR_20261104-churn_model-runtime-")


def test_tag_json_is_compact_and_parses() -> None:
    text = attr.query_tag_json(EP, phase="dev", commit=COMMIT, run_id=RUN_ID, session_url=SESSION)
    assert " " not in text
    assert json.loads(text)["csid"] == EP.csid
    assert len(text) <= attr.QUERY_TAG_MAX_CHARS


def test_make_run_id_uses_token_and_utc() -> None:
    when = datetime(2026, 11, 4, 20, 16, 5, tzinfo=timezone.utc)
    assert attr.make_run_id("churn_model", "runtime", when) == "SFNFR_20261104-churn_model-runtime-20261104T201605Z"
    assert attr.RUN_ID_RE.match(attr.make_run_id("churn_model", "dev"))
    with pytest.raises(attr.AttributionError):
        attr.make_run_id("churn_model", "dev", when, run_token="sfnfr")


def test_connection_params_label_every_connection() -> None:
    params = attr.connection_params(
        EP,
        account="xy12345",
        private_key_file="/keys/svc.p8",
        phase="dev",
        commit=COMMIT,
        run_id=RUN_ID,
        session_url=SESSION,
    )
    assert params["user"] == "SVC_CS_DOC_USAGE_DASHBOARD_ACCOUNT_USAGE"
    assert params["authenticator"] == "SNOWFLAKE_JWT"
    assert params["application"] == "Devin_Demo"
    assert params["warehouse"] == "WH_DOC_USAGE_DASHBOARD"
    assert params["database"] == "DB_DOC_USAGE_DASHBOARD"
    assert "password" not in params and "role" not in params
    tag = json.loads(params["session_parameters"]["QUERY_TAG"])
    assert tag["phase"] == "dev" and tag["session_url"] == SESSION


def test_connection_params_require_key_pair() -> None:
    with pytest.raises(attr.AttributionError, match="key pair"):
        attr.connection_params(
            EP, account="xy12345", private_key_file="", phase="runtime", commit=COMMIT, run_id=RUNTIME_RUN_ID
        )


def test_connect_passes_params_to_connector(monkeypatch) -> None:
    calls = []
    fake = type(sys)("snowflake.connector")
    fake.connect = lambda **kw: calls.append(kw) or "conn"
    pkg = type(sys)("snowflake")
    pkg.connector = fake
    monkeypatch.setitem(sys.modules, "snowflake", pkg)
    monkeypatch.setitem(sys.modules, "snowflake.connector", fake)
    conn = attr.connect(
        EP,
        account="xy12345",
        private_key_file="/k.p8",
        phase="runtime",
        commit=COMMIT,
        run_id=RUNTIME_RUN_ID,
        role="R_X",
    )
    assert conn == "conn"
    assert calls[0]["role"] == "R_X" and calls[0]["application"] == "Devin_Demo"


def test_task_carries_its_own_runtime_tag() -> None:
    sql = attr.create_task_sql(
        EP, schedule="USING CRON 0 1 * * * UTC", body="SELECT 1", commit=COMMIT, run_id=RUNTIME_RUN_ID
    )
    assert sql.startswith("CREATE OR REPLACE TASK DB_DOC_USAGE_DASHBOARD.ANALYTICS.REFRESH_DOC_USAGE_DASHBOARD")
    assert "WAREHOUSE = WH_DOC_USAGE_DASHBOARD" in sql
    assert f"  WITH TAG ({attr.TAG_FQN} = 'cs_doc_usage_dashboard_account_usage')\n" in sql
    assert sql.index("WITH TAG") < sql.index("WAREHOUSE =")
    literal = sql.split("QUERY_TAG = ", 1)[1].split("\n", 1)[0]
    assert literal.startswith("'") and literal.endswith("'")
    tag = json.loads(literal[1:-1])
    assert tag["phase"] == "runtime" and "session_url" not in tag
    alter = attr.alter_task_query_tag_sql(EP, commit=COMMIT, run_id=RUNTIME_RUN_ID)
    assert alter.startswith("ALTER TASK DB_DOC_USAGE_DASHBOARD.ANALYTICS.REFRESH_DOC_USAGE_DASHBOARD SET QUERY_TAG = '")


def test_task_tag_lists_every_workload_csid() -> None:
    sql = attr.create_task_sql(
        EP,
        schedule="USING CRON 0 1 * * * UTC",
        body="SELECT 1",
        commit=COMMIT,
        run_id=RUNTIME_RUN_ID,
        csids=["cs_doc_usage_dashboard_z", EP.csid],
    )
    assert "= 'cs_doc_usage_dashboard_account_usage,cs_doc_usage_dashboard_z')" in sql
    with pytest.raises(attr.AttributionError, match="256"):
        attr.devin_csid_value([f"cs_w_{i:03d}_{'x' * 20}" for i in range(12)])


def test_streamlit_sets_tag_on_its_session() -> None:
    sql = attr.streamlit_query_tag_sql(EP, commit=COMMIT, run_id=RUNTIME_RUN_ID)
    assert sql.startswith('ALTER SESSION SET QUERY_TAG = \'{"csid":"cs_doc_usage_dashboard_account_usage"')


def test_sql_string_escapes_quotes_and_backslashes() -> None:
    assert attr.sql_string("it's \\ok") == "'it\\'s \\\\ok'"


def test_warehouse_ddl_is_xsmall_60s_with_own_monitor() -> None:
    monitor, warehouse = attr.warehouse_ddl("churn_model")
    assert monitor.startswith("CREATE RESOURCE MONITOR IF NOT EXISTS RM_CHURN_MODEL WITH CREDIT_QUOTA = 10")
    assert "FREQUENCY = MONTHLY" in monitor and "ON 100 PERCENT DO SUSPEND" in monitor
    assert "CREATE WAREHOUSE IF NOT EXISTS WH_CHURN_MODEL" in warehouse
    assert "WAREHOUSE_SIZE = 'XSMALL'" in warehouse and "AUTO_SUSPEND = 60" in warehouse
    assert "RESOURCE_MONITOR = RM_CHURN_MODEL" in warehouse
    with pytest.raises(attr.AttributionError):
        attr.warehouse_ddl("churn_model", credit_quota=0)


def test_service_user_ddl_strips_pem_armor() -> None:
    pem = "-----BEGIN PUBLIC KEY-----\nMIIBIjAN\nBgkqhkiG\n-----END PUBLIC KEY-----\n"
    sql = attr.service_user_ddl(EP, rsa_public_key=pem)
    assert "CREATE USER IF NOT EXISTS SVC_CS_DOC_USAGE_DASHBOARD_ACCOUNT_USAGE TYPE = SERVICE" in sql
    assert "RSA_PUBLIC_KEY = 'MIIBIjANBgkqhkiG'" in sql
    assert "DEFAULT_WAREHOUSE = WH_DOC_USAGE_DASHBOARD" in sql
    with pytest.raises(attr.AttributionError):
        attr.service_user_ddl(EP, rsa_public_key="-----BEGIN PUBLIC KEY-----\n-----END PUBLIC KEY-----")


def test_service_user_ddl_sets_a_plain_role_only() -> None:
    sql = attr.service_user_ddl(EP, rsa_public_key="MIIB", role="R_DOC_USAGE")
    assert "DEFAULT_ROLE = R_DOC_USAGE " in sql


@pytest.mark.parametrize(
    "role",
    ["R_X COMMENT = 'x'", "R_X; DROP DATABASE DB_CHURN_MODEL", '"R X"', "1ROLE", "R-X", "R_X\n"],
)
def test_service_user_ddl_refuses_role_that_is_not_an_identifier(role: str) -> None:
    with pytest.raises(attr.AttributionError, match="role"):
        attr.service_user_ddl(EP, rsa_public_key="MIIB", role=role)


def test_object_tags_cover_warehouse_database_task_streamlit() -> None:
    stmts = attr.object_tag_ddl("doc_usage_dashboard", [EP.csid], streamlit=True)
    assert [s.split()[1] for s in stmts] == ["WAREHOUSE", "DATABASE", "TASK", "STREAMLIT"]
    assert all(s.endswith(f"SET TAG {attr.TAG_FQN} = 'cs_doc_usage_dashboard_account_usage'") for s in stmts)
    assert len(attr.object_tag_ddl("churn_model", ["cs_churn_model_account_score"])) == 3


def test_devin_csid_value_is_sorted_and_deduplicated() -> None:
    assert attr.devin_csid_value(["cs_w_b", "cs_w_a", "cs_w_b"]) == "cs_w_a,cs_w_b"
    with pytest.raises(attr.AttributionError):
        attr.devin_csid_value([])


def test_cli_tag_and_ddl(capsys) -> None:
    rc = attr.main(
        [
            "tag",
            "--csid",
            EP.csid,
            "--workload",
            EP.workload,
            "--phase",
            "runtime",
            "--commit",
            COMMIT,
            "--run-id",
            RUNTIME_RUN_ID,
        ]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["phase"] == "runtime"
    assert (
        attr.main(
            [
                "tag",
                "--csid",
                EP.csid,
                "--workload",
                EP.workload,
                "--phase",
                "dev",
                "--commit",
                COMMIT,
                "--run-id",
                RUN_ID,
            ]
        )
        == 2
    )
    assert attr.main(["ddl", "--workload", "churn_model", "--csid", "cs_churn_model_account_score"]) == 0
    out = capsys.readouterr().out
    assert "CREATE WAREHOUSE IF NOT EXISTS WH_CHURN_MODEL" in out and out.count(";\n") == 5
