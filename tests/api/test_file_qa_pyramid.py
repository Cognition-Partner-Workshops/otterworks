"""Files-area QA: black-box API tests through the gateway.

Covers upload/download, rename, move, folders, trash/restore, metadata,
versions and owner isolation. Tests that encode a genuine defect are left
failing on purpose (see PR description); none of them are planted bugs.
"""

from __future__ import annotations

import os
import socket
import uuid
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.api_flow


# ── helpers ────────────────────────────────────────────────────────────


def createFolder(api_client, user, name: str, parentId: str | None = None) -> dict[str, Any]:
    response = api_client.client.post(
        "/api/v1/folders",
        headers=user.auth_headers,
        json={"name": name, "owner_id": user.id, "parent_id": parentId},
    )
    assert response.status_code == 201, response.text
    folder = response.json()
    api_client.created_folders.append(folder["id"])
    return folder


def uploadFile(
    api_client,
    user,
    name: str = "qa.txt",
    content: bytes = b"files qa content",
    mimeType: str = "text/plain",
    folderId: str | None = None,
) -> dict[str, Any]:
    data = {"folder_id": folderId} if folderId else {}
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=user.auth_headers,
        files={"file": (name, content, mimeType)},
        data=data,
    )
    assert response.status_code == 201, response.text
    file = response.json()["file"]
    api_client.created_files.append(file["id"])
    return file


def listFiles(api_client, user, **params) -> list[dict[str, Any]]:
    response = api_client.client.get("/api/v1/files", headers=user.auth_headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()["files"]


def fileIds(files: list[dict[str, Any]]) -> set[str]:
    return {f["id"] for f in files}


@pytest.fixture
def owner(api_client):
    return api_client.register_user("files-qa-owner")


@pytest.fixture
def otherUser(api_client):
    return api_client.register_user("files-qa-other")


# ── upload / metadata / download ───────────────────────────────────────


def test_upload_returns_complete_metadata(api_client, owner):
    content = b"metadata check \x00\x01 binary-ish"
    file = uploadFile(api_client, owner, name="meta.bin", content=content, mimeType="application/octet-stream")
    assert file["name"] == "meta.bin"
    assert file["size_bytes"] == len(content)
    assert file["mime_type"] == "application/octet-stream"
    assert file["owner_id"] == owner.id
    assert file["version"] == 1
    assert file["is_trashed"] is False
    uuid.UUID(file["id"])


def test_get_metadata_matches_upload(api_client, owner):
    file = uploadFile(api_client, owner, name="detail.txt")
    response = api_client.client.get(f"/api/v1/files/{file['id']}", headers=owner.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == file["id"]
    assert body["name"] == "detail.txt"
    assert body["shared_with"] == []


def test_download_url_serves_uploaded_bytes(api_client, owner):
    content = f"download roundtrip {api_client.run_id}".encode()
    file = uploadFile(api_client, owner, name="roundtrip.txt", content=content)
    response = api_client.client.get(f"/api/v1/files/{file['id']}/download", headers=owner.auth_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["url"].startswith("http")
    assert body["expires_in_secs"] > 0
    # Same rewrite the web client applies (frontend/client-app/src/lib/api.ts getDownloadUrl).
    blob = httpx.get(body["url"].replace("://localstack:", "://localhost:"), timeout=10)
    assert blob.status_code == 200
    assert blob.content == content


def test_upload_rejects_empty_file(api_client, owner):
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400, response.text


def test_upload_rejects_missing_file_part(api_client, owner):
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"other": ("x.txt", b"x", "text/plain")},
    )
    assert response.status_code == 400, response.text


def test_upload_ignores_spoofed_owner_field(api_client, owner, otherUser):
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("spoof.txt", b"spoof", "text/plain")},
        data={"owner_id": otherUser.id},
    )
    assert response.status_code == 201, response.text
    file = response.json()["file"]
    api_client.created_files.append(file["id"])
    assert file["owner_id"] == owner.id


