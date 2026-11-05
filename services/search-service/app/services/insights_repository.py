"""Repository for per-account search insights."""

from __future__ import annotations

import os
from datetime import date
from typing import Any

from app.config import SnowflakeConfig
from app.services.snowflake_pool import SnowflakeConnectionPool
from app.vendor import sf_attribution as attr


def build_connection_params(config: SnowflakeConfig) -> dict[str, Any]:
    """Build the only supported endpoint connection arguments through attribution."""
    config.validate()
    os.environ.pop("SNOWFLAKE_HOST", None)
    endpoint = attr.Endpoint.from_csid("cs_doc_search_api_top_items", "doc_search_api")
    options: dict[str, Any] = {
        "account": config.account,
        "private_key_file": config.private_key_file,
        "phase": config.query_phase,
        "commit": config.deployed_commit,
        "run_id": attr.make_run_id("doc_search_api", config.query_phase),
        "role": config.role,
    }
    if config.query_phase == "dev":
        options["session_url"] = config.session_url
    if config.private_key_file_pwd:
        options["private_key_file_pwd"] = config.private_key_file_pwd
    params = attr.connection_params(endpoint, **options)
    params["login_timeout"] = config.login_timeout
    params["network_timeout"] = config.network_timeout
    params.setdefault("session_parameters", {})["STATEMENT_TIMEOUT_IN_SECONDS"] = config.query_timeout
    return params


class DocSearchInsightsRepository:
    """Loads top search terms and documents from the attributed output table."""

    def __init__(self, pool: SnowflakeConnectionPool) -> None:
        self.pool = pool

    @classmethod
    def from_config(cls, config: SnowflakeConfig) -> DocSearchInsightsRepository:
        pool = SnowflakeConnectionPool(
            size=config.pool_size,
            connection_params=build_connection_params(config),
            query_timeout=config.query_timeout,
            max_retries=config.max_retries,
            backoff_base=config.backoff_base,
            backoff_max=config.backoff_max,
        )
        return cls(pool)

    def top_items(self, account_id: str, window_end_date: date | None) -> list[dict[str, Any]] | None:
        table = attr.output_table_name("doc_search_api")
        sql = f"""select window_end_date, window_days, account_id, item_type, rank, term, document_id, document_title,
          search_count, zero_result_count, last_searched_at
   from {table}
  where account_id = %(account_id)s
    and window_end_date = coalesce(%(window_end_date)s::date,
        (select max(window_end_date) from {table} where account_id = %(account_id)s))
  order by item_type, rank"""
        rows = self.pool.run_query(
            sql,
            {"account_id": account_id, "window_end_date": window_end_date},
        )
        return rows or None
