"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly.

Every caller-supplied value is bound as a query parameter, and the ORDER BY
column and direction are resolved from fixed allowlists, so no request value
ever becomes part of the SQL text.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

COLUMNS = (
    "id",
    "title",
    "content",
    "content_type",
    "owner_id",
    "folder_id",
    "is_deleted",
    "is_template",
    "word_count",
    "version",
    "created_at",
    "updated_at",
)

SORTABLE_COLUMNS = frozenset(
    {
        "id",
        "title",
        "content_type",
        "owner_id",
        "folder_id",
        "word_count",
        "version",
        "created_at",
        "updated_at",
    }
)

DIRECTIONS = frozenset({"asc", "desc"})


class InvalidSortError(ValueError):
    """The requested sort column or direction is not in the allowlist."""


def resolve_order_by(sort: str, direction: str) -> tuple[str, str]:
    """Map caller-supplied ``sort``/``direction`` onto allowlisted SQL fragments."""
    column = (sort or "").strip().lower()
    order = (direction or "").strip().lower()
    if column not in SORTABLE_COLUMNS or order not in DIRECTIONS:
        raise InvalidSortError(f"sort={sort!r} direction={direction!r}")
    return column, order


class DocumentQueryRepository:
    """Reads the document table for the list endpoint's metadata filters."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _where(
        self,
        owner_id: str | None,
        title_contains: str | None,
        content_type: str | None,
        folder_id: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        clauses = ["is_deleted = false", "is_template = false"]
        params: dict[str, Any] = {}
        if owner_id:
            clauses.append("owner_id = :owner_id")
            params["owner_id"] = owner_id
        if folder_id:
            clauses.append("folder_id = :folder_id")
            params["folder_id"] = folder_id
        if title_contains:
            clauses.append("lower(title) LIKE lower(:title_pattern)")
            params["title_pattern"] = f"%{title_contains}%"
        if content_type:
            clauses.append("content_type = :content_type")
            params["content_type"] = content_type
        return " AND ".join(clauses), params

    async def count_documents(
        self,
        *,
        owner_id: str | None = None,
        title_contains: str | None = None,
        content_type: str | None = None,
        folder_id: str | None = None,
    ) -> int:
        """Count documents matching the metadata filters."""
        where, params = self._where(owner_id, title_contains, content_type, folder_id)
        # `where` holds only fixed predicates with :named placeholders; caller values
        # travel in `params`.
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        stmt = text(f"SELECT count(*) FROM documents WHERE {where}")
        result = await self.db.execute(stmt, params)
        return int(result.scalar_one())

    async def search_documents(
        self,
        *,
        owner_id: str | None = None,
        title_contains: str | None = None,
        content_type: str | None = None,
        folder_id: str | None = None,
        sort: str = "updated_at",
        direction: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return document rows matching the metadata filters, newest first."""
        column, order = resolve_order_by(sort, direction)
        where, params = self._where(owner_id, title_contains, content_type, folder_id)
        # `column`/`order` come from SORTABLE_COLUMNS/DIRECTIONS, `where` from fixed
        # predicates; every caller value (filters, limit, offset) is bound in `params`.
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        stmt = text(
            f"SELECT {', '.join(COLUMNS)} FROM documents WHERE {where} "
            f"ORDER BY {column} {order} LIMIT :limit OFFSET :offset"
        )
        params["limit"] = int(limit)
        params["offset"] = int(offset)
        logger.debug("document_filter_query", sort=column, direction=order)
        result = await self.db.execute(stmt, params)
        return [dict(row._mapping) for row in result]
