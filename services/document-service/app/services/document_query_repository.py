"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly.

Every caller-supplied value is sent as a bound parameter, and ``ORDER BY`` is
resolved from an allow-list, so no caller text is ever part of the SQL string.
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

SORTABLE_COLUMNS = frozenset(COLUMNS)
SORT_DIRECTIONS = {"asc": "ASC", "desc": "DESC"}
LIKE_ESCAPE = "\\"


class InvalidOrderingError(ValueError):
    """Raised when a caller asks to sort by an unknown column or direction."""


def _escape_like(value: str) -> str:
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def _order_by(sort: str, direction: str) -> str:
    if sort not in SORTABLE_COLUMNS:
        raise InvalidOrderingError(f"Unsupported sort column: {sort!r}")
    sql_direction = SORT_DIRECTIONS.get(direction.lower())
    if sql_direction is None:
        raise InvalidOrderingError(f"Unsupported sort direction: {direction!r}")
    return f"{sort} {sql_direction}"


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
            params["owner_id"] = str(owner_id)
        if folder_id:
            clauses.append("folder_id = :folder_id")
            params["folder_id"] = str(folder_id)
        if title_contains:
            clauses.append(
                "lower(title) LIKE lower(:title_pattern) ESCAPE :like_escape"
            )
            params["title_pattern"] = f"%{_escape_like(title_contains)}%"
            params["like_escape"] = LIKE_ESCAPE
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
        # Only fixed SQL fragments are concatenated; caller values are bound.
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        stmt = text("SELECT count(*) FROM documents WHERE " + where)
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
        order_by = _order_by(sort, direction)
        where, params = self._where(owner_id, title_contains, content_type, folder_id)
        params["limit"] = int(limit)
        params["offset"] = int(offset)
        logger.debug("document_filter_query", sort=sort, direction=direction)
        # Only fixed SQL fragments and allow-listed identifiers are concatenated;
        # caller values are bound.
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        stmt = text(
            f"SELECT {', '.join(COLUMNS)} FROM documents WHERE {where}"
            f" ORDER BY {order_by} LIMIT :limit OFFSET :offset"
        )
        result = await self.db.execute(stmt, params)
        return [dict(row._mapping) for row in result]
