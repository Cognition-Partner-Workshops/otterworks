"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.document import Document

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
            Document.is_deleted.is_(False), Document.is_template.is_(False)
        ]
        if owner_id:
            clauses.append(Document.owner_id == UUID(owner_id))
        if folder_id:
            clauses.append(Document.folder_id == UUID(folder_id))
        if title_contains:
            clauses.append(Document.title.ilike(f"%{title_contains}%"))
        if content_type:
            clauses.append(Document.content_type == content_type)
        return clauses

    async def count_documents(
        self,
        *,
        owner_id: str | None = None,
        title_contains: str | None = None,
        content_type: str | None = None,
        folder_id: str | None = None,
    ) -> int:
        """Count documents matching the metadata filters."""
        query = select(func.count()).select_from(Document).where(
            *self._where(owner_id, title_contains, content_type, folder_id)
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
            raise ValueError("Invalid ordering")
        column = getattr(Document, sort)
        ordering = column.asc() if direction.lower() == "asc" else column.desc()
        query = (
            select(*(getattr(Document, name) for name in COLUMNS))
            .where(*self._where(owner_id, title_contains, content_type, folder_id))
            .order_by(ordering)
            .limit(limit)
            .offset(offset)
        )
        logger.debug("document_filter_query", sort=sort, direction=direction)
        result = await self.db.execute(query)
        return [dict(row._mapping) for row in result]
