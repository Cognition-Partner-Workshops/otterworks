"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly.

The statements are built with SQLAlchemy Core so every caller-supplied value
is bound as a query parameter, and the ORDER BY clause is resolved from an
allow-list of column names and directions; no request input ever reaches the
SQL text.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import ColumnElement, column, false, func, select, table
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
SORT_DIRECTIONS = ("asc", "desc")

# Untyped so rows come back exactly as the driver returns them.
DOCUMENTS = table("documents", *(column(name) for name in COLUMNS))


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
            DOCUMENTS.c.is_deleted == false(),
            DOCUMENTS.c.is_template == false(),
        ]
        if owner_id:
            clauses.append(DOCUMENTS.c.owner_id == owner_id)
        if folder_id:
            clauses.append(DOCUMENTS.c.folder_id == folder_id)
        if title_contains:
            clauses.append(func.lower(DOCUMENTS.c.title).like(func.lower(f"%{title_contains}%")))
        if content_type:
            clauses.append(DOCUMENTS.c.content_type == content_type)
        return clauses

    @staticmethod
    def _order_by(sort: str, direction: str) -> ColumnElement[Any]:
        if sort not in SORTABLE_COLUMNS:
            raise ValueError(f"unsupported sort column: {sort!r}")
        normalized_direction = str(direction).lower()
        if normalized_direction not in SORT_DIRECTIONS:
            raise ValueError(f"unsupported sort direction: {direction!r}")
        sort_column = DOCUMENTS.c[sort]
        return sort_column.asc() if normalized_direction == "asc" else sort_column.desc()

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
            .select_from(DOCUMENTS)
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
        """Return document rows matching the metadata filters, newest first."""
        stmt = (
            select(*DOCUMENTS.c)
            .where(*self._where(owner_id, title_contains, content_type, folder_id))
            .order_by(self._order_by(sort, direction))
            .limit(int(limit))
            .offset(int(offset))
        )
        logger.debug("document_filter_query", sort=sort, direction=direction)
        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result]
