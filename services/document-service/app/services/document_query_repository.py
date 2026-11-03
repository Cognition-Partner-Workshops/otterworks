"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import ColumnElement, column, false, func, literal, select, table
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import NullType

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

SORT_DIRECTIONS = ("asc", "desc")

_documents = table("documents", *(column(name) for name in COLUMNS))


def _uuid_param(value: str) -> ColumnElement[Any]:
    # Untyped so asyncpg lets PostgreSQL infer uuid instead of casting to VARCHAR.
    return literal(value, NullType())


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
        c = _documents.c
        clauses: list[ColumnElement[bool]] = [
            c.is_deleted == false(),
            c.is_template == false(),
        ]
        if owner_id:
            clauses.append(c.owner_id == _uuid_param(owner_id))
        if folder_id:
            clauses.append(c.folder_id == _uuid_param(folder_id))
        if title_contains:
            clauses.append(func.lower(c.title).like(func.lower(f"%{title_contains}%")))
        if content_type:
            clauses.append(c.content_type == content_type)
        return clauses

    @staticmethod
    def _order_by(sort: str, direction: str) -> ColumnElement[Any]:
        sort_key = sort.strip().lower()
        direction_key = direction.strip().lower()
        if sort_key not in COLUMNS:
            raise ArgumentError(f"unsupported sort column; expected one of {COLUMNS}")
        if direction_key not in SORT_DIRECTIONS:
            raise ArgumentError(f"unsupported sort direction; expected one of {SORT_DIRECTIONS}")
        sort_column = _documents.c[sort_key]
        return sort_column.asc() if direction_key == "asc" else sort_column.desc()

    async def count_documents(
        self,
        *,
        owner_id: str | None = None,
        title_contains: str | None = None,
        content_type: str | None = None,
        folder_id: str | None = None,
    ) -> int:
        """Count documents matching the metadata filters."""
        statement = (
            select(func.count())
            .select_from(_documents)
            .where(*self._where(owner_id, title_contains, content_type, folder_id))
        )
        result = await self.db.execute(statement)
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
        statement = (
            select(*(_documents.c[name] for name in COLUMNS))
            .where(*self._where(owner_id, title_contains, content_type, folder_id))
            .order_by(self._order_by(sort, direction))
            .limit(limit)
            .offset(offset)
        )
        logger.debug("document_filter_query", sort=sort, direction=direction)
        result = await self.db.execute(statement)
        return [dict(row._mapping) for row in result]