def test_upload_rejects_malformed_folder_id(api_client, owner):
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("x.txt", b"x", "text/plain")},
        data={"folder_id": "not-a-uuid"},
    )
    assert response.status_code == 400, response.text


@pytest.mark.parametrize(
    "method,suffix",
    [
        ("get", ""),
        ("delete", ""),
        ("get", "/download"),
        ("get", "/versions"),
        ("post", "/trash"),
        ("post", "/restore"),
    ],
)
def test_invalid_file_id_returns_400(api_client, owner, method, suffix):
    response = api_client.client.request(method, f"/api/v1/files/not-a-uuid{suffix}", headers=owner.auth_headers)
    assert response.status_code == 400, response.text


@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("get", "", None),
        ("delete", "", None),
        ("get", "/download", None),
        ("post", "/trash", None),
        ("post", "/restore", None),
        ("patch", "/rename", {"name": "x.txt"}),
        ("put", "/move", {"folder_id": None}),
    ],
)
def test_missing_file_returns_404(api_client, owner, method, suffix, body):
    response = api_client.client.request(
        method, f"/api/v1/files/{uuid.uuid4()}{suffix}", headers=owner.auth_headers, json=body
    )
    assert response.status_code == 404, response.text


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/files"),
        ("get", "/api/v1/files/trash"),
        ("get", "/api/v1/files/shared"),
        ("post", "/api/v1/files/upload"),
        ("get", "/api/v1/folders"),
    ],
)
def test_files_routes_require_authentication(api_client, method, path):
    response = api_client.client.request(method, path)
    assert response.status_code == 401, response.text


# ── rename / move / versions ───────────────────────────────────────────


