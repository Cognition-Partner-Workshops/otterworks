"""Upstream paging and indexing for the otterworks_search_reindex DAG, over ``HttpHook``."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from airflow.providers.http.hooks.http import HttpHook

from otterworks_etl.common.log import get_logger, log_event
from otterworks_etl.search_reindex.mapping import (
    DOCUMENT_SETTINGS,
    FILE_SETTINGS,
    batches,
    is_last_page,
    map_document,
    map_file,
    page_items,
)
from otterworks_etl.search_reindex.meilisearch import MeiliSearch, submit, task_error

logger = get_logger(__name__)


@dataclass(frozen=True)
class Source:
    """One upstream service and the index it feeds."""

    name: str
    conn_id: str
    endpoint: str
    page_size_param: str
    items_key: str
    index_variable: str
    mapper: Callable[[Mapping[str, Any]], dict[str, Any]]
    settings: Mapping[str, list[str]]


DOCUMENTS = Source(
    name="documents",
    conn_id="otterworks_document_service",
    endpoint="api/v1/documents",
    page_size_param="size",
    items_key="documents",
    index_variable="search_reindex_documents_index",
    mapper=map_document,
    settings=DOCUMENT_SETTINGS,
)
FILES = Source(
    name="files",
    conn_id="otterworks_file_service",
    endpoint="api/v1/files",
    page_size_param="page_size",
    items_key="files",
    index_variable="search_reindex_files_index",
    mapper=map_file,
    settings=FILE_SETTINGS,
)
SOURCES = (DOCUMENTS, FILES)

INT_VARIABLES = {
    "api_page_size": "search_reindex_api_page_size",
    "bulk_batch_size": "search_reindex_bulk_batch_size",
}
# document-service rejects size > 100 (422); file-service caps page_size at 100, which would
# look like a short last page and stop paging early.
MAX_API_PAGE_SIZE = 100
TIMEOUT_VARIABLES = {
    "task_timeout": "search_reindex_task_timeout_seconds",
    "bulk_task_timeout": "search_reindex_bulk_task_timeout_seconds",
}
VARIABLES = (
    *(s.index_variable for s in SOURCES),
    *INT_VARIABLES.values(),
    *TIMEOUT_VARIABLES.values(),
)


@dataclass(frozen=True)
class ReindexConfig:
    indices: dict[str, str]
    api_page_size: int
    bulk_batch_size: int
    task_timeout: float
    bulk_task_timeout: float


def parse_config(values: Mapping[str, str]) -> ReindexConfig:
    """Validate the ``search_reindex_*`` Variables (``values`` maps Variable key to value)."""
    indices = {s.name: str(values[s.index_variable]).strip() for s in SOURCES}
    if not all(indices.values()) or len(set(indices.values())) != len(indices):
        raise ValueError(f"index names must be non-empty and distinct, got {indices}")
    numbers: dict[str, Any] = {}
    for field, key in INT_VARIABLES.items():
        numbers[field] = _number(key, values[key], int)
    for field, key in TIMEOUT_VARIABLES.items():
        numbers[field] = _number(key, values[key], float)
    if numbers["api_page_size"] > MAX_API_PAGE_SIZE:
        raise ValueError(
            f"Variable {INT_VARIABLES['api_page_size']}={numbers['api_page_size']} "
            f"exceeds the upstream page limit {MAX_API_PAGE_SIZE}"
        )
    return ReindexConfig(indices=indices, **numbers)


def _number(key: str, raw: str, kind: type) -> Any:
    try:
        value = kind(raw)
    except (TypeError, ValueError):
        raise ValueError(f"Variable {key}={raw!r} is not a {kind.__name__}") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"Variable {key}={raw!r} must be a positive finite number")
    return value


def fetch_pages(source: Source, page_size: int) -> Iterator[list[dict[str, Any]]]:
    """Yield the upstream's pages from page 1 until an empty or short page.

    An HTTP error on any page raises AirflowException; pages already yielded stay indexed.
    """
    hook = HttpHook(method="GET", http_conn_id=source.conn_id)
    page = 1
    while True:
        params = {"page": page, source.page_size_param: page_size}
        items = page_items(hook.run(source.endpoint, data=params).json(), source.items_key)
        if not items:
            return
        yield items
        if is_last_page(items, page_size):
            return
        page += 1


def index_source(
    meili: MeiliSearch, source: Source, index: str, config: ReindexConfig
) -> dict[str, Any]:
    """Fetch every page of ``source``, map it and add it to ``index`` in bulk batches.

    As in legacy, a failed add-documents task is logged and skipped (its whole batch is
    dropped), and ``fetched`` counts the records fetched, not the unique ids.
    """
    fetched = pages = sent = failed = 0
    for items in fetch_pages(source, config.api_page_size):
        pages += 1
        records = [source.mapper(item) for item in items]
        for batch in batches(records, config.bulk_batch_size):
            sent += 1
            endpoint = f"indexes/{index}/documents"
            task = submit(meili, "POST", endpoint, batch, config.bulk_task_timeout)
            if task.get("status") != "succeeded":
                failed += 1
                log_event(
                    logger,
                    "index_batch_failed",
                    logging.WARNING,
                    index=index,
                    page=pages,
                    records=len(batch),
                    task_uid=task.get("uid"),
                    status=task.get("status"),
                    error=task_error(task),
                )
        fetched += len(items)
    return {
        "index": index,
        "fetched": fetched,
        "pages": pages,
        "batches": sent,
        "failed_batches": failed,
    }
