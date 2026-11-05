"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly. Every caller value is
bound as a query parameter; ordering is resolved from a fixed allow-list.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import BindParameter, Uuid, bindparam, text
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

SORT_COLUMNS = frozenset({"title", "created_at", "updated_at", "word_count"})
SORT_DIRECTIONS = frozenset({"asc", "desc"})


class InvalidSortError(ValueError):
    """Raised when the caller asks for an ordering outside the allow-list."""


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def resolve_order_by(sort: str, direction: str) -> str:
    """Map a caller-chosen sort onto a fixed ORDER BY clause."""
    column = sort.lower() if isinstance(sort, str) else ""
    order = direction.lower() if isinstance(direction, str) else ""
    if column not in SORT_COLUMNS or order not in SORT_DIRECTIONS:
        raise InvalidSortError("Invalid sort")
    return f"{column} {order}"


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
    ) -> tuple[str, list[BindParameter[Any]]]:
        clauses = ["is_deleted = false", "is_template = false"]
        params: list[BindParameter[Any]] = []
        if owner_id:
            clauses.append("owner_id = :owner_id")
            params.append(bindparam("owner_id", UUID(str(owner_id)), type_=Uuid))
        if folder_id:
            clauses.append("folder_id = :folder_id")
            params.append(bindparam("folder_id", UUID(str(folder_id)), type_=Uuid))
        if title_contains:
            clauses.append("lower(title) LIKE lower(:title_pattern) ESCAPE '\\'")
            params.append(
                bindparam("title_pattern", f"%{_escape_like(title_contains)}%")
            )
        if content_type:
            clauses.append("content_type = :content_type")
            params.append(bindparam("content_type", content_type))
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
        # Only fixed predicate text is formatted in; every value is a bound parameter.
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        statement = text(f"SELECT count(*) FROM documents WHERE {where}")
        result = await self.db.execute(statement.bindparams(*params))
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
        order_by = resolve_order_by(sort, direction)
        where, params = self._where(owner_id, title_contains, content_type, folder_id)
        params.append(bindparam("limit", int(limit)))
        params.append(bindparam("offset", int(offset)))
        # Only fixed predicate text and the allow-listed ORDER BY are formatted in.
        # nosemgrep: python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text
        statement = text(
            f"SELECT {', '.join(COLUMNS)} FROM documents WHERE {where}"
            f" ORDER BY {order_by} LIMIT :limit OFFSET :offset"
        )
        logger.debug("document_filter_query", sort=sort, direction=direction)
        result = await self.db.execute(statement.bindparams(*params))
        return [dict(row._mapping) for row in result]
