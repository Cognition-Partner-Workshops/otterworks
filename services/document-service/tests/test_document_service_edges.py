"""DocumentService paths not reached through the happy-path tests."""

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.document import DocumentCreate, DocumentPatch, DocumentUpdate
from app.services.document_service import DocumentService


async def _doc(service: DocumentService, owner_id: uuid.UUID, content: str = "one two"):
    return await service.create(DocumentCreate(title="T", content=content, owner_id=owner_id))


@pytest.mark.asyncio
async def test_update_and_patch_of_missing_document_return_none(db_session: AsyncSession):
    service = DocumentService(db_session)
    missing = uuid.uuid4()
    assert await service.update(missing, DocumentUpdate(title="x")) is None
    assert await service.patch(missing, DocumentPatch(title="x")) is None


@pytest.mark.asyncio
async def test_patch_content_recounts_words(db_session: AsyncSession, owner_id: uuid.UUID):
    service = DocumentService(db_session)
    doc = await _doc(service, owner_id)

    patched = await service.patch(doc.id, DocumentPatch(content="a b c d"))
    assert patched.word_count == 4
    assert patched.version == 2

    emptied = await service.patch(doc.id, DocumentPatch(content=""))
    assert emptied.content == ""
    assert emptied.word_count == 0
    assert emptied.version == 3


@pytest.mark.asyncio
async def test_patch_content_type_and_folder(
    db_session: AsyncSession, owner_id: uuid.UUID, folder_id: uuid.UUID
):
    service = DocumentService(db_session)
    doc = await _doc(service, owner_id)

    patched = await service.patch(
        doc.id, DocumentPatch(content_type="text/html", folder_id=folder_id)
    )
    assert patched.content_type == "text/html"
    assert patched.folder_id == folder_id
    assert patched.version == 2
    versions = await service.list_versions(doc.id)
    assert [v.version_number for v in versions] == [1, 2]

    moved_to_root = await service.patch(doc.id, DocumentPatch(folder_id=None))
    assert moved_to_root.folder_id is None


@pytest.mark.asyncio
async def test_empty_patch_does_not_bump_version(db_session: AsyncSession, owner_id: uuid.UUID):
    service = DocumentService(db_session)
    doc = await _doc(service, owner_id)

    unchanged = await service.patch(doc.id, DocumentPatch())
    assert unchanged.version == 1
    assert len(await service.list_versions(doc.id)) == 1


@pytest.mark.asyncio
async def test_restore_version_of_missing_document_or_version(
    db_session: AsyncSession, owner_id: uuid.UUID
):
    service = DocumentService(db_session)
    doc = await _doc(service, owner_id)
    (version,) = await service.list_versions(doc.id)
    other = await _doc(service, owner_id)

    assert await service.restore_version(uuid.uuid4(), version.id) is None
    assert await service.restore_version(doc.id, uuid.uuid4()) is None
    assert await service.restore_version(other.id, version.id) is None


@pytest.mark.asyncio
async def test_deleted_document_is_hidden_from_get_and_search(
    db_session: AsyncSession, owner_id: uuid.UUID
):
    service = DocumentService(db_session)
    doc = await service.create(
        DocumentCreate(title="Ephemeral", content="soon gone", owner_id=owner_id)
    )
    assert await service.delete(doc.id) is True

    assert await service.get(doc.id) is None
    items, total = await service.search("Ephemeral")
    assert (items, total) == ([], 0)
    assert await service.delete(doc.id) is False


@pytest.mark.parametrize("field", ["title", "content", "content_type"])
def test_patch_rejects_explicit_null_for_not_null_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        DocumentPatch.model_validate({field: None})


def test_patch_allows_null_folder() -> None:
    assert DocumentPatch.model_validate({"folder_id": None}).folder_id is None
