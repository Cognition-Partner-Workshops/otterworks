"""QA (files area): size/type/name validation and error contracts."""

import uuid

import pytest


pytestmark = pytest.mark.api_flow

MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def test_upload_over_100mb_is_rejected_with_413(api_client):
    owner = api_client.register_user("qa-files-toobig")
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("big.bin", b"\0" * (MAX_UPLOAD_BYTES + 1), "application/octet-stream")},
        timeout=120.0,
    )
    assert response.status_code == 413, response.text
    body = api_client.assert_json_error(response)
    assert body["error"] == "file_too_large"
    listed = api_client.client.get("/api/v1/files", headers=owner.auth_headers).json()
    assert listed["total"] == 0


def test_empty_upload_is_rejected(api_client):
    owner = api_client.register_user("qa-files-empty")
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400, response.text
    api_client.assert_json_error(response)


def test_upload_without_file_part_is_rejected(api_client):
    owner = api_client.register_user("qa-files-nopart")
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"other": ("x.txt", b"x", "text/plain")},
    )
    assert response.status_code == 400, response.text


def test_unauthenticated_file_requests_are_rejected(api_client):
    for method, path in (
        ("GET", "/api/v1/files"),
        ("GET", f"/api/v1/files/{uuid.uuid4()}"),
        ("POST", "/api/v1/files/upload"),
    ):
        response = api_client.client.request(method, path)
        assert response.status_code == 401, f"{method} {path}: {response.status_code}"


def test_blank_rename_is_rejected_and_name_unchanged(api_client):
    owner = api_client.register_user("qa-files-blank-rename")
    upload = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("keep.txt", b"k", "text/plain")},
    )
    fileId = upload.json()["file"]["id"]
    api_client.created_files.append(fileId)

    response = api_client.client.patch(
        f"/api/v1/files/{fileId}/rename", headers=owner.auth_headers, json={"name": "   "}
    )
    assert response.status_code == 400, response.text
    assert api_client.client.get(f"/api/v1/files/{fileId}", headers=owner.auth_headers).json()["name"] == "keep.txt"


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("GET", "", None),
        ("GET", "/download", None),
        ("PATCH", "/rename", {"name": "x.txt"}),
        ("PUT", "/move", {"folder_id": None}),
        ("POST", "/trash", None),
        ("DELETE", "", None),
    ],
)
def test_operations_on_missing_file_return_404(api_client, method, suffix, body):
    owner = api_client.register_user("qa-files-missing")
    response = api_client.client.request(
        method, f"/api/v1/files/{uuid.uuid4()}{suffix}", headers=owner.auth_headers, json=body
    )
    assert response.status_code == 404, response.text


def test_malformed_file_id_returns_400(api_client):
    owner = api_client.register_user("qa-files-badid")
    response = api_client.client.get("/api/v1/files/not-a-uuid/download", headers=owner.auth_headers)
    assert response.status_code == 400, response.text
    api_client.assert_json_error(response)


@pytest.mark.gap_revealer
def test_move_into_nonexistent_folder_is_rejected(api_client):
    owner = api_client.register_user("qa-files-move-ghost")
    upload = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("ghost.txt", b"g", "text/plain")},
    )
    fileId = upload.json()["file"]["id"]
    api_client.created_files.append(fileId)

    response = api_client.client.put(
        f"/api/v1/files/{fileId}/move",
        headers=owner.auth_headers,
        json={"folder_id": str(uuid.uuid4())},
    )
    assert response.status_code in {400, 404}, (
        f"file was moved into a folder that does not exist: {response.status_code} {response.text}"
    )


@pytest.mark.gap_revealer
def test_rename_rejects_path_separators(api_client):
    owner = api_client.register_user("qa-files-rename-slash")
    upload = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("plain.txt", b"p", "text/plain")},
    )
    fileId = upload.json()["file"]["id"]
    api_client.created_files.append(fileId)

    response = api_client.client.patch(
        f"/api/v1/files/{fileId}/rename", headers=owner.auth_headers, json={"name": "../escape.txt"}
    )
    assert response.status_code == 400, f"path-like name accepted: {response.text}"
