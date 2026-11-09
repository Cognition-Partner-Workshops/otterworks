"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import ColumnElement, column, func, select, table
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
    {"title", "content_type", "word_count", "version", "created_at", "updated_at"}
)
DIRECTIONS = frozenset({"asc", "desc"})

documents = table("documents", *(column(name) for name in COLUMNS))


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
    ) -> list[ColumnElement[bool]]:
        clauses: list[ColumnElement[bool]] = [
            documents.c.is_deleted.is_(False),
            documents.c.is_template.is_(False),
        ]
        if owner_id:
            clauses.append(documents.c.owner_id == owner_id)
        if folder_id:
            clauses.append(documents.c.folder_id == folder_id)
        if title_contains:
            clauses.append(func.lower(documents.c.title).like(func.lower(f"%{title_contains}%")))
        if content_type:
            clauses.append(documents.c.content_type == content_type)
        return clauses

    @staticmethod
    def _order_by(sort: str, direction: str) -> ColumnElement[Any]:
        if sort not in SORTABLE_COLUMNS:
            raise ValueError(f"Unsupported sort column: {sort!r}")
        if direction.lower() not in DIRECTIONS:
            raise ValueError(f"Unsupported sort direction: {direction!r}")
        sort_column = documents.c[sort]
        return sort_column.asc() if direction.lower() == "asc" else sort_column.desc()

    async def count_documents(
        self,
        *,
        owner_id: str | None = None,
        title_contains: str | None = None,
        content_type: str | None = None,
        folder_id: str | None = None,
    ) -> int:
        """Count documents matching the metadata filters."""
        stmt = (
            select(func.count())
            .select_from(documents)
            .where(*self._where(owner_id, title_contains, content_type, folder_id))
        )
        result = await self.db.execute(stmt)
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
        """Return document rows matching the metadata filters, newest first.

        ``sort`` and ``direction`` are resolved against an allow-list; every
        caller-supplied value is sent as a bound parameter.
        """
        stmt = (
            select(*documents.c)
            .where(*self._where(owner_id, title_contains, content_type, folder_id))
            .order_by(self._order_by(sort, direction))
            .limit(limit)
            .offset(offset)
        )
        logger.debug("document_filter_query", sort=sort, direction=direction)
        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result]
