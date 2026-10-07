"""Weekly search reindex (replaces etl/scripts/search_reindex_weekly.py, cron Sundays 04:00 UTC).

``clear_indices`` deletes and recreates the MeiliSearch ``documents`` and ``files`` indices
(primary key ``id``, legacy settings); ``fetch_and_index_documents`` and
``fetch_and_index_files`` page through document-service and file-service and add the mapped
records in bulk; ``validate_indices`` fails the run when an index's document count differs
from the number of records fetched for it. Every call goes through ``HttpHook`` and the
``otterworks_meilisearch`` / ``otterworks_document_service`` / ``otterworks_file_service``
Connections. Only index names and counts go through XCom; nothing is staged.

Parity choices pinned by the goldens (etl/tests/golden/search_reindex_weekly), kept as
follow-ups: the count check uses fetched records, not unique ids, so duplicate ids fail the
run; a failed add-documents task only logs a warning, so one bad id drops its whole batch; the
reindex is not atomic, so an upstream 5xx mid-run leaves the indices partly filled; the
mapping defaults (``null`` / ``""`` / ``[]`` / ``0``) stay as they are. A missing index on
delete is the expected first-run case and logs at INFO.

Retries: a retried fetch task recreates its index and starts again from page 1, so a
persistent failure ends in the same state as legacy. Retry delays are short (1 then 2
minutes) because search is degraded from ``clear_indices`` until the run finishes.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import pendulum
from airflow.decorators import dag, task
from airflow.exceptions import AirflowFailException
from airflow.models import Variable

from otterworks_etl.common import LEGACY_SCHEDULES, get_logger, log_event, otterworks_dag_kwargs
from otterworks_etl.search_reindex import (
    DOCUMENTS,
    FILES,
    SOURCES,
    VARIABLES,
    MeiliSearch,
    ReindexConfig,
    Source,
    count_mismatches,
    index_source,
    parse_config,
    recreate_index,
)

DAG_ID = "otterworks_search_reindex"
MEILISEARCH_CONN_ID = "otterworks_meilisearch"

logger = get_logger(__name__)


def _config() -> ReindexConfig:
    try:
        return parse_config({key: Variable.get(key) for key in VARIABLES})
    except ValueError as exc:
        raise AirflowFailException(str(exc)) from exc


@dag(
    dag_id=DAG_ID,
    schedule=LEGACY_SCHEDULES[DAG_ID],
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    doc_md=__doc__,
    **otterworks_dag_kwargs(
        tags=["search", "meilisearch"],
        default_args={
            "retry_delay": timedelta(minutes=1),
            "max_retry_delay": timedelta(minutes=2),
        },
    ),
)
def otterworks_search_reindex():
    @task
    def clear_indices() -> dict[str, str]:
        config = _config()
        meili = MeiliSearch(MEILISEARCH_CONN_ID)
        for source in SOURCES:
            recreate_index(meili, config.indices[source.name], source.settings, config.task_timeout)
        return config.indices

    def fetch_and_index(source: Source, indices: dict[str, str], ti: Any) -> dict[str, Any]:
        config = _config()
        index = indices[source.name]
        meili = MeiliSearch(MEILISEARCH_CONN_ID)
        if ti.try_number > 1:
            recreate_index(meili, index, source.settings, config.task_timeout)
        result = index_source(meili, source, index, config)
        log_event(logger, "source_indexed", source=source.name, **result)
        return result

    @task
    def fetch_and_index_documents(indices: dict[str, str], **context) -> dict[str, Any]:
        return fetch_and_index(DOCUMENTS, indices, context["ti"])

    @task
    def fetch_and_index_files(indices: dict[str, str], **context) -> dict[str, Any]:
        return fetch_and_index(FILES, indices, context["ti"])

    @task
    def validate_indices(documents: dict[str, Any], files: dict[str, Any]) -> dict[str, int]:
        meili = MeiliSearch(MEILISEARCH_CONN_ID)
        expected = {r["index"]: r["fetched"] for r in (documents, files)}
        actual = {index: meili.number_of_documents(index) for index in expected}
        problems = count_mismatches(expected, actual)
        log_event(
            logger,
            "index_counts",
            logging.ERROR if problems else logging.INFO,
            expected=expected,
            actual=actual,
        )
        if problems:
            raise AirflowFailException("search index validation failed: " + "; ".join(problems))
        return actual

    indices = clear_indices()
    validate_indices(fetch_and_index_documents(indices), fetch_and_index_files(indices))


otterworks_search_reindex()
