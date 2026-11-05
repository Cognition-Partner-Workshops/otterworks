import json
from datetime import date

import pytest

import dashboard as d

CONFIG = {"table": "DB.APP.ACCOUNT_STORAGE_USAGE"}
SELECTED = date(2026, 11, 2)
EXPECTED_COLUMNS = (
    "snapshot_date, account_id, account_email, tier, quota_bytes, used_bytes, "
    "remaining_bytes, usage_pct, usage_band, active_document_count"
)


@pytest.mark.parametrize("builder", [d.account_rows_sql, d.close_to_limit_sql])
def test_account_column_order_and_sort(builder):
    sql, params = builder(CONFIG, SELECTED)
    assert sql.startswith(f"SELECT {EXPECTED_COLUMNS} FROM {CONFIG['table']}")
    assert sql.endswith("ORDER BY usage_pct DESC NULLS LAST, account_id")
    assert params == [SELECTED]
    assert sql.count("?") == len(params)


@pytest.mark.parametrize("search", ["", "ada@example.com", "%' OR 1=1 --", "_", "MiXeD"])
def test_search_is_bound_literal_substring(search):
    sql, params = d.account_rows_sql(CONFIG, SELECTED, search)
    assert params == ([SELECTED, search, search] if search else [SELECTED])
    assert sql.count("?") == len(params)
    if search:
        assert sql == d.account_rows_sql(CONFIG, SELECTED, "another search")[0]
        assert "CONTAINS(LOWER(account_id), LOWER(?))" in sql
        assert "CONTAINS(LOWER(account_email), LOWER(?))" in sql
    else:
        assert "CONTAINS" not in sql


def test_close_to_limit_bands():
    sql, _ = d.close_to_limit_sql(CONFIG, SELECTED)
    assert "AND usage_band IN ('near_limit', 'over_quota')" in sql
    assert "no_quota" not in sql


def test_dates_latest_first():
    assert d.snapshot_dates_sql(CONFIG) == (
        "SELECT DISTINCT snapshot_date FROM DB.APP.ACCOUNT_STORAGE_USAGE ORDER BY snapshot_date DESC", []
    )


@pytest.mark.parametrize("builder,args", [(d.trend_sql, ()), (d.account_history_sql, ("a'--",))])
def test_thirty_day_window(builder, args):
    sql, params = builder(CONFIG, SELECTED, *args)
    assert "snapshot_date > DATEADD(day, -30, TO_DATE(?))" in sql
    assert "snapshot_date <= TO_DATE(?)" in sql
    assert params == [SELECTED, SELECTED, *args]
    assert sql.count("?") == len(params)
    assert sql.endswith("ORDER BY snapshot_date")
    if args:
        assert "AND account_id = ?" in sql
        assert args[0] not in sql


def test_trend_aggregation_and_zero_quota():
    sql, _ = d.trend_sql(CONFIG, SELECTED)
    assert "COUNT(*) AS account_count" in sql
    assert "COUNT(CASE WHEN usage_band IN ('near_limit', 'over_quota') THEN 1 END)" in sql
    assert "SUM(used_bytes) AS used_bytes, SUM(quota_bytes) AS quota_bytes" in sql
    assert "ROUND(SUM(used_bytes) / NULLIF(SUM(quota_bytes), 0) * 100, 2) AS usage_pct" in sql
    assert "GROUP BY snapshot_date" in sql


@pytest.mark.parametrize("table", ["x; DROP TABLE x", "a.b.c.d", '"quoted"', "a --", "a\n", "", None])
def test_invalid_table_rejected_by_every_builder(table):
    config = {"table": table}
    for builder, args in (
        (d.account_rows_sql, (SELECTED,)), (d.close_to_limit_sql, (SELECTED,)),
        (d.snapshot_dates_sql, ()), (d.trend_sql, (SELECTED,)),
        (d.account_history_sql, (SELECTED, "id")),
    ):
        with pytest.raises(ValueError):
            builder(config, *args)


@pytest.mark.parametrize("table", ["a", "SCHEMA.table_1", "DB.APP.TABLE$1"])
def test_valid_tables(table):
    assert d.table_name({"table": table}) == table


@pytest.mark.parametrize("as_string", [False, True])
def test_statement_comment_escapes_delimiters_preserving_json(as_string):
    tag = {"csid": "cs_doc_usage_dashboard_account_usage", "run_id": "*/ SELECT 1 /*"}
    comment = d.statement_comment({"query_tag": json.dumps(tag) if as_string else tag})
    assert comment.startswith(" /* ") and comment.endswith(" */")
    body = comment[4:-3]
    assert "*/" not in body and "/*" not in body
    assert json.loads(body) == tag


def test_load_config(tmp_path):
    config = {**CONFIG, "query_tag_sql": "ALTER SESSION SET QUERY_TAG = '{}'", "query_tag": {}}
    (tmp_path / "runtime_config.json").write_text(json.dumps(config))
    assert d.load_runtime_config(tmp_path) == config


@pytest.mark.parametrize("change", [{"table": "x;--"}, {"query_tag": []}, {"query_tag_sql": ""}])
def test_load_invalid_config(tmp_path, change):
    config = {**CONFIG, "query_tag_sql": "ALTER SESSION SET QUERY_TAG = '{}'", "query_tag": {}, **change}
    (tmp_path / "runtime_config.json").write_text(json.dumps(config))
    with pytest.raises(ValueError):
        d.load_runtime_config(tmp_path)


def test_missing_config(tmp_path):
    with pytest.raises(FileNotFoundError):
        d.load_runtime_config(tmp_path)


def test_missing_config_key(tmp_path):
    (tmp_path / "runtime_config.json").write_text(json.dumps(CONFIG))
    with pytest.raises(ValueError, match="query_tag_sql"):
        d.load_runtime_config(tmp_path)
