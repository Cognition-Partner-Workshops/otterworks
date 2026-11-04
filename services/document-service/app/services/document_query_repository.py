"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import ColumnElement, String, bindparam, column, false, func, select, table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import SQLAlchemyError
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

DIRECTIONS = ("asc", "desc")

_LIKE_ESCAPE = "!"

# Bound as uuid on PostgreSQL (the column type) and as text elsewhere, matching
# how the ids are stored by each backend.
_UUID_TEXT = String().with_variant(UUID(as_uuid=False), "postgresql")

_documents = table("documents", *(column(name) for name in COLUMNS))


class InvalidDocumentFilterError(SQLAlchemyError):
    """A filter was rejected or the filter query failed.

    The message is safe to return to the caller: it never carries the SQL
    statement, bound values or the database driver's error text.
    """


def _escape_like(value: str) -> str:
    return (
        value.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", f"{_LIKE_ESCAPE}%")
        .replace("_", f"{_LIKE_ESCAPE}_")
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
        c = _documents.c
        clauses: list[ColumnElement[bool]] = [c.is_deleted == false(), c.is_template == false()]
        if owner_id:
            clauses.append(c.owner_id == bindparam("owner_id", owner_id, type_=_UUID_TEXT))
        if folder_id:
            clauses.append(c.folder_id == bindparam("folder_id", folder_id, type_=_UUID_TEXT))
        if title_contains:
            pattern = f"%{_escape_like(title_contains)}%"
            clauses.append(func.lower(c.title).like(func.lower(pattern), escape=_LIKE_ESCAPE))
        if content_type:
            clauses.append(c.content_type == content_type)
        return clauses

    async def _execute(self, stmt: Any) -> Any:
        try:
            return await self.db.execute(stmt)
        except SQLAlchemyError as exc:
            logger.warning("document_filter_query_failed", error_type=type(exc).__name__)
            raise InvalidDocumentFilterError("document filter query failed") from exc

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
            .select_from(_documents)
            .where(*self._where(owner_id, title_contains, content_type, folder_id))
        )
        result = await self._execute(stmt)
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
        if sort not in COLUMNS:
            raise InvalidDocumentFilterError(
                f"unsupported sort column; expected one of: {', '.join(COLUMNS)}"
            )
        normalized_direction = direction.lower()
        if normalized_direction not in DIRECTIONS:
            raise InvalidDocumentFilterError("unsupported sort direction; expected asc or desc")
        sort_column = _documents.c[sort]
        order = sort_column.asc() if normalized_direction == "asc" else sort_column.desc()
        stmt = (
            select(*(_documents.c[name] for name in COLUMNS))
            .where(*self._where(owner_id, title_contains, content_type, folder_id))
            .order_by(order)
            .limit(int(limit))
            .offset(int(offset))
        )
        logger.debug("document_filter_query", sort=sort, direction=normalized_direction)
        result = await self._execute(stmt)
        return [dict(row._mapping) for row in result]
