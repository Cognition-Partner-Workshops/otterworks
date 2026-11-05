"""Security observations do not change vulnerable endpoint behavior."""

import uuid
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from app.api.documents import _observe_body_owner
from app.telemetry import AUTHZ_EVENTS, SECURITY_EVENTS


@pytest.mark.parametrize("body", [b"", b"not-json", b"{"])
async def test_body_observer_ignores_invalid_json(body):
    request = Request(
        {"type": "http", "method": "PUT", "path": "/", "headers": []},
        receive=AsyncMock(return_value={"type": "http.request", "body": body}),
    )
    await _observe_body_owner(request)


def value(event, outcome):
    return AUTHZ_EVENTS.labels(event, outcome)._value.get()


@pytest.fixture
def identity(monkeypatch, owner_id):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    return {"Authorization": "Bearer token", "X-User-ID": str(owner_id)}


async def test_owner_observations(client, owner_id, identity):
    other = str(uuid.uuid4())
    before = value("owner_override", "observed")
    created = await client.post(
        "/api/v1/documents/", headers=identity, json={"title": "Foreign", "owner_id": other}
    )
    assert created.status_code == 201
    assert created.json()["owner_id"] == other
    assert value("owner_override", "observed") == before + 1
    doc_id = created.json()["id"]

    before = value("cross_owner_object", "allowed")
    for path in ("/api/v1/documents/", "/api/v1/documents"):
        response = await client.get(path, headers=identity, params={"owner_id": other})
        assert response.status_code == 200
        assert response.json()["items"][0]["id"] == doc_id
    assert value("cross_owner_object", "allowed") == before + 2
    response = await client.get(
        "/api/v1/documents/search", headers=identity, params={"q": "Foreign"}
    )
    assert response.status_code == 200
    assert value("cross_owner_object", "allowed") == before + 3

    before = value("cross_owner_object", "denied")
    denied = await client.get(f"/api/v1/documents/{doc_id}", headers=identity)
    assert denied.status_code == 403
    assert value("cross_owner_object", "denied") == before + 1
    missing = await client.get(f"/api/v1/documents/{uuid.uuid4()}", headers=identity)
    assert missing.status_code == 404
    assert value("cross_owner_object", "denied") == before + 1


async def test_normal_empty_and_update_owner_observations(client, owner_id, identity):
    before = value("owner_override", "observed")
    allowed = value("cross_owner_object", "allowed")
    for body in ({"title": "Implicit"}, {"title": "Explicit", "owner_id": str(owner_id)}):
        created = await client.post("/api/v1/documents/", headers=identity, json=body)
        assert created.status_code == 201
    doc_id = created.json()["id"]
    response = await client.get("/api/v1/documents/", headers=identity)
    assert response.status_code == 200
    empty = await client.get(
        "/api/v1/documents/", headers=identity, params={"folder_id": str(uuid.uuid4())}
    )
    assert empty.json()["items"] == []
    assert value("owner_override", "observed") == before
    assert value("cross_owner_object", "allowed") == allowed
    for method in ("put", "patch"):
        response = await getattr(client, method)(
            f"/api/v1/documents/{doc_id}",
            headers=identity,
            json={"title": "Updated", "owner_id": str(uuid.uuid4())},
        )
        assert response.status_code == 200
        assert response.json()["owner_id"] == str(owner_id)
    assert value("owner_override", "observed") == before + 2


async def test_foreign_empty_list_and_filter_error(client, identity):
    before = value("cross_owner_object", "allowed")
    other = str(uuid.uuid4())
    empty = await client.get(
        "/api/v1/documents/", headers=identity, params={"owner_id": other, "title": "absent"}
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert value("cross_owner_object", "allowed") == before + 1
    invalid = await client.get(
        "/api/v1/documents/", headers=identity, params={"owner_id": other, "sort": "not_a_column"}
    )
    assert invalid.status_code == 400
    assert value("cross_owner_object", "allowed") == before + 1


async def test_template_owner_observation(client, identity):
    template = await client.post(
        "/api/v1/templates/", json={"name": "Blank", "content": "", "created_by": str(uuid.uuid4())}
    )
    before = value("owner_override", "observed")
    other = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/documents/from-template/{template.json()['id']}",
        headers=identity,
        json={"title": "From template", "owner_id": other},
    )
    assert response.status_code == 201
    assert response.json()["owner_id"] == other
    assert value("owner_override", "observed") == before + 1


@pytest.mark.parametrize(
    "name,suspicious",
    [
        ("report.md", False),
        ("absent.md", False),
        ("../outside.md", True),
        ("/absent.md", True),
        ("nested/file.md", True),
        ("nested\\file.md", True),
    ],
)
async def test_export_observations(client, monkeypatch, tmp_path, name, suspicious):
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))
    (tmp_path / "report.md").write_text("report")
    before = value("export_path_traversal", "observed")
    response = await client.get("/api/v1/documents/exports", params={"name": name})
    assert response.status_code == (200 if name == "report.md" else 404)
    assert value("export_path_traversal", "observed") == before + int(suspicious)


async def test_share_and_metrics_exposure(client, owner_id, identity):
    created = await client.post("/api/v1/documents/", headers=identity, json={"title": "Share"})
    doc_id = created.json()["id"]
    minted = await client.post(f"/api/v1/documents/{doc_id}/share", headers=identity)
    counter = SECURITY_EVENTS.labels("share_token_rejected")
    before = counter._value.get()
    response = await client.get(
        "/api/v1/documents/shared", params={"document_id": doc_id, "token": minted.json()["token"]}
    )
    assert response.status_code == 200
    assert counter._value.get() == before
    allowed = value("cross_owner_object", "allowed")
    foreign = {**identity, "X-User-ID": str(uuid.uuid4())}
    response = await client.get(
        "/api/v1/documents/shared",
        headers=foreign,
        params={"document_id": doc_id, "token": minted.json()["token"]},
    )
    assert response.status_code == 200
    assert value("cross_owner_object", "allowed") == allowed + 1
    response = await client.get(
        "/api/v1/documents/shared", params={"document_id": doc_id, "token": "bad"}
    )
    assert response.status_code == 403
    assert counter._value.get() == before + 1
    response = await client.get("/api/v1/documents/shared", params={"document_id": doc_id})
    assert response.status_code == 422
    assert counter._value.get() == before + 2
    response = await client.get(
        "/api/v1/documents/shared", params={"document_id": doc_id, "token": ""}
    )
    assert response.status_code == 422
    assert counter._value.get() == before + 3
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    assert 'otterworks_security_events_total{event="share_token_rejected"}' in metrics.text
    assert (
        'otterworks_authz_events_total{event="owner_override",outcome="observed"}' in metrics.text
    )
