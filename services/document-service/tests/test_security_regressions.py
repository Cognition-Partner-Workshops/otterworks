"""Regression tests for document-service access control and data-exposure fixes."""

import hashlib
import hmac
import json
import uuid
from urllib.parse import urlparse

import pytest
from httpx import AsyncClient

from app.chaos import FLAG_REQUEST_LOG
from app.config import Settings
from app.middleware import request_log as request_log_module
from app.middleware.request_log import RequestLog
from app.services.document_query_repository import DocumentQueryRepository
from app.services.export_archive import ExportArchive
from app.services.share_link import ShareLinkService
from tests.conftest import TEST_SHARE_LINK_SECRET, auth_headers

DOCS = "/api/v1/documents/"


async def _create(client: AsyncClient, owner: uuid.UUID, title: str, **extra) -> dict:
    resp = await client.post(
        DOCS,
        json={"title": title, "content": f"{title} body", **extra},
        headers=auth_headers(owner),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---- sfind-7042a65c: list trusts caller-supplied owner_id ----


@pytest.mark.asyncio
async def test_list_rejects_another_users_owner_id(anon_client: AsyncClient):
    alice, bob = uuid.uuid4(), uuid.uuid4()
    await _create(anon_client, alice, "Alice private")

    resp = await anon_client.get(
        DOCS, params={"owner_id": str(alice)}, headers=auth_headers(bob)
    )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_filtered_list_rejects_another_users_owner_id(anon_client: AsyncClient):
    alice, bob = uuid.uuid4(), uuid.uuid4()
    await _create(anon_client, alice, "Alice report")

    resp = await anon_client.get(
        DOCS,
        params={"owner_id": str(alice), "title": "report"},
        headers=auth_headers(bob),
    )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_requires_authentication(anon_client: AsyncClient):
    await _create(anon_client, uuid.uuid4(), "Someone's doc")

    resp = await anon_client.get(DOCS)

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_defaults_to_callers_documents(anon_client: AsyncClient):
    alice, bob = uuid.uuid4(), uuid.uuid4()
    await _create(anon_client, alice, "Alice doc")
    await _create(anon_client, bob, "Bob doc")

    resp = await anon_client.get(DOCS, headers=auth_headers(bob))

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Bob doc"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["admin", "ADMIN"])
async def test_admin_may_list_another_users_documents(anon_client: AsyncClient, role: str):
    alice, admin = uuid.uuid4(), uuid.uuid4()
    await _create(anon_client, alice, "Alice doc")

    resp = await anon_client.get(
        DOCS, params={"owner_id": str(alice)}, headers=auth_headers(admin, roles=[role])
    )

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Alice doc"]


# ---- sfind-63052532: documents can be created in another user's account ----


@pytest.mark.asyncio
async def test_create_rejects_another_users_owner_id(anon_client: AsyncClient):
    alice, bob = uuid.uuid4(), uuid.uuid4()

    resp = await anon_client.post(
        DOCS,
        json={"title": "Planted", "owner_id": str(alice)},
        headers=auth_headers(bob),
    )

    assert resp.status_code == 403
    listed = await anon_client.get(DOCS, headers=auth_headers(alice))
    assert listed.json()["total"] == 0


@pytest.mark.asyncio
async def test_create_requires_authentication_even_with_owner_id(anon_client: AsyncClient):
    resp = await anon_client.post(
        DOCS, json={"title": "Anonymous", "owner_id": str(uuid.uuid4())}
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_stores_callers_id(anon_client: AsyncClient):
    bob = uuid.uuid4()

    created = await _create(anon_client, bob, "Mine", owner_id=str(bob))

    assert created["owner_id"] == str(bob)


# ---- sfind-4f49e9e2: X-User-ID trusted when JWT_SECRET is unset ----


@pytest.mark.asyncio
async def test_x_user_id_is_not_identity_without_jwt_secret(
    anon_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    owner = uuid.uuid4()
    doc = await _create(anon_client, owner, "Owned")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    resp = await anon_client.get(
        f"{DOCS}{doc['id']}",
        headers={"Authorization": "Bearer anything", "X-User-ID": str(owner)},
    )

    assert resp.status_code == 401


# ---- sfind-4927b2b0: search returns every user's documents ----


@pytest.mark.asyncio
async def test_search_never_returns_other_users_documents(anon_client: AsyncClient):
    alice, bob = uuid.uuid4(), uuid.uuid4()
    await _create(anon_client, alice, "Merger plan")
    await _create(anon_client, bob, "Merger notes")

    resp = await anon_client.get(
        f"{DOCS}search", params={"q": "Merger"}, headers=auth_headers(bob)
    )

    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Merger notes"]
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_search_requires_authentication(anon_client: AsyncClient):
    resp = await anon_client.get(f"{DOCS}search", params={"q": "anything"})

    assert resp.status_code == 401


# ---- sfind-36210d74: SQL injection in list filters and sort ----


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"sort": "updated_at;select pg_sleep(5)"},
        {"sort": "title; DROP TABLE documents"},
        {"direction": "desc; select 1"},
    ],
)
async def test_sort_injection_is_rejected_without_sql_in_error(
    client: AsyncClient, owner_id: uuid.UUID, params: dict
):
    await _create(client, owner_id, "Report")

    resp = await client.get(DOCS, params=params)

    assert resp.status_code == 400
    detail = resp.text.lower()
    for leaked in ("select", "from documents", "syntax", "sqlite", "operationalerror"):
        assert leaked not in detail


