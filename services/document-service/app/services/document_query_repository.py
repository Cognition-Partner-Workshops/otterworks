"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import BindParameter, ColumnElement, bindparam, false, func, select, table
from sqlalchemy import column as sql_column
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

DOCUMENTS = table("documents", *(sql_column(name) for name in COLUMNS))
DIRECTIONS = {"asc": "asc", "desc": "desc"}


def _untyped(value: Any) -> BindParameter[Any]:
    """Bind without a client-side type so the database infers it (uuid columns)."""
    return bindparam(None, value, type_=NullType())


class DocumentQueryRepository:
    """Reads the document table for the list endpoint's metadata filters.

    Statements are composed with SQLAlchemy Core, so every caller-supplied value
    is a bound parameter. Sort column and direction are resolved from allow-lists.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _where(
        owner_id: str | None,
        title_contains: str | None,
        content_type: str | None,
        folder_id: str | None = None,
    ) -> list[ColumnElement[bool]]:
        c = DOCUMENTS.c
        clauses: list[ColumnElement[bool]] = [c.is_deleted == false(), c.is_template == false()]
        if owner_id:
            clauses.append(c.owner_id == _untyped(owner_id))
        if folder_id:
            clauses.append(c.folder_id == _untyped(folder_id))
        if title_contains:
            clauses.append(func.lower(c.title).like(func.lower(f"%{title_contains}%")))
        if content_type:
            clauses.append(c.content_type == content_type)
        return clauses

    @staticmethod
    def _order_by(sort: str, direction: str) -> ColumnElement[Any]:
        name = sort.lower()
        if name not in COLUMNS:
            raise ValueError("unsupported sort column")
        keyword = DIRECTIONS.get(direction.lower())
        if keyword is None:
            raise ValueError("unsupported sort direction")
        column = DOCUMENTS.c[name]
        return column.asc() if keyword == "asc" else column.desc()

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
            .select_from(DOCUMENTS)
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
            select(*(DOCUMENTS.c[name] for name in COLUMNS))
            .where(*self._where(owner_id, title_contains, content_type, folder_id))
            .order_by(self._order_by(sort, direction))
            .limit(int(limit))
            .offset(int(offset))
        )
        logger.debug("document_filter_query", sort=sort, direction=direction)
        result = await self.db.execute(statement)
        return [dict(row._mapping) for row in result]
