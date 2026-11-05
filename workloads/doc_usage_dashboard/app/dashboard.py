"""Pure SQL builders for the account storage dashboard."""

import json
import re
from pathlib import Path

COLUMNS = (
    "snapshot_date", "account_id", "account_email", "tier", "quota_bytes",
    "used_bytes", "remaining_bytes", "usage_pct", "usage_band", "active_document_count",
)
ORDER_BY = "ORDER BY usage_pct DESC NULLS LAST, account_id"
TABLE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*){0,2}")
CLOSE_TO_LIMIT = "usage_band IN ('near_limit', 'over_quota')"
WINDOW = "snapshot_date > DATEADD(day, -30, TO_DATE(?)) AND snapshot_date <= TO_DATE(?)"


def table_name(config):
    table = config["table"]
    if not isinstance(table, str) or not TABLE_RE.fullmatch(table):
        raise ValueError("table must be an unquoted Snowflake identifier (up to three parts)")
    return table


def load_runtime_config(app_dir=None):
    path = Path(app_dir) if app_dir is not None else Path(__file__).resolve().parent
    with (path / "runtime_config.json").open() as handle:
        config = json.load(handle)
    table_name(config)
    for key in ("query_tag_sql", "query_tag"):
        if key not in config:
            raise ValueError(f"runtime config is missing {key}")
    if not isinstance(config["query_tag_sql"], str) or not config["query_tag_sql"].strip():
        raise ValueError("query_tag_sql must be a nonempty string")
    statement_prefix(config)
    return config


def statement_prefix(config):
    tag = config["query_tag"]
    if isinstance(tag, str):
        tag = json.loads(tag)
    if not isinstance(tag, dict):
        raise ValueError("query_tag must be a JSON object")
    encoded = json.dumps(tag, separators=(",", ":"), ensure_ascii=True)
    return "/* " + encoded.replace("*/", "*\\u002f").replace("/*", "\\u002f*") + " */ "


def account_rows_sql(config, snapshot_date, search=""):
    sql = f"SELECT {', '.join(COLUMNS)} FROM {table_name(config)} WHERE snapshot_date = TO_DATE(?)"
    params = [snapshot_date]
    if search:
        sql += " AND (CONTAINS(LOWER(account_id), LOWER(?)) OR CONTAINS(LOWER(account_email), LOWER(?)))"
        params.extend([search, search])
    return f"{sql} {ORDER_BY}", params


def close_to_limit_sql(config, snapshot_date):
    return (
        f"SELECT {', '.join(COLUMNS)} FROM {table_name(config)} "
        f"WHERE snapshot_date = TO_DATE(?) AND {CLOSE_TO_LIMIT} {ORDER_BY}",
        [snapshot_date],
    )


def snapshot_dates_sql(config):
    return f"SELECT DISTINCT snapshot_date FROM {table_name(config)} ORDER BY snapshot_date DESC", []


def trend_sql(config, snapshot_date):
    return (
        f"SELECT snapshot_date, COUNT(*) AS account_count, "
        f"COUNT(CASE WHEN {CLOSE_TO_LIMIT} THEN 1 END) AS accounts_close_to_limit, "
        "SUM(used_bytes) AS used_bytes, SUM(quota_bytes) AS quota_bytes, "
        "ROUND(SUM(used_bytes) / NULLIF(SUM(quota_bytes), 0) * 100, 2) AS usage_pct "
        f"FROM {table_name(config)} WHERE {WINDOW} GROUP BY snapshot_date ORDER BY snapshot_date",
        [snapshot_date, snapshot_date],
    )


def account_history_sql(config, snapshot_date, account_id):
    return (
        f"SELECT snapshot_date, usage_pct FROM {table_name(config)} "
        f"WHERE {WINDOW} AND account_id = ? ORDER BY snapshot_date",
        [snapshot_date, snapshot_date, account_id],
    )
