import importlib.util
import json
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from snowflake.connector.errors import OperationalError, ProgrammingError

from app.config import AuthConfig, InsightsConfig
from app.services.insights import COLUMNS, InsightsClient, InsightsTimeout, InsightsUnavailable

ACCOUNT = "00000000-0000-4000-8000-000000000101"
URL = f"/api/v1/insights/search/accounts/{ACCOUNT}/top"
ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("provision", ROOT / "workloads/doc_search_api/provision.py")
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)


def raw_rows():
    return [
        (date(2026, 11, 1), 28, ACCOUNT, "document", 1, None,
         "03ebe472-1e21-9b1c-20c5-18a0d26cbe6f", "Synthetic document 1", 2, None, datetime(2026, 10, 25, 9)),
        (date(2026, 11, 1), 28, ACCOUNT, "term", 1, "quarterly report", None, None, 2, 0, datetime(2026, 10, 25, 9)),
        (date(2026, 11, 1), 28, ACCOUNT, "term", 2, "budget", None, None, 1, 1, datetime(2026, 10, 30, 15)),
    ]


def expected_rows():
    import yaml

    examples = yaml.safe_load((ROOT / "workloads/doc_search_api/spec.yaml").read_text())["examples"]
    rows = examples["rows"]
    return sorted(rows, key=lambda row: (row["item_type"], row["rank"]))


def fake_connection():
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = (date(2026, 11, 1),)
    cur.fetchall.return_value = raw_rows()
    return conn, cur


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "test-account")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PATH", "unused-test-path")
    return InsightsConfig(commit="a" * 40, backoff=0.01)


@pytest.mark.parametrize("kind", [None, "term", "document"])
def test_contract(app, client, configured, kind):
    conn, cur = fake_connection()
    cur.fetchall.return_value = [r for r in raw_rows() if kind is None or r[3] == kind]
    backend = InsightsClient(configured, connector=MagicMock(return_value=conn))
    app.config["INSIGHTS_CLIENT"] = backend
    response = client.get(URL, query_string={} if kind is None else {"item_type": kind})
    assert response.status_code == 200
    body = response.json
    assert list(body) == ["account_id", "window_end_date", "window_days", "item_type", "rows"]
    assert body["account_id"] == ACCOUNT
    assert body["window_end_date"] == "2026-11-01"
    assert body["window_days"] == 28 and body["item_type"] == kind
    for row in body["rows"]:
        assert tuple(row) == COLUMNS
        assert type(row["rank"]) is int and type(row["search_count"]) is int
        assert row["last_searched_at"] in ("2026-10-25 09:00:00", "2026-10-30 15:00:00")
    sql, binds = cur.execute.call_args.args
    assert sql.endswith("ORDER BY ITEM_TYPE, RANK")
    assert ACCOUNT in binds and ACCOUNT not in sql
    assert body["rows"] == sorted(body["rows"], key=lambda r: (r["item_type"], r["rank"]))
    backend.close()


@pytest.mark.parametrize("suffix,code", [
    ("?item_type=bad", "invalid_item_type"), ("?item_type=", "invalid_item_type"),
    ("?window_end_date=2026-02-30", "invalid_window_end_date"),
    ("?window_end_date=20261101", "invalid_window_end_date"),
])
def test_bad_query(client, suffix, code):
    response = client.get(URL + suffix)
    assert response.status_code == 400 and response.json["error"] == code
    assert set(response.json) == {"error", "message"}


@pytest.mark.parametrize("account", ["bad", "a" * 37])
def test_bad_account(client, account):
    response = client.get(URL.replace(ACCOUNT, account))
    assert response.status_code == 400 and response.json["error"] == "invalid_account_id"


def test_auth(app, client):
    app.config["APP_CONFIG"] = replace(app.config["APP_CONFIG"], auth=AuthConfig(service_token="secret", require_auth=True))
    from app.main import create_app
    from unittest.mock import patch

    with patch("app.main.MeiliSearchService"):
        secured = create_app(app.config["APP_CONFIG"])
    secured.config["INSIGHTS_CLIENT"] = MagicMock(fetch=MagicMock(return_value=(None, [])))
    c = secured.test_client()
    assert c.get(URL).status_code == 401
    response = c.get(URL, headers={"X-User-ID": "00000000-0000-4000-8000-000000000102"})
    assert response.status_code == 403 and response.json["error"] == "forbidden"
    assert c.get(URL, headers={"X-User-ID": ACCOUNT}).status_code == 200
    assert c.get(URL, headers={"Authorization": "Bearer secret", "X-User-ID": "other"}).status_code == 200


