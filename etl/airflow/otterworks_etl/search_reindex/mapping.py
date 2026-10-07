"""Pure parts of the search reindex: index settings, record mapping, paging and validation.

Everything here is pinned by the goldens in etl/tests/golden/search_reindex_weekly. The
mapping defaults (``None`` / ``""`` / ``[]`` / ``0``) are the legacy ones and stay as they are.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

PRIMARY_KEY = "id"

RANKING_RULES = ["words", "typo", "proximity", "attribute", "sort", "exactness"]

DOCUMENT_SETTINGS: dict[str, list[str]] = {
    "searchableAttributes": ["title", "content", "tags"],
    "filterableAttributes": ["type", "owner_id", "tags", "created_at", "updated_at"],
    "sortableAttributes": ["updated_at", "created_at"],
    "rankingRules": RANKING_RULES,
}

FILE_SETTINGS: dict[str, list[str]] = {
    "searchableAttributes": ["name", "tags", "mime_type"],
    "filterableAttributes": [
        "type",
        "owner_id",
        "mime_type",
        "folder_id",
        "tags",
        "created_at",
        "updated_at",
    ],
    "sortableAttributes": ["updated_at", "created_at", "size"],
    "rankingRules": RANKING_RULES,
}


def map_document(doc: Mapping[str, Any]) -> dict[str, Any]:
    """A document-service record as a ``documents`` index entry (legacy field fallbacks)."""
    return {
        "id": doc.get("document_id", doc.get("id", "")),
        "title": doc.get("title", ""),
        "content": doc.get("content", ""),
        "owner_id": doc.get("owner_id", ""),
        "tags": doc.get("tags", []),
        "type": "document",
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def map_file(f: Mapping[str, Any]) -> dict[str, Any]:
    """A file-service record as a ``files`` index entry (legacy field fallbacks)."""
    return {
        "id": f.get("file_id", f.get("id", "")),
        "name": f.get("file_name", f.get("name", "")),
        "owner_id": f.get("owner_id", ""),
        "mime_type": f.get("mime_type", ""),
        "folder_id": f.get("folder_id", ""),
        "size": f.get("size_bytes", f.get("size", 0)),
        "tags": f.get("tags", []),
        "type": "file",
        "created_at": f.get("created_at"),
        "updated_at": f.get("updated_at"),
    }


def page_items(payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
    """The records of one upstream page: ``payload[key]``, else ``payload["items"]``."""
    return list(payload.get(key, payload.get("items", [])) or [])


def is_last_page(items: Sequence[Any], page_size: int) -> bool:
    """Legacy paging: stop on an empty page or a page shorter than ``page_size``."""
    return len(items) < page_size


def batches(records: Sequence[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    if size < 1:
        raise ValueError(f"batch size must be at least 1, got {size}")
    for start in range(0, len(records), size):
        yield list(records[start : start + size])


def count_mismatches(expected: Mapping[str, int], actual: Mapping[str, int]) -> list[str]:
    """Indices whose document count differs from the number of records fetched for them.

    ``expected`` counts fetched records, not unique ids, as legacy does: duplicate ids
    upstream collapse in MeiliSearch and fail this check.
    """
    return [
        f"{index}: {actual.get(index, 0)} documents, expected {count}"
        for index, count in expected.items()
        if actual.get(index, 0) != count
    ]
