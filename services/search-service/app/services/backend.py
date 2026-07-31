"""Shared interface for interchangeable search backends.

Both :class:`app.services.meilisearch_client.MeiliSearchService` and
:class:`app.services.opensearch_client.OpenSearchService` satisfy this
Protocol, so the API layer and indexer depend only on the contract — the
concrete backend is chosen at startup by ``SEARCH_BACKEND``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.models.search_result import SearchResponse


@runtime_checkable
class SearchBackend(Protocol):
    """Behaviour every search backend adapter must provide."""

    def ensure_indices(self) -> None: ...

    def ping(self) -> bool: ...

    def search(
        self,
        query: str,
        doc_type: str | None = None,
        owner_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResponse: ...

    def advanced_search(
        self,
        query: str | None = None,
        doc_type: str | None = None,
        owner_id: str | None = None,
        tags: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResponse: ...

    def suggest(self, prefix: str, size: int = 10) -> list[str]: ...

    def index_document(self, document: dict[str, Any]) -> None: ...

    def index_file(self, file_data: dict[str, Any]) -> None: ...

    def delete_document(self, doc_type: str, doc_id: str) -> bool: ...

    def reindex(
        self,
        documents: list[dict[str, Any]] | None = None,
        files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]: ...
