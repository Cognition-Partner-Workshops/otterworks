"""Caller values remain data in metadata queries."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects.postgresql.asyncpg import dialect

from app.services.document_query_repository import DocumentQueryRepository


@pytest.mark.parametrize("value", ["report", "' OR 1=1 --", "O'Reilly", "%_"])
async def test_filter_values_are_bound(value):
    db = AsyncMock()
    db.execute.return_value.scalar_one = lambda: 0
    repo = DocumentQueryRepository(db)
    assert await repo.count_documents(
        owner_id=value, title_contains=value, content_type=value, folder_id=value
    ) == 0
    query = db.execute.call_args.args[0].compile()
    assert value not in str(query)
    assert value in query.params.values()
    assert f"%{value}%" in query.params.values()


def test_uuid_filters_use_database_inferred_types():
    query = DocumentQueryRepository(None)._where("owner", None, None, "folder")
    compiled = query.compile(dialect=dialect())
    assert "::VARCHAR" not in str(compiled)
    assert compiled.params == {"owner_id": "owner", "folder_id": "folder"}


@pytest.mark.parametrize("sort,direction", [("title; DROP TABLE documents", "asc"),
                                              ("title", "desc; SELECT 1"), ("", "asc")])
async def test_invalid_ordering_never_executes(sort, direction):
    db = AsyncMock()
    with pytest.raises(ValueError, match="Invalid document ordering"):
        await DocumentQueryRepository(db).search_documents(sort=sort, direction=direction)
    db.execute.assert_not_called()