@pytest.mark.parametrize("exception,status,code", [
    (InsightsUnavailable(), 503, "insights_unavailable"),
    (InsightsTimeout(), 504, "insights_timeout"),
])
def test_backend_error(app, client, exception, status, code):
    app.config["INSIGHTS_CLIENT"] = MagicMock(fetch=MagicMock(side_effect=exception))
    response = client.get(URL)
    assert response.status_code == status and response.json["error"] == code
    if status == 503:
        assert response.headers["Retry-After"] == "5"


def test_empty_and_not_configured(app, client, configured, monkeypatch):
    conn, cur = fake_connection()
    cur.fetchone.return_value = (None,)
    backend = InsightsClient(configured, connector=MagicMock(return_value=conn))
    app.config["INSIGHTS_CLIENT"] = backend
    assert client.get(URL).json == dict(account_id=ACCOUNT, window_end_date=None, window_days=28, item_type=None, rows=[])
    backend.close()
    monkeypatch.delenv("SNOWFLAKE_ACCOUNT")
    app.config["INSIGHTS_CLIENT"] = InsightsClient(configured)
    assert client.get(URL).status_code == 503


@pytest.mark.parametrize("error,retried,expected", [
    (OperationalError(msg="network"), True, InsightsUnavailable),
    (ProgrammingError(msg="bad SQL"), False, InsightsUnavailable),
    (ProgrammingError(msg="timeout", errno=604), False, InsightsTimeout),
])
def test_retry_exhaustion(configured, error, retried, expected):
    connector = MagicMock(side_effect=error)
    sleep = MagicMock()
    backend = InsightsClient(configured, connector=connector, sleep=sleep)
    with pytest.raises(expected):
        backend.fetch(ACCOUNT)
    assert connector.call_count == (3 if retried else 1)
    assert sleep.call_count == (2 if retried else 0)
    if retried:
        assert 0.01 <= sleep.call_args_list[0].args[0] <= 0.02
        assert 0.02 <= sleep.call_args_list[1].args[0] <= 0.03
    assert backend.count == 0
    backend.close()


def test_pool_retry_discard_tags_and_timeouts(configured):
    first, cur = fake_connection()
    cur.execute.side_effect = OperationalError(msg="broken")
    second, second_cur = fake_connection()
    connector = MagicMock(side_effect=[first, second])
    backend = InsightsClient(configured, connector=connector, sleep=MagicMock())
    backend.fetch(ACCOUNT)
    backend.fetch(ACCOUNT, "term", "2026-11-01")
    assert connector.call_count == 2
    first.close.assert_called_once()
    params = connector.call_args.kwargs
    assert params["application"] == "Devin_Demo"
    assert params["user"] == "SVC_CS_DOC_SEARCH_API_TOP_ITEMS"
    tag = json.loads(params["session_parameters"]["QUERY_TAG"])
    assert tag["phase"] == "runtime" and tag["csid"] == "cs_doc_search_api_top_items"
    assert "session_url" not in tag
    assert params["session_parameters"]["STATEMENT_TIMEOUT_IN_SECONDS"] == configured.query_timeout
    assert params["login_timeout"] == configured.login_timeout
    assert params["network_timeout"] == configured.network_timeout
    assert second_cur.execute.call_args.kwargs["timeout"] == configured.query_timeout
    backend.close()
    second.close.assert_called_once()


def test_pool_bound(configured):
    conn, _ = fake_connection()
    backend = InsightsClient(replace(configured, pool_size=1, pool_timeout=0.001), connector=MagicMock(return_value=conn))
    with backend.connection():
        with pytest.raises(InsightsUnavailable):
            with backend.connection():
                pytest.fail("pool exceeded bound")
    backend.close()
    with pytest.raises(InsightsUnavailable):
        with backend.connection():
            pytest.fail("closed pool reused")


def test_provision_sql():
    sql = provision.provision_sql("-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----")
    assert len(sql) == 8
    assert "CREATE ROLE IF NOT EXISTS SFEXT_20261105A_DOC_SEARCH_API_ENDPOINT" in sql[0]
    assert "2026-11-19" in sql[0] and "SFEXT_20261105A" in sql[0]
    grants = [s for s in sql if s.startswith("GRANT")]
    assert len(grants) == 5
    assert all("SELECT" in s or "USAGE" in s or "GRANT ROLE" in s for s in grants)
    assert "TYPE = SERVICE" in sql[5] and "SVC_CS_DOC_SEARCH_API_TOP_ITEMS" in sql[5]
    assert all("ALTER WAREHOUSE" not in s for s in sql)
