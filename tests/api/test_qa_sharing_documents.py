"""QA: document share links and access control through the api-gateway."""

import uuid

import pytest


pytestmark = pytest.mark.api_flow


def mintLink(apiClient, user, documentId):
    return apiClient.client.post(f"/api/v1/documents/{documentId}/share", headers=user.auth_headers)


def openLink(apiClient, user, documentId, token):
    return apiClient.client.get(
        "/api/v1/documents/shared",
        headers=user.auth_headers,
        params={"document_id": documentId, "token": token},
    )


def test_owner_share_link_opens_document_for_another_user(api_client):
    owner = api_client.register_user("qa-doclink-owner")
    recipient = api_client.register_user("qa-doclink-recipient")
    document = api_client.create_document(owner, f"QA shared doc {api_client.run_id}", "shared body")

    minted = mintLink(api_client, owner, document["id"])
    assert minted.status_code == 200, minted.text
    token = minted.json()["token"]
    assert minted.json()["document_id"] == document["id"]
    assert len(token) == 16

    again = mintLink(api_client, owner, document["id"])
    assert again.json()["token"] == token

    opened = openLink(api_client, recipient, document["id"], token)
    assert opened.status_code == 200, opened.text
    assert opened.json()["id"] == document["id"]
    assert opened.json()["title"] == document["title"]


def test_share_link_rejects_bad_tokens(api_client):
    owner = api_client.register_user("qa-doclink-badtoken-owner")
    recipient = api_client.register_user("qa-doclink-badtoken-recipient")
    first = api_client.create_document(owner, "QA doc one", "one")
    second = api_client.create_document(owner, "QA doc two", "two")
    firstToken = mintLink(api_client, owner, first["id"]).json()["token"]

    assert openLink(api_client, recipient, first["id"], "0" * 16).status_code == 403
    assert openLink(api_client, recipient, first["id"], firstToken[:-1]).status_code == 403
    assert openLink(api_client, recipient, second["id"], firstToken).status_code == 403

    missingToken = api_client.client.get(
        "/api/v1/documents/shared", headers=recipient.auth_headers, params={"document_id": first["id"]}
    )
    assert missingToken.status_code == 422, missingToken.text


def test_non_owner_denied_document_and_link_minting(api_client):
    owner = api_client.register_user("qa-doclink-acl-owner")
    outsider = api_client.register_user("qa-doclink-acl-outsider")
    document = api_client.create_document(owner, "QA private doc", "secret body")

    direct = api_client.client.get(f"/api/v1/documents/{document['id']}", headers=outsider.auth_headers)
    assert direct.status_code == 403, direct.text

    minted = mintLink(api_client, outsider, document["id"])
    assert minted.status_code == 403, minted.text

    unauthenticated = api_client.client.post(f"/api/v1/documents/{document['id']}/share")
    assert unauthenticated.status_code == 401, unauthenticated.text

    missing = mintLink(api_client, owner, str(uuid.uuid4()))
    assert missing.status_code == 404, missing.text
