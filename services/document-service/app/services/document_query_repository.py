"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import and_, bindparam, column, func, select, table
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
    ):
        clauses = [DOCUMENTS.c.is_deleted == False, DOCUMENTS.c.is_template == False]  # noqa: E712
        if owner_id:
            clauses.append(
                DOCUMENTS.c.owner_id == bindparam("owner_id", owner_id, type_=NullType())
            )
        if folder_id:
            clauses.append(
                DOCUMENTS.c.folder_id == bindparam("folder_id", folder_id, type_=NullType())
            )
        if title_contains:
            clauses.append(func.lower(DOCUMENTS.c.title).like(func.lower(f"%{title_contains}%")))
        if content_type:
            clauses.append(DOCUMENTS.c.content_type == content_type)
        return and_(*clauses)

    async def count_documents(
        self,
        *,
        owner_id: str | None = None,
        title_contains: str | None = None,
        content_type: str | None = None,
        folder_id: str | None = None,
    ) -> int:
        """Count documents matching the metadata filters."""
        query = (
            select(func.count()).select_from(DOCUMENTS)
            .where(self._where(owner_id, title_contains, content_type, folder_id))
        )
        result = await self.db.execute(query)
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
        if sort not in COLUMNS or direction.lower() not in ("asc", "desc"):
            raise ValueError("Invalid document ordering")
        order = DOCUMENTS.c[sort]
        query = (
            select(DOCUMENTS)
            .where(self._where(owner_id, title_contains, content_type, folder_id))
            .order_by(order.asc() if direction.lower() == "asc" else order.desc())
            .limit(limit).offset(offset)
        )
        logger.debug("document_filter_query", sort=sort, direction=direction)
        result = await self.db.execute(query)
        return [dict(row._mapping) for row in result]
