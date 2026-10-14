"""QA (files area): end-to-end file lifecycle through the API gateway."""

import httpx
import pytest


pytestmark = pytest.mark.api_flow


def fetchObject(downloadUrl: str) -> httpx.Response:
    # The file-service presigns against the in-cluster `localstack` host.
    return httpx.get(downloadUrl.replace("://localstack:", "://localhost:"), timeout=15.0)


def uploadFile(api_client, user, name: str, content: bytes, mimeType: str, **data):
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=user.auth_headers,
        files={"file": (name, content, mimeType)},
        data=data,
    )
    assert response.status_code == 201, response.text
    fileMeta = response.json()["file"]
    api_client.created_files.append(fileMeta["id"])
    return fileMeta


def listFileIds(api_client, user, **params) -> list[str]:
    response = api_client.client.get("/api/v1/files", headers=user.auth_headers, params=params)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["files"]]


def test_upload_records_accurate_metadata_and_download_round_trips_bytes(api_client):
    owner = api_client.register_user("qa-files-upload")
    payload = b"OtterWorks QA payload \xe2\x9c\x93\n" * 64

    fileMeta = uploadFile(api_client, owner, "qa-notes.txt", payload, "text/plain")

    assert fileMeta["name"] == "qa-notes.txt"
    assert fileMeta["mime_type"] == "text/plain"
    assert fileMeta["size_bytes"] == len(payload)
    assert fileMeta["owner_id"] == owner.id
    assert fileMeta["folder_id"] is None
    assert fileMeta["is_trashed"] is False
    assert fileMeta["version"] == 1

    download = api_client.client.get(f"/api/v1/files/{fileMeta['id']}/download", headers=owner.auth_headers)
    assert download.status_code == 200, download.text
    body = download.json()
    assert body["expires_in_secs"] > 0
    objectResponse = fetchObject(body["url"])
    assert objectResponse.status_code == 200
    assert objectResponse.content == payload


def test_binary_upload_preserves_bytes_and_mime(api_client):
    owner = api_client.register_user("qa-files-binary")
    pngBytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f"
        b"\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    fileMeta = uploadFile(api_client, owner, "pixel.png", pngBytes, "image/png")
    assert fileMeta["mime_type"] == "image/png"
    assert fileMeta["size_bytes"] == len(pngBytes)

    url = api_client.client.get(f"/api/v1/files/{fileMeta['id']}/download", headers=owner.auth_headers).json()["url"]
    assert fetchObject(url).content == pngBytes


def test_upload_without_content_type_defaults_to_octet_stream(api_client):
    owner = api_client.register_user("qa-files-noctype")
    response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("blob", b"raw-bytes")},
    )
    assert response.status_code == 201, response.text
    fileMeta = response.json()["file"]
    api_client.created_files.append(fileMeta["id"])
    assert fileMeta["mime_type"] == "application/octet-stream"