def test_rename_persists_and_trims(api_client, owner):
    file = uploadFile(api_client, owner, name="before.txt")
    response = api_client.client.patch(
        f"/api/v1/files/{file['id']}/rename", headers=owner.auth_headers, json={"name": "  after.txt  "}
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "after.txt"
    detail = api_client.client.get(f"/api/v1/files/{file['id']}", headers=owner.auth_headers).json()
    assert detail["name"] == "after.txt"


@pytest.mark.parametrize("badName", ["", "   "])
def test_rename_rejects_blank_name(api_client, owner, badName):
    file = uploadFile(api_client, owner)
    response = api_client.client.patch(
        f"/api/v1/files/{file['id']}/rename", headers=owner.auth_headers, json={"name": badName}
    )
    assert response.status_code == 400, response.text


def test_move_between_folders_and_back_to_root(api_client, owner):
    source = createFolder(api_client, owner, f"Src {api_client.run_id}")
    target = createFolder(api_client, owner, f"Dst {api_client.run_id}")
    file = uploadFile(api_client, owner, name="mover.txt", folderId=source["id"])
    assert file["folder_id"] == source["id"]

    moved = api_client.client.put(
        f"/api/v1/files/{file['id']}/move", headers=owner.auth_headers, json={"folder_id": target["id"]}
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["folder_id"] == target["id"]
    assert file["id"] in fileIds(listFiles(api_client, owner, folder_id=target["id"]))
    assert file["id"] not in fileIds(listFiles(api_client, owner, folder_id=source["id"]))

    toRoot = api_client.client.put(
        f"/api/v1/files/{file['id']}/move", headers=owner.auth_headers, json={"folder_id": None}
    )
    assert toRoot.status_code == 200, toRoot.text
    assert toRoot.json().get("folder_id") is None


def test_versions_lists_initial_version(api_client, owner):
    file = uploadFile(api_client, owner, content=b"v1 bytes")
    response = api_client.client.get(f"/api/v1/files/{file['id']}/versions", headers=owner.auth_headers)
    assert response.status_code == 200, response.text
    versions = response.json()["versions"]
    assert [v["version"] for v in versions] == [1]
    assert versions[0]["size_bytes"] == len(b"v1 bytes")
    assert versions[0]["created_by"] == owner.id


# ── folders ────────────────────────────────────────────────────────────


def test_nested_folder_create_get_list_rename(api_client, owner):
    parent = createFolder(api_client, owner, f"Parent {api_client.run_id}")
    child = createFolder(api_client, owner, "Child", parentId=parent["id"])
    assert child["parent_id"] == parent["id"]
    assert child["owner_id"] == owner.id

    got = api_client.client.get(f"/api/v1/folders/{child['id']}", headers=owner.auth_headers)
    assert got.status_code == 200, got.text
    assert got.json()["name"] == "Child"

    listed = api_client.client.get(
        "/api/v1/folders", headers=owner.auth_headers, params={"parent_id": parent["id"]}
    )
    assert listed.status_code == 200, listed.text
    assert child["id"] in {f["id"] for f in listed.json()["folders"]}

    renamed = api_client.client.put(
        f"/api/v1/folders/{child['id']}", headers=owner.auth_headers, json={"name": "Child Renamed"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Child Renamed"


def test_folder_list_is_scoped_to_caller(api_client, owner, otherUser):
    folder = createFolder(api_client, owner, f"Private {api_client.run_id}")
    listed = api_client.client.get("/api/v1/folders", headers=otherUser.auth_headers)
    assert listed.status_code == 200, listed.text
    assert folder["id"] not in {f["id"] for f in listed.json()["folders"]}


def test_folder_create_requires_owner(api_client, owner):
    response = api_client.client.post("/api/v1/folders", headers=owner.auth_headers, json={"name": "No Owner"})
    assert response.status_code == 400, response.text


def test_missing_folder_returns_404(api_client, owner):
    response = api_client.client.get(f"/api/v1/folders/{uuid.uuid4()}", headers=owner.auth_headers)
    assert response.status_code == 404, response.text


def test_folder_delete_removes_folder(api_client, owner):
    folder = createFolder(api_client, owner, f"Doomed {api_client.run_id}")
    deleted = api_client.client.delete(f"/api/v1/folders/{folder['id']}", headers=owner.auth_headers)
    assert deleted.status_code == 204, deleted.text
    got = api_client.client.get(f"/api/v1/folders/{folder['id']}", headers=owner.auth_headers)
    assert got.status_code == 404, got.text


# ── listing / trash / restore / delete ─────────────────────────────────


def test_list_is_scoped_to_caller(api_client, owner, otherUser):
    file = uploadFile(api_client, owner)
    assert file["id"] in fileIds(listFiles(api_client, owner))
    assert file["id"] not in fileIds(listFiles(api_client, otherUser))
    assert file["id"] not in fileIds(listFiles(api_client, otherUser, owner_id=owner.id))


def test_list_filters_by_folder(api_client, owner):
    folder = createFolder(api_client, owner, f"Filter {api_client.run_id}")
    inside = uploadFile(api_client, owner, name="inside.txt", folderId=folder["id"])
    outside = uploadFile(api_client, owner, name="outside.txt")
    ids = fileIds(listFiles(api_client, owner, folder_id=folder["id"]))
    assert inside["id"] in ids
    assert outside["id"] not in ids


def test_list_pagination_metadata(api_client, owner):
    for i in range(3):
        uploadFile(api_client, owner, name=f"page-{i}.txt")
    response = api_client.client.get(
        "/api/v1/files", headers=owner.auth_headers, params={"page": 1, "page_size": 2}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["files"]) <= 2
    assert body["total"] >= 3


def test_trash_hides_file_and_restore_brings_it_back(api_client, owner):
    file = uploadFile(api_client, owner, name="trashme.txt")
    trashed = api_client.client.post(f"/api/v1/files/{file['id']}/trash", headers=owner.auth_headers)
    assert trashed.status_code == 200, trashed.text
    assert trashed.json()["is_trashed"] is True

    assert file["id"] not in fileIds(listFiles(api_client, owner))
    assert file["id"] in fileIds(listFiles(api_client, owner, include_trashed="true"))
    trashList = api_client.client.get("/api/v1/files/trash", headers=owner.auth_headers)
    assert trashList.status_code == 200, trashList.text
    assert file["id"] in fileIds(trashList.json()["files"])

    restored = api_client.client.post(f"/api/v1/files/{file['id']}/restore", headers=owner.auth_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["is_trashed"] is False
    assert file["id"] in fileIds(listFiles(api_client, owner))
    trashAfter = api_client.client.get("/api/v1/files/trash", headers=owner.auth_headers).json()["files"]
    assert file["id"] not in fileIds(trashAfter)


def test_trash_list_is_scoped_to_caller(api_client, owner, otherUser):
    file = uploadFile(api_client, owner)
    api_client.client.post(f"/api/v1/files/{file['id']}/trash", headers=owner.auth_headers)
    otherTrash = api_client.client.get("/api/v1/files/trash", headers=otherUser.auth_headers)
    assert otherTrash.status_code == 200, otherTrash.text
    assert file["id"] not in fileIds(otherTrash.json()["files"])


def test_permanent_delete_removes_metadata_and_versions(api_client, owner):
    file = uploadFile(api_client, owner, name="gone.txt")
    deleted = api_client.client.delete(f"/api/v1/files/{file['id']}", headers=owner.auth_headers)
    assert deleted.status_code == 204, deleted.text
    assert api_client.client.get(f"/api/v1/files/{file['id']}", headers=owner.auth_headers).status_code == 404
    assert (
        api_client.client.get(f"/api/v1/files/{file['id']}/download", headers=owner.auth_headers).status_code == 404
    )
    assert file["id"] not in fileIds(listFiles(api_client, owner, include_trashed="true"))


# ── [REAL] defects: left failing on purpose ────────────────────────────
# security/dast/attack-surface.yaml: "/api/v1/files ... object ids from another
# owner return 403/404". Not listed in scripts/bug-catalog.yaml or AGENTS.md.


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason="[REAL] file-service has no object-level authz: any authenticated user can read/download/rename/trash/delete another user's file by ID")
@pytest.mark.parametrize(
    "method,suffix,body",
    [
        ("get", "", None),
        ("get", "/download", None),
        ("patch", "/rename", {"name": "hijacked.txt"}),
        ("post", "/trash", None),
        ("delete", "", None),
    ],
)
def test_non_owner_cannot_access_file_by_id(api_client, owner, otherUser, method, suffix, body):
    file = uploadFile(api_client, owner, name="private.txt")
    response = api_client.client.request(
        method, f"/api/v1/files/{file['id']}{suffix}", headers=otherUser.auth_headers, json=body
    )
    assert response.status_code in (403, 404), (
        f"[REAL] non-owner {method.upper()} {suffix or '/'} returned {response.status_code}"
    )
    stillThere = api_client.client.get(f"/api/v1/files/{file['id']}", headers=owner.auth_headers)
    assert stillThere.status_code == 200
    assert stillThere.json()["name"] == "private.txt"
    assert stillThere.json()["is_trashed"] is False


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason='[REAL] create_folder trusts the request body owner_id instead of the JWT subject')
def test_folder_create_ignores_spoofed_owner(api_client, owner, otherUser):
    response = api_client.client.post(
        "/api/v1/folders",
        headers=owner.auth_headers,
        json={"name": f"Spoofed {api_client.run_id}", "owner_id": otherUser.id},
    )
    if response.status_code == 201:
        api_client.created_folders.append(response.json()["id"])
        assert response.json()["owner_id"] == owner.id, "[REAL] folder created in another user's account"
    else:
        assert response.status_code in (400, 403), response.text


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason='[REAL] list_files applies no folder filter when folder_id is absent, so the root view returns files from every folder')
def test_root_listing_excludes_files_in_subfolders(api_client, owner):
    folder = createFolder(api_client, owner, f"Nested {api_client.run_id}")
    nested = uploadFile(api_client, owner, name="nested-only.txt", folderId=folder["id"])
    rootFile = uploadFile(api_client, owner, name="root-only.txt")
    rootIds = fileIds(listFiles(api_client, owner))
    assert rootFile["id"] in rootIds
    assert nested["id"] not in rootIds, "[REAL] root listing (no folder_id) returns files from every folder"


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason='[REAL] create_folder accepts blank/whitespace names')
@pytest.mark.parametrize("badName", ["", "   "])
def test_folder_create_rejects_blank_name(api_client, owner, badName):
    response = api_client.client.post(
        "/api/v1/folders", headers=owner.auth_headers, json={"name": badName, "owner_id": owner.id}
    )
    if response.status_code == 201:
        api_client.created_folders.append(response.json()["id"])
    assert response.status_code == 400, f"[REAL] blank folder name accepted ({response.status_code})"


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason='[REAL] update_folder accepts a blank/whitespace name')
def test_folder_rename_rejects_blank_name(api_client, owner):
    folder = createFolder(api_client, owner, f"Keep {api_client.run_id}")
    response = api_client.client.put(
        f"/api/v1/folders/{folder['id']}", headers=owner.auth_headers, json={"name": "  "}
    )
    assert response.status_code == 400, f"[REAL] blank folder rename accepted ({response.status_code})"


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason='[REAL] move_file does not verify the target folder exists')
def test_move_rejects_nonexistent_folder(api_client, owner):
    file = uploadFile(api_client, owner)
    response = api_client.client.put(
        f"/api/v1/files/{file['id']}/move", headers=owner.auth_headers, json={"folder_id": str(uuid.uuid4())}
    )
    assert response.status_code in (400, 404), f"[REAL] move into nonexistent folder accepted ({response.status_code})"


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason='[REAL] upload_file does not verify folder_id exists')
def test_upload_rejects_nonexistent_folder(api_client, owner):
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("orphan.txt", b"orphan", "text/plain")},
        data={"folder_id": str(uuid.uuid4())},
    )
    if response.status_code == 201:
        api_client.created_files.append(response.json()["file"]["id"])
    assert response.status_code in (400, 404), f"[REAL] upload into nonexistent folder accepted ({response.status_code})"