@pytest.mark.asyncio
async def test_title_quote_is_treated_as_data(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Quarterly report")

    resp = await client.get(DOCS, params={"title": "report'"})

    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_content_type_tautology_does_not_cross_owners(
    anon_client: AsyncClient, db_session
):
    alice, bob = uuid.uuid4(), uuid.uuid4()
    await _create(anon_client, alice, "Alice secret")
    await _create(anon_client, bob, "Bob doc")

    rows = await DocumentQueryRepository(db_session).search_documents(
        owner_id=str(bob), content_type="text/markdown' OR '1'='1"
    )

    assert rows == []


@pytest.mark.asyncio
async def test_repository_rejects_unknown_sort_column(db_session):
    with pytest.raises(ValueError):
        await DocumentQueryRepository(db_session).search_documents(
            sort="title; DROP TABLE documents"
        )


# ---- sfind-890d3acf / sfind-e61dc81c: share-link tokens from a public salt ----

DOC_ID = "11111111-1111-4111-8111-111111111111"


def test_token_from_old_default_salt_is_rejected():
    forged = hashlib.md5(f"{DOC_ID}:otterworks-share".encode()).hexdigest()[:16]  # noqa: S324

    assert ShareLinkService().verify_token(DOC_ID, forged) is False


def test_token_is_hmac_sha256_of_document_id():
    expected = hmac.new(
        TEST_SHARE_LINK_SECRET.encode(), DOC_ID.encode(), hashlib.sha256
    ).hexdigest()

    assert ShareLinkService().mint_token(DOC_ID) == expected


def test_share_link_service_requires_a_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SHARE_LINK_SECRET", raising=False)

    with pytest.raises(RuntimeError):
        ShareLinkService()


# ---- sfind-b4edaa4a: path traversal in export reader ----


@pytest.fixture
def archive(tmp_path):
    base = tmp_path / "archive"
    (base / "reports").mkdir(parents=True)
    (base / "report.md").write_text("# Report\n", encoding="utf-8")
    (tmp_path / "outside.env").write_text("SUPPLIER_API_KEY=x\n", encoding="utf-8")
    return ExportArchive(base_dir=str(base))


@pytest.mark.parametrize(
    "name",
    [
        "/etc/passwd",
        "../../../proc/self/environ",
        "report.md/../../outside.env",
        "../outside.env",
        "reports/../../outside.env",
    ],
)
def test_export_reader_refuses_paths_outside_archive(archive, name):
    with pytest.raises(FileNotFoundError):
        archive.read_export(name)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["/etc/passwd", "../../../proc/self/environ"])
async def test_export_endpoint_404s_for_traversal(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path, name
):
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))

    resp = await client.get(f"{DOCS}exports", params={"name": name})

    assert resp.status_code == 404
    assert "root:" not in resp.text


# ---- sfind-e581959a: request log writes document text to disk ----


@pytest.mark.asyncio
async def test_request_log_keeps_metadata_but_no_document_text(
    anon_client: AsyncClient, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(request_log_module, "flag_active", lambda key: key == FLAG_REQUEST_LOG)
    monkeypatch.setattr(request_log_module, "request_log", RequestLog(str(tmp_path)))
    owner = uuid.uuid4()
    await anon_client.post(
        DOCS,
        json={"title": "Payroll", "content": "CONFIDENTIAL-SALARY-TABLE"},
        headers={**auth_headers(owner), "X-User-ID": str(owner)},
    )

    raw = (tmp_path / next(p.name for p in tmp_path.iterdir())).read_text()

    assert "CONFIDENTIAL-SALARY-TABLE" not in raw
    assert str(owner) not in raw
    record = json.loads(raw.splitlines()[-1])
    assert "response" not in record
    assert record["status"] == 201
    assert record["response_bytes"] > 0
    assert "duration_ms" in record


# ---- sfind-c4f244f4: hardcoded PostgreSQL password ----


def test_default_database_url_has_no_password():
    default = Settings.model_fields["database_url"].default

    assert urlparse(default.replace("+asyncpg", "")).password is None
