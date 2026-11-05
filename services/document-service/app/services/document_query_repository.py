"""Metadata filtering for the document list endpoint.

The list endpoint supports ad-hoc metadata filters (title fragment, content
type) and caller-chosen ordering. The repository builds the predicate list for
those filters and reads the ``documents`` table directly. Every caller value
is a bound parameter; ``ORDER BY`` comes from a fixed allow-list.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import Integer, Uuid, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import BindParameter

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
SORT_DIRECTIONS = {"asc": "ASC", "desc": "DESC"}
_UUID_TYPE = Uuid()


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
    ) -> tuple[str, list[BindParameter]]:
        clauses = ["is_deleted = false", "is_template = false"]
        params: list[BindParameter] = []
        if owner_id:
            clauses.append("owner_id = :owner_id")
            params.append(bindparam("owner_id", UUID(owner_id), type_=_UUID_TYPE))
        if folder_id:
            clauses.append("folder_id = :folder_id")
            params.append(bindparam("folder_id", UUID(folder_id), type_=_UUID_TYPE))
        if title_contains:
            clauses.append("lower(title) LIKE lower(:title_pattern)")
            params.append(bindparam("title_pattern", f"%{title_contains}%"))
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
        statement = text(f"SELECT count(*) FROM documents WHERE {where}").bindparams(*params)
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
        """Return document rows matching the metadata filters, newest first.

        Raises ``ValueError`` when ``sort`` is not a document column or
        ``direction`` is not ``asc``/``desc``.
        """
        if sort not in COLUMNS:
            raise ValueError("unsupported sort column")
        order = SORT_DIRECTIONS.get(direction.lower())
        if order is None:
            raise ValueError("unsupported sort direction")
        where, params = self._where(owner_id, title_contains, content_type, folder_id)
        statement = text(
            f"SELECT {', '.join(COLUMNS)} FROM documents WHERE {where}"
            f" ORDER BY {sort} {order} LIMIT :limit OFFSET :offset"
        ).bindparams(
            *params,
            bindparam("limit", int(limit), type_=Integer()),
            bindparam("offset", int(offset), type_=Integer()),
        )
        logger.debug("document_filter_query", sort=sort, direction=order)
        result = await self.db.execute(statement)
        return [dict(row._mapping) for row in result]
