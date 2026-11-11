"""Tests for the reading_time_minutes field on document responses."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.schemas.document import READING_WORDS_PER_MINUTE, DocumentResponse


def _response(word_count: int) -> DocumentResponse:
    now = datetime.now(UTC)
    return DocumentResponse(
        id=uuid.uuid4(),
        title="Doc",
        content="",
        content_type="text/markdown",
        owner_id=uuid.uuid4(),
        folder_id=None,
        is_deleted=False,
        is_template=False,
        word_count=word_count,
        version=1,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.parametrize(
    ("word_count", "expected"),
    [
        (0, 0),
        (1, 1),
        (READING_WORDS_PER_MINUTE, 1),
        (READING_WORDS_PER_MINUTE + 1, 2),
        (READING_WORDS_PER_MINUTE * 5, 5),
    ],
)
def test_reading_time_rounds_up_to_whole_minutes(word_count: int, expected: int):
    assert _response(word_count).reading_time_minutes == expected


def test_reading_time_is_serialized():
    assert _response(450).model_dump()["reading_time_minutes"] == 3


@pytest.mark.asyncio
async def test_create_and_list_include_reading_time(client: AsyncClient, owner_id: uuid.UUID):
    body = " ".join(["word"] * (READING_WORDS_PER_MINUTE + 1))
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Long read", "content": body, "owner_id": str(owner_id)},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["word_count"] == READING_WORDS_PER_MINUTE + 1
    assert created["reading_time_minutes"] == 2

    empty_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Empty", "content": "", "owner_id": str(owner_id)},
    )
    assert empty_resp.status_code == 201
    assert empty_resp.json()["reading_time_minutes"] == 0

    list_resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert list_resp.status_code == 200
    by_id = {item["id"]: item for item in list_resp.json()["items"]}
    assert by_id[created["id"]]["reading_time_minutes"] == 2
    assert by_id[empty_resp.json()["id"]]["reading_time_minutes"] == 0
