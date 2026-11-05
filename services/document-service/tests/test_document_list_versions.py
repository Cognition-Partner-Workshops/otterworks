import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentVersion
from app.schemas.document import DocumentCreate
from app.services.document_service import DocumentService


@pytest.fixture
def sql_statements(db_session: AsyncSession) -> Iterator[list[str]]:
    statements: list[str] = []
    engine = db_session.bind.sync_engine

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)


@pytest.mark.asyncio
async def test_list_documents_batches_recent_versions_and_preserves_order(
    db_session: AsyncSession, owner_id: uuid.UUID, sql_statements: list[str]
) -> None:
    service = DocumentService(db_session)
    documents = [
        await service.create(
            DocumentCreate(title=f"Document {index}", content="body", owner_id=owner_id)
        )
        for index in range(2)
    ]
    for document in documents:
        for version_number in range(2, 8):
            db_session.add(
                DocumentVersion(
                    document_id=document.id,
                    version_number=version_number,
                    title=document.title,
                    content=f"version {version_number}",
                    created_by=owner_id,
                )
            )
    await db_session.commit()

    sql_statements.clear()
    db_session.expunge_all()
    one_document, one_total = await service.list_documents(owner_id=owner_id, size=1)
    one_page_statements = len(sql_statements)
    sql_statements.clear()
    db_session.expunge_all()
    listed, total = await service.list_documents(owner_id=owner_id, size=2)

    assert one_total == 2
    assert one_page_statements == 5
    assert total == 2
    assert len(sql_statements) == 5
    assert [version.version_number for version in one_document[0].recent_versions] == [
        7,
        6,
        5,
        4,
        3,
    ]
    assert [version.version_number for version in listed[0].recent_versions] == [7, 6, 5, 4, 3]
    assert [version.version_number for version in listed[1].recent_versions] == [7, 6, 5, 4, 3]


@pytest.mark.asyncio
async def test_list_documents_empty_page_does_not_query_versions(
    db_session: AsyncSession, owner_id: uuid.UUID, sql_statements: list[str]
) -> None:
    service = DocumentService(db_session)
    listed, total = await service.list_documents(owner_id=owner_id)

    assert listed == []
    assert total == 0
    assert len(sql_statements) == 2