@pytest.mark.gap_revealer
@pytest.mark.xfail(strict=True, reason='[REAL] list_versions returns 200 [] for a nonexistent file instead of 404')
def test_versions_of_missing_file_returns_404(api_client, owner):
    response = api_client.client.get(f"/api/v1/files/{uuid.uuid4()}/versions", headers=owner.auth_headers)
    assert response.status_code == 404, f"[REAL] versions of nonexistent file returned {response.status_code}"


# ── planted scenario (bug-catalog: file-upload-fails) ──────────────────


def redisCommand(*args: str) -> bytes:
    host = os.getenv("OTTERWORKS_REDIS_HOST", "localhost")
    port = int(os.getenv("OTTERWORKS_REDIS_PORT", "6379"))
    payload = f"*{len(args)}\r\n" + "".join(f"${len(a)}\r\n{a}\r\n" for a in args)
    with socket.create_connection((host, port), timeout=2) as sock:
        sock.sendall(payload.encode())
        return sock.recv(1024)


@pytest.mark.degradation
def test_chaos_flag_upload_s3_error_breaks_uploads(api_client, owner):
    flag = "chaos:file-service:upload_s3_error"
    try:
        redisCommand("SET", flag, "1", "EX", "30")
    except OSError:
        pytest.skip("redis not reachable from the test host")
    try:
        response = api_client.client.post(
            "/api/v1/files/upload",
            headers=owner.auth_headers,
            files={"file": ("chaos.txt", b"chaos", "text/plain")},
        )
        assert response.status_code >= 500, response.text
    finally:
        redisCommand("DEL", flag)
    recovered = uploadFile(api_client, owner, name="after-chaos.txt")
    assert recovered["id"]