def test_rename_persists_and_trims_whitespace(api_client):
    owner = api_client.register_user("qa-files-rename")
    fileMeta = uploadFile(api_client, owner, "draft.txt", b"draft", "text/plain")

    rename = api_client.client.patch(
        f"/api/v1/files/{fileMeta['id']}/rename",
        headers=owner.auth_headers,
        json={"name": "  final-report.txt  "},
    )
    assert rename.status_code == 200, rename.text
    assert rename.json()["name"] == "final-report.txt"
    assert rename.json()["updated_at"] >= fileMeta["updated_at"]

    fetched = api_client.client.get(f"/api/v1/files/{fileMeta['id']}", headers=owner.auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "final-report.txt"
    assert fetched.json()["size_bytes"] == fileMeta["size_bytes"]


def test_move_between_folder_and_root_updates_listings(api_client):
    owner = api_client.register_user("qa-files-move")
    folderResponse = api_client.client.post(
        "/api/v1/folders",
        headers=owner.auth_headers,
        json={"name": f"QA Move {api_client.run_id}", "owner_id": owner.id},
    )
    assert folderResponse.status_code == 201, folderResponse.text
    folderId = folderResponse.json()["id"]
    api_client.created_folders.append(folderId)

    fileMeta = uploadFile(api_client, owner, "movable.txt", b"move me", "text/plain")

    moveIn = api_client.client.put(
        f"/api/v1/files/{fileMeta['id']}/move",
        headers=owner.auth_headers,
        json={"folder_id": folderId},
    )
    assert moveIn.status_code == 200, moveIn.text
    assert moveIn.json()["folder_id"] == folderId
    assert fileMeta["id"] in listFileIds(api_client, owner, folder_id=folderId)

    moveOut = api_client.client.put(
        f"/api/v1/files/{fileMeta['id']}/move",
        headers=owner.auth_headers,
        json={"folder_id": None},
    )
    assert moveOut.status_code == 200, moveOut.text
    assert moveOut.json()["folder_id"] is None
    assert fileMeta["id"] not in listFileIds(api_client, owner, folder_id=folderId)


def test_upload_directly_into_folder(api_client):
    owner = api_client.register_user("qa-files-folder-upload")
    folderResponse = api_client.client.post(
        "/api/v1/folders",
        headers=owner.auth_headers,
        json={"name": f"QA Upload {api_client.run_id}", "owner_id": owner.id},
    )
    assert folderResponse.status_code == 201, folderResponse.text
    folderId = folderResponse.json()["id"]
    api_client.created_folders.append(folderId)

    fileMeta = uploadFile(api_client, owner, "in-folder.txt", b"x", "text/plain", folder_id=folderId)
    assert fileMeta["folder_id"] == folderId
    assert listFileIds(api_client, owner, folder_id=folderId) == [fileMeta["id"]]


def test_trash_hides_file_and_restore_brings_it_back(api_client):
    owner = api_client.register_user("qa-files-trash")
    fileMeta = uploadFile(api_client, owner, "trash-me.txt", b"bye", "text/plain")

    trash = api_client.client.post(f"/api/v1/files/{fileMeta['id']}/trash", headers=owner.auth_headers)
    assert trash.status_code == 200, trash.text
    assert trash.json()["is_trashed"] is True
    assert fileMeta["id"] not in listFileIds(api_client, owner)

    trashList = api_client.client.get("/api/v1/files/trash", headers=owner.auth_headers)
    assert trashList.status_code == 200, trashList.text
    assert fileMeta["id"] in [item["id"] for item in trashList.json()["files"]]

    restore = api_client.client.post(f"/api/v1/files/{fileMeta['id']}/restore", headers=owner.auth_headers)
    assert restore.status_code == 200, restore.text
    assert restore.json()["is_trashed"] is False
    assert fileMeta["id"] in listFileIds(api_client, owner)


def test_permanent_delete_removes_metadata_and_download(api_client):
    owner = api_client.register_user("qa-files-delete")
    fileMeta = uploadFile(api_client, owner, "delete-me.txt", b"gone", "text/plain")

    delete = api_client.client.delete(f"/api/v1/files/{fileMeta['id']}", headers=owner.auth_headers)
    assert delete.status_code == 204, delete.text
    api_client.created_files.remove(fileMeta["id"])

    for path in (f"/api/v1/files/{fileMeta['id']}", f"/api/v1/files/{fileMeta['id']}/download"):
        response = api_client.client.get(path, headers=owner.auth_headers)
        assert response.status_code == 404, path
    assert fileMeta["id"] not in listFileIds(api_client, owner)


def test_list_is_scoped_to_caller_and_paginates(api_client):
    owner = api_client.register_user("qa-files-list")
    other = api_client.register_user("qa-files-list-other")
    ids = [uploadFile(api_client, owner, f"page-{i}.txt", b"p", "text/plain")["id"] for i in range(3)]
    otherId = uploadFile(api_client, other, "other.txt", b"o", "text/plain")["id"]

    ownerIds = listFileIds(api_client, owner)
    assert set(ids) <= set(ownerIds)
    assert otherId not in ownerIds

    pageOne = api_client.client.get(
        "/api/v1/files", headers=owner.auth_headers, params={"page": 1, "page_size": 2}
    ).json()
    pageTwo = api_client.client.get(
        "/api/v1/files", headers=owner.auth_headers, params={"page": 2, "page_size": 2}
    ).json()
    assert pageOne["total"] == 3
    assert len(pageOne["files"]) == 2
    assert len(pageTwo["files"]) == 1
    assert {f["id"] for f in pageOne["files"]} | {f["id"] for f in pageTwo["files"]} == set(ids)
