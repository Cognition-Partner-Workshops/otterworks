"""Amazon OpenSearch (Serverless) client for full-text search operations.

Sibling adapter to :class:`app.services.meilisearch_client.MeiliSearchService`.
It implements the identical public surface so the API layer is a pure
adapter-behind-a-config-flip: selecting ``SEARCH_BACKEND=opensearch`` points
the same endpoints at an Amazon OpenSearch Serverless SEARCH collection with no
change to callers or response contracts.

Parity notes:
- MeiliSearch is prefix-first (type-ahead out of the box). A plain OpenSearch
  ``match`` query is not, so the ``/suggest`` path maps to
  ``search_as_you_type`` fields queried with a ``bool_prefix`` multi_match
  (equivalent to ``match_phrase_prefix``) to preserve type-ahead behaviour.
- ``score`` / ``highlights`` / ``content_snippet`` mirror the MeiliSearch
  adapter so response bodies validate against shared/openapi/search-service.yaml.
"""

from __future__ import annotations

from typing import Any

import structlog
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy import exceptions as os_exceptions
from opensearchpy.helpers import bulk

from app.config import OpenSearchConfig
from app.models.search_result import SearchHit, SearchResponse
from app.services.analytics import get_search_analytics, record_search_analytics

logger = structlog.get_logger()

__all__ = [
    "OpenSearchService",
    "get_search_analytics",
    "record_search_analytics",
]

# Highlight tags kept identical to the MeiliSearch adapter.
_HL_PRE = "<em>"
_HL_POST = "</em>"


class OpenSearchService:
    """Client for Amazon OpenSearch (Serverless) search and indexing.

    Public methods mirror :class:`MeiliSearchService` exactly.
    """

    def __init__(self, config: OpenSearchConfig) -> None:
        self.config = config
        self.documents_index_name = config.documents_index
        self.files_index_name = config.files_index
        # OpenSearch Serverless (service "aoss") is eventually consistent and
        # rejects the refresh parameter; a self-managed cluster accepts it.
        self._serverless = config.service == "aoss"
        self.client = self._build_client(config)

    @staticmethod
    def _build_client(config: OpenSearchConfig) -> OpenSearch:
        endpoint = config.endpoint
        use_ssl = endpoint.startswith("https")
        host = endpoint.replace("https://", "").replace("http://", "")
        port = 443 if use_ssl else 9200
        if ":" in host:
            host, port_str = host.split(":", 1)
            port = int(port_str)

        http_auth = None
        if config.use_aws_auth:
            # Lazily import so local/no-auth runs don't require botocore SigV4.
            import boto3
            from opensearchpy import AWSV4SignerAuth

            credentials = boto3.Session().get_credentials()
            http_auth = AWSV4SignerAuth(credentials, config.region, config.service)

        return OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=http_auth,
            use_ssl=use_ssl,
            verify_certs=use_ssl,
            connection_class=RequestsHttpConnection,
            pool_maxsize=20,
        )

    # --- index lifecycle -----------------------------------------------------

    @staticmethod
    def _documents_mapping() -> dict[str, Any]:
        return {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "title": {
                        "type": "text",
                        "fields": {"suggest": {"type": "search_as_you_type"}},
                    },
                    "content": {"type": "text"},
                    "tags": {"type": "keyword"},
                    "type": {"type": "keyword"},
                    "owner_id": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                }
            }
        }

    @staticmethod
    def _files_mapping() -> dict[str, Any]:
        return {
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {
                        "type": "text",
                        "fields": {"suggest": {"type": "search_as_you_type"}},
                    },
                    "mime_type": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                    "type": {"type": "keyword"},
                    "owner_id": {"type": "keyword"},
                    "folder_id": {"type": "keyword"},
                    "size": {"type": "long"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                }
            }
        }

    def ensure_indices(self) -> None:
        """Create indices with mappings if they don't already exist."""
        specs = {
            self.documents_index_name: self._documents_mapping(),
            self.files_index_name: self._files_mapping(),
        }
        for index_name, body in specs.items():
            if not self.client.indices.exists(index=index_name):
                self.client.indices.create(index=index_name, body=body)
                logger.info("opensearch_index_created", index=index_name)
        logger.info("opensearch_indices_configured")

    def ping(self) -> bool:
        """Check if OpenSearch is reachable."""
        try:
            # AOSS does not expose the cluster ping/health API; a lightweight
            # indices.exists call works across both serverless and managed.
            self.client.indices.exists(index=self.documents_index_name)
            return True
        except Exception:
            return False

    # --- search --------------------------------------------------------------

    def _refresh_kwargs(self) -> dict[str, Any]:
        return {} if self._serverless else {"refresh": "wait_for"}

    def _build_query(self, query: str | None, filter_parts: list[dict[str, Any]]) -> dict[str, Any]:
        if query:
            must: dict[str, Any] = {
                "multi_match": {
                    "query": query,
                    "fields": ["title", "content", "tags", "name", "mime_type"],
                    "type": "best_fields",
                }
            }
        else:
            must = {"match_all": {}}
        return {"bool": {"must": [must], "filter": filter_parts}}

    def _paginate(self, page: int, page_size: int, multi_index: bool) -> tuple[int, int]:
        if multi_index:
            return 0, page * page_size
        return (page - 1) * page_size, page_size

    def _run_search(
        self,
        query: str | None,
        filter_parts: list[dict[str, Any]],
        indices: list[str],
        page: int,
        page_size: int,
    ) -> tuple[list[SearchHit], int]:
        multi_index = len(indices) > 1
        from_, size = self._paginate(page, page_size, multi_index)
        body = {
            "query": self._build_query(query, filter_parts),
            "from": from_,
            "size": size,
            "highlight": {
                "pre_tags": [_HL_PRE],
                "post_tags": [_HL_POST],
                "fields": {
                    "title": {},
                    "name": {},
                    "content": {"fragment_size": 200, "number_of_fragments": 1},
                },
            },
        }

        all_hits: list[SearchHit] = []
        total = 0
        for index_name in indices:
            try:
                result = self.client.search(index=index_name, body=body)
            except os_exceptions.RequestError as exc:
                logger.warning("search_query_error", index=index_name, error=str(exc))
                raise ValueError(f"Invalid search filter: {exc}") from exc
            total += result["hits"]["total"]["value"]
            for hit in result["hits"]["hits"]:
                all_hits.append(self._parse_hit(hit, index_name))
        return all_hits, total

    def search(
        self,
        query: str,
        doc_type: str | None = None,
        owner_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SearchResponse:
        """Full-text search across documents and files."""
        filter_parts: list[dict[str, Any]] = []
        if doc_type:
            filter_parts.append({"term": {"type": doc_type}})
        if owner_id:
            filter_parts.append({"term": {"owner_id": owner_id}})

        indices = self._resolve_indices(doc_type)
        all_hits, total = self._run_search(query, filter_parts, indices, page, page_size)

        record_search_analytics(query, total)

        start = (page - 1) * page_size if len(indices) > 1 else 0
        page_hits = all_hits[start : start + page_size]

        return SearchResponse(
            results=page_hits,
            total=total,
            page=page,
            page_size=page_size,
            query=query,
        )

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
    ) -> SearchResponse:
        """Advanced search with detailed filters."""
        filter_parts: list[dict[str, Any]] = []
        if doc_type:
            filter_parts.append({"term": {"type": doc_type}})
        if owner_id:
            filter_parts.append({"term": {"owner_id": owner_id}})
        if tags:
            filter_parts.append({"terms": {"tags": tags}})
        date_range: dict[str, str] = {}
        if date_from:
            date_range["gte"] = date_from
        if date_to:
            date_range["lte"] = date_to
        if date_range:
            filter_parts.append({"range": {"created_at": date_range}})

        search_term = query or ""
        indices = self._resolve_indices(doc_type)
        all_hits, total = self._run_search(query, filter_parts, indices, page, page_size)

        record_search_analytics(search_term or "*", total)

        start = (page - 1) * page_size if len(indices) > 1 else 0
        page_hits = all_hits[start : start + page_size]

        return SearchResponse(
            results=page_hits,
            total=total,
            page=page,
            page_size=page_size,
            query=search_term or "*",
        )

    def suggest(self, prefix: str, size: int = 10) -> list[str]:
        """Autocomplete suggestions using prefix (type-ahead) matching.

        Uses ``search_as_you_type`` fields with a ``bool_prefix`` query so the
        last term is prefix-matched, preserving MeiliSearch's prefix-first
        type-ahead semantics (a plain ``match`` query would not).
        """
        suggestions: list[str] = []
        seen: set[str] = set()

        index_fields = [
            (self.documents_index_name, "title"),
            (self.files_index_name, "name"),
        ]
        for index_name, field in index_fields:
            body = {
                "size": size,
                "_source": [field],
                "query": {
                    "multi_match": {
                        "query": prefix,
                        "type": "bool_prefix",
                        "fields": [
                            f"{field}.suggest",
                            f"{field}.suggest._2gram",
                            f"{field}.suggest._3gram",
                        ],
                    }
                },
            }
            try:
                result = self.client.search(index=index_name, body=body)
            except os_exceptions.OpenSearchException:
                continue
            for hit in result["hits"]["hits"]:
                text = hit["_source"].get(field, "")
                if text and text not in seen:
                    suggestions.append(text)
                    seen.add(text)
                    if len(suggestions) >= size:
                        break
            if len(suggestions) >= size:
                break

        return suggestions

    # --- indexing ------------------------------------------------------------

    def index_document(self, document: dict[str, Any]) -> None:
        """Index or update a document."""
        doc = {**document, "type": "document"}
        self.client.index(
            index=self.documents_index_name,
            id=doc["id"],
            body=doc,
            **self._refresh_kwargs(),
        )
        logger.info("document_indexed", document_id=doc.get("id"))

    def index_file(self, file_data: dict[str, Any]) -> None:
        """Index or update a file."""
        doc = {**file_data, "type": "file"}
        self.client.index(
            index=self.files_index_name,
            id=doc["id"],
            body=doc,
            **self._refresh_kwargs(),
        )
        logger.info("file_indexed", file_id=doc.get("id"))

    def _exists(self, index_name: str, doc_id: str) -> bool:
        """Check document existence via a term search (works on serverless)."""
        result = self.client.search(
            index=index_name,
            body={"query": {"term": {"id": doc_id}}, "size": 0},
        )
        return result["hits"]["total"]["value"] > 0

    def delete_document(self, doc_type: str, doc_id: str) -> bool:
        """Remove a document or file from the index. Returns False if not found."""
        index_name = self.documents_index_name if doc_type == "document" else self.files_index_name
        if not self._exists(index_name, doc_id):
            logger.warning("document_not_found_in_index", doc_id=doc_id, index=index_name)
            return False
        try:
            self.client.delete(index=index_name, id=doc_id, **self._refresh_kwargs())
        except os_exceptions.NotFoundError:
            logger.warning("document_not_found_in_index", doc_id=doc_id, index=index_name)
            return False
        logger.info("document_removed_from_index", doc_id=doc_id, index=index_name)
        return True

    def reindex(
        self,
        documents: list[dict[str, Any]] | None = None,
        files: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Delete indices, recreate them, and optionally repopulate."""
        for index_name in [self.documents_index_name, self.files_index_name]:
            try:
                self.client.indices.delete(index=index_name)
                logger.info("opensearch_index_deleted", index=index_name)
            except os_exceptions.NotFoundError:
                pass
        self.ensure_indices()

        indexed_counts: dict[str, int] = {"documents": 0, "files": 0}
        if documents:
            self._bulk_index(self.documents_index_name, documents, "document")
            indexed_counts["documents"] = len(documents)
        if files:
            self._bulk_index(self.files_index_name, files, "file")
            indexed_counts["files"] = len(files)

        return {
            "status": "reindexed",
            "indices": [self.documents_index_name, self.files_index_name],
            "indexed_counts": indexed_counts,
        }

    def _bulk_index(self, index_name: str, docs: list[dict[str, Any]], doc_type: str) -> None:
        actions = [
            {
                "_index": index_name,
                "_id": doc.get("id"),
                "_source": {**doc, "type": doc.get("type", doc_type)},
            }
            for doc in docs
        ]
        bulk(self.client, actions, **self._refresh_kwargs())

    # --- helpers -------------------------------------------------------------

    def _resolve_indices(self, doc_type: str | None) -> list[str]:
        """Determine which indices to search based on type filter."""
        if doc_type == "document":
            return [self.documents_index_name]
        if doc_type == "file":
            return [self.files_index_name]
        return [self.documents_index_name, self.files_index_name]

    def _parse_hit(self, hit: dict[str, Any], index_name: str) -> SearchHit:
        """Convert an OpenSearch hit to a SearchHit model."""
        source = hit.get("_source", {})
        highlight = hit.get("highlight", {})
        highlights: dict[str, list[str]] = {}
        for field in ["title", "name", "content"]:
            if field in highlight:
                highlights[field] = [str(frag) for frag in highlight[field]]

        is_doc = index_name == self.documents_index_name
        content_snippet = ""
        if is_doc:
            if highlight.get("content"):
                content_snippet = str(highlight["content"][0])[:200]
            else:
                content_snippet = str(source.get("content", ""))[:200]

        return SearchHit(
            id=source.get("id", hit.get("_id", "")),
            title=source.get("title", "") if is_doc else source.get("name", ""),
            content_snippet=content_snippet,
            type=source.get("type", "document" if is_doc else "file"),
            owner_id=source.get("owner_id", ""),
            tags=source.get("tags", []),
            score=round(float(hit.get("_score") or 0.0), 4),
            highlights=highlights,
            created_at=source.get("created_at"),
            updated_at=source.get("updated_at"),
            mime_type=source.get("mime_type"),
            folder_id=source.get("folder_id"),
            size=source.get("size"),
        )
