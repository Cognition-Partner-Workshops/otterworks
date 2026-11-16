import os
import uuid

import httpx
import pytest


pytestmark = pytest.mark.api_flow


def test_file_folder_upload_lifecycle_share_and_download(api_client):
    owner = api_client.register_user("file-owner")
    collaborator = api_client.register_user("file-collaborator")

    folder_response = api_client.client.post(
        "/api/v1/folders",
        headers=owner.auth_headers,
        json={"name": f"Flow Folder {api_client.run_id}", "owner_id": owner.id},
    )
    api_client.assert_gateway_route_available(folder_response, "/api/v1/folders")
    assert folder_response.status_code == 201, folder_response.text
    folder = folder_response.json()
    api_client.created_folders.append(folder["id"])

    upload_response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("flow.txt", b"hello file flow", "text/plain")},
        data={"folder_id": folder["id"]},
    )
    assert upload_response.status_code == 201, upload_response.text
    file_metadata = upload_response.json()["file"]
    file_id = file_metadata["id"]
    api_client.created_files.append(file_id)
    assert file_metadata["owner_id"] == owner.id
    assert file_metadata["folder_id"] == folder["id"]
    assert file_metadata["version"] == 1

    list_response = api_client.client.get(
        "/api/v1/files",
        headers=owner.auth_headers,
        params={"owner_id": owner.id, "page": 1, "page_size": 10},
    )
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == file_id for item in list_response.json()["files"])

    get_response = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["id"] == file_id

    download_response = api_client.client.get(
        f"/api/v1/files/{file_id}/download",
        headers=owner.auth_headers,
    )
    assert download_response.status_code == 200, download_response.text
    assert download_response.json()["url"]

    versions_response = api_client.client.get(
        f"/api/v1/files/{file_id}/versions",
        headers=owner.auth_headers,
    )
    assert versions_response.status_code == 200, versions_response.text
    assert versions_response.json()["versions"][0]["version"] == 1

    share_response = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=owner.auth_headers,
        json={
            "shared_with": collaborator.id,
            "permission": "viewer",
            "shared_by": owner.id,
        },
    )
    assert share_response.status_code == 201, share_response.text
    assert share_response.json()["share"]["shared_with"] == collaborator.id

    trash_response = api_client.client.post(f"/api/v1/files/{file_id}/trash", headers=owner.auth_headers)
    assert trash_response.status_code == 200, trash_response.text
    assert trash_response.json()["is_trashed"] is True

    restore_response = api_client.client.post(f"/api/v1/files/{file_id}/restore", headers=owner.auth_headers)
    assert restore_response.status_code == 200, restore_response.text
    assert restore_response.json()["is_trashed"] is False

    move_response = api_client.client.put(
        f"/api/v1/files/{file_id}/move",
        headers=owner.auth_headers,
        json={"folder_id": None},
    )
    assert move_response.status_code == 200, move_response.text
    assert move_response.json()["folder_id"] is None

    delete_file_response = api_client.client.delete(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert delete_file_response.status_code == 204, delete_file_response.text
    api_client.created_files.remove(file_id)

    deleted_get_response = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert deleted_get_response.status_code == 404

    delete_folder_response = api_client.client.delete(
        f"/api/v1/folders/{folder['id']}",
        headers=owner.auth_headers,
    )
    assert delete_folder_response.status_code == 204, delete_folder_response.text
    api_client.created_folders.remove(folder["id"])


@pytest.mark.gap_revealer
def test_file_validation_and_route_gaps(api_client):
    owner = api_client.register_user("file-validation")

    empty_upload_response = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert empty_upload_response.status_code in {400, 422}

    missing_owner_upload = api_client.client.post(
        "/api/v1/files/upload",
        files={"file": ("no-owner.txt", b"body", "text/plain")},
    )
    assert missing_owner_upload.status_code in {400, 401, 403}

    invalid_file_id = api_client.client.get("/api/v1/files/not-a-uuid", headers=owner.auth_headers)
    assert invalid_file_id.status_code in {400, 422}

    folder_route_response = api_client.client.post(
        "/api/v1/folders",
        headers=owner.auth_headers,
        json={"name": "route probe", "owner_id": owner.id},
    )
    api_client.assert_gateway_route_available(folder_route_response, "/api/v1/folders")


def unknown_id() -> str:
    return str(uuid.uuid4())


def list_file_ids(api_client, user, **params) -> list[str]:
    response = api_client.client.get("/api/v1/files", headers=user.auth_headers, params=params)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["files"]]


def list_shared_ids(api_client, user) -> list[str]:
    response = api_client.client.get("/api/v1/files/shared", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["files"]]


def list_trash_ids(api_client, user, **params) -> list[str]:
    response = api_client.client.get("/api/v1/files/trash", headers=user.auth_headers, params=params)
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["files"]]


def test_file_upload_records_metadata_and_binds_owner_to_caller(api_client):
    owner = api_client.register_user("file-meta-owner")
    other = api_client.register_user("file-meta-other")
    content = os.urandom(2048)

    file_metadata = api_client.upload_file(
        owner,
        "report.bin",
        content,
        content_type="application/octet-stream",
        extra_fields={"owner_id": other.id},
    )

    assert file_metadata["owner_id"] == owner.id
    assert file_metadata["name"] == "report.bin"
    assert file_metadata["mime_type"] == "application/octet-stream"
    assert file_metadata["size_bytes"] == len(content)
    assert file_metadata["version"] == 1
    assert file_metadata["is_trashed"] is False
    assert file_metadata["folder_id"] is None
    assert "s3_key" in file_metadata

    detail_response = api_client.client.get(
        f"/api/v1/files/{file_metadata['id']}",
        headers=owner.auth_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert detail["owner_id"] == owner.id
    assert detail["size_bytes"] == len(content)
    assert detail["shared_with"] == []

    versions_response = api_client.client.get(
        f"/api/v1/files/{file_metadata['id']}/versions",
        headers=owner.auth_headers,
    )
    assert versions_response.status_code == 200, versions_response.text
    versions = versions_response.json()["versions"]
    assert len(versions) == 1
    assert versions[0]["created_by"] == owner.id
    assert versions[0]["size_bytes"] == len(content)

    assert file_metadata["id"] in list_file_ids(api_client, owner)
    assert file_metadata["id"] not in list_file_ids(api_client, other)


def test_file_download_url_serves_uploaded_bytes(api_client):
    owner = api_client.register_user("file-download")
    content = os.urandom(4096)
    file_metadata = api_client.upload_file(owner, "payload.bin", content, "application/octet-stream")

    download_response = api_client.client.get(
        f"/api/v1/files/{file_metadata['id']}/download",
        headers=owner.auth_headers,
    )
    assert download_response.status_code == 200, download_response.text
    body = download_response.json()
    assert body["expires_in_secs"] == 3600
    assert f"files/{owner.id}/{file_metadata['id']}" in body["url"]

    try:
        blob_response = httpx.get(body["url"], timeout=10.0)
    except httpx.HTTPError as exc:
        pytest.skip(f"presigned object-store URL is not reachable from the test runner: {exc}")
    assert blob_response.status_code == 200, blob_response.text
    assert blob_response.content == content


def test_file_rename_updates_metadata_and_rejects_blank_names(api_client):
    owner = api_client.register_user("file-rename")
    file_metadata = api_client.upload_file(owner, "draft.txt", b"rename me")
    file_id = file_metadata["id"]

    rename_response = api_client.client.patch(
        f"/api/v1/files/{file_id}/rename",
        headers=owner.auth_headers,
        json={"name": "  final.txt  "},
    )
    assert rename_response.status_code == 200, rename_response.text
    assert rename_response.json()["name"] == "final.txt"

    get_response = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["name"] == "final.txt"

    for blank_name in ("", "   "):
        blank_response = api_client.client.patch(
            f"/api/v1/files/{file_id}/rename",
            headers=owner.auth_headers,
            json={"name": blank_name},
        )
        assert blank_response.status_code == 400, blank_response.text
        api_client.assert_json_error(blank_response)

    missing_body_response = api_client.client.patch(
        f"/api/v1/files/{file_id}/rename",
        headers=owner.auth_headers,
        json={},
    )
    assert missing_body_response.status_code in {400, 422}

    unchanged_response = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert unchanged_response.json()["name"] == "final.txt"


def test_file_trash_and_restore_drive_listing_visibility(api_client):
    owner = api_client.register_user("file-trash")
    kept = api_client.upload_file(owner, "kept.txt", b"kept")
    trashed = api_client.upload_file(owner, "trashed.txt", b"trashed")

    trash_response = api_client.client.post(
        f"/api/v1/files/{trashed['id']}/trash",
        headers=owner.auth_headers,
    )
    assert trash_response.status_code == 200, trash_response.text
    assert trash_response.json()["is_trashed"] is True

    active_ids = list_file_ids(api_client, owner)
    assert kept["id"] in active_ids
    assert trashed["id"] not in active_ids

    all_ids = list_file_ids(api_client, owner, include_trashed="true")
    assert {kept["id"], trashed["id"]} <= set(all_ids)

    trash_ids = list_trash_ids(api_client, owner)
    assert trashed["id"] in trash_ids
    assert kept["id"] not in trash_ids

    get_response = api_client.client.get(f"/api/v1/files/{trashed['id']}", headers=owner.auth_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["is_trashed"] is True

    restore_response = api_client.client.post(
        f"/api/v1/files/{trashed['id']}/restore",
        headers=owner.auth_headers,
    )
    assert restore_response.status_code == 200, restore_response.text
    assert restore_response.json()["is_trashed"] is False

    assert trashed["id"] in list_file_ids(api_client, owner)
    assert trashed["id"] not in list_trash_ids(api_client, owner)


def test_file_listing_filters_by_folder_and_paginates(api_client):
    owner = api_client.register_user("file-pagination")
    folder = api_client.create_folder(owner, f"Paged {api_client.run_id}")
    in_folder = [
        api_client.upload_file(owner, f"page-{index}.txt", f"page {index}".encode(), folder_id=folder["id"])
        for index in range(3)
    ]
    at_root = api_client.upload_file(owner, "root.txt", b"root")

    folder_ids = list_file_ids(api_client, owner, folder_id=folder["id"])
    assert sorted(folder_ids) == sorted(item["id"] for item in in_folder)

    first_page = api_client.client.get(
        "/api/v1/files",
        headers=owner.auth_headers,
        params={"folder_id": folder["id"], "page": 1, "page_size": 2},
    )
    assert first_page.status_code == 200, first_page.text
    first_body = first_page.json()
    assert first_body["total"] == 3
    assert first_body["page"] == 1
    assert first_body["page_size"] == 2
    assert len(first_body["files"]) == 2

    second_page = api_client.client.get(
        "/api/v1/files",
        headers=owner.auth_headers,
        params={"folder_id": folder["id"], "page": 2, "page_size": 2},
    )
    assert second_page.status_code == 200, second_page.text
    second_body = second_page.json()
    assert len(second_body["files"]) == 1
    paged_ids = [item["id"] for item in first_body["files"] + second_body["files"]]
    assert sorted(paged_ids) == sorted(folder_ids)

    oversized_page = api_client.client.get(
        "/api/v1/files",
        headers=owner.auth_headers,
        params={"page": 1, "page_size": 1000},
    )
    assert oversized_page.status_code == 200, oversized_page.text
    assert oversized_page.json()["page_size"] == 100

    move_response = api_client.client.put(
        f"/api/v1/files/{at_root['id']}/move",
        headers=owner.auth_headers,
        json={"folder_id": folder["id"]},
    )
    assert move_response.status_code == 200, move_response.text
    assert move_response.json()["folder_id"] == folder["id"]
    assert at_root["id"] in list_file_ids(api_client, owner, folder_id=folder["id"])


def test_file_and_folder_listings_ignore_spoofed_owner_query(api_client):
    victim = api_client.register_user("file-list-victim")
    attacker = api_client.register_user("file-list-attacker")
    victim_folder = api_client.create_folder(victim, f"Victim {api_client.run_id}")
    victim_file = api_client.upload_file(victim, "secret.txt", b"victim data")
    victim_trashed = api_client.upload_file(victim, "secret-trash.txt", b"victim trash")
    trash_response = api_client.client.post(
        f"/api/v1/files/{victim_trashed['id']}/trash",
        headers=victim.auth_headers,
    )
    assert trash_response.status_code == 200, trash_response.text

    spoofed_files = list_file_ids(api_client, attacker, owner_id=victim.id, include_trashed="true")
    assert victim_file["id"] not in spoofed_files
    assert victim_trashed["id"] not in spoofed_files

    assert victim_trashed["id"] not in list_trash_ids(api_client, attacker, owner_id=victim.id)

    folders_response = api_client.client.get(
        "/api/v1/folders",
        headers=attacker.auth_headers,
        params={"owner_id": victim.id},
    )
    assert folders_response.status_code == 200, folders_response.text
    assert victim_folder["id"] not in [item["id"] for item in folders_response.json()["folders"]]

    activity_response = api_client.client.get("/api/v1/files/activity", headers=attacker.auth_headers)
    assert activity_response.status_code == 200, activity_response.text
    assert victim_file["id"] not in [item["resource_id"] for item in activity_response.json()["items"]]


def test_file_share_lifecycle_for_recipient(api_client):
    owner = api_client.register_user("file-share-owner")
    recipient = api_client.register_user("file-share-recipient")
    file_metadata = api_client.upload_file(owner, "shared.txt", b"shared body")
    file_id = file_metadata["id"]
    share_url = f"/api/v1/files/{file_id}/share"

    assert file_id not in list_shared_ids(api_client, recipient)

    share_response = api_client.client.post(
        share_url,
        headers=owner.auth_headers,
        json={"shared_with": recipient.id, "permission": "viewer", "shared_by": owner.id},
    )
    assert share_response.status_code == 201, share_response.text
    share = share_response.json()["share"]
    assert share["permission"] == "viewer"
    assert share["file_id"] == file_id

    assert list_shared_ids(api_client, recipient).count(file_id) == 1
    assert file_id not in list_shared_ids(api_client, owner)

    detail_response = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert detail_response.status_code == 200, detail_response.text
    assert [entry["shared_with"] for entry in detail_response.json()["shared_with"]] == [recipient.id]

    repeat_response = api_client.client.post(
        share_url,
        headers=owner.auth_headers,
        json={"shared_with": recipient.id, "permission": "viewer", "shared_by": owner.id},
    )
    assert repeat_response.status_code == 200, repeat_response.text
    assert repeat_response.json()["share"]["id"] == share["id"]

    upgrade_response = api_client.client.post(
        share_url,
        headers=owner.auth_headers,
        json={"shared_with": recipient.id, "permission": "editor", "shared_by": owner.id},
    )
    assert upgrade_response.status_code == 200, upgrade_response.text
    upgraded = upgrade_response.json()["share"]
    assert upgraded["id"] == share["id"]
    assert upgraded["permission"] == "editor"
    assert list_shared_ids(api_client, recipient).count(file_id) == 1

    invalid_permission_response = api_client.client.post(
        share_url,
        headers=owner.auth_headers,
        json={"shared_with": recipient.id, "permission": "owner", "shared_by": owner.id},
    )
    assert invalid_permission_response.status_code in {400, 422}

    trash_response = api_client.client.post(f"/api/v1/files/{file_id}/trash", headers=owner.auth_headers)
    assert trash_response.status_code == 200, trash_response.text
    assert file_id not in list_shared_ids(api_client, recipient)

    restore_response = api_client.client.post(f"/api/v1/files/{file_id}/restore", headers=owner.auth_headers)
    assert restore_response.status_code == 200, restore_response.text
    assert file_id in list_shared_ids(api_client, recipient)

    unshare_url = f"/api/v1/files/{file_id}/share/{recipient.id}"
    unshare_response = api_client.client.delete(unshare_url, headers=owner.auth_headers)
    assert unshare_response.status_code == 204, unshare_response.text
    assert file_id not in list_shared_ids(api_client, recipient)

    detail_after_unshare = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert detail_after_unshare.json()["shared_with"] == []

    repeat_unshare_response = api_client.client.delete(unshare_url, headers=owner.auth_headers)
    assert repeat_unshare_response.status_code == 404
    api_client.assert_json_error(repeat_unshare_response)


def test_deleted_file_disappears_from_recipient_shared_list(api_client):
    owner = api_client.register_user("file-delete-share-owner")
    recipient = api_client.register_user("file-delete-share-recipient")
    file_metadata = api_client.upload_file(owner, "ephemeral.txt", b"short lived")
    file_id = file_metadata["id"]

    share_response = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=owner.auth_headers,
        json={"shared_with": recipient.id, "permission": "viewer", "shared_by": owner.id},
    )
    assert share_response.status_code == 201, share_response.text
    assert file_id in list_shared_ids(api_client, recipient)

    delete_response = api_client.client.delete(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert delete_response.status_code == 204, delete_response.text
    api_client.created_files.remove(file_id)

    assert file_id not in list_shared_ids(api_client, recipient)
    for path in (f"/api/v1/files/{file_id}", f"/api/v1/files/{file_id}/download"):
        response = api_client.client.get(path, headers=owner.auth_headers)
        assert response.status_code == 404, f"{path}: {response.text}"

    repeat_delete_response = api_client.client.delete(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert repeat_delete_response.status_code == 404


def test_file_activity_feed_reports_uploads_and_shares(api_client):
    owner = api_client.register_user("file-activity-owner")
    recipient = api_client.register_user("file-activity-recipient")
    first = api_client.upload_file(owner, "first.txt", b"first")
    second = api_client.upload_file(owner, "second.txt", b"second")

    share_response = api_client.client.post(
        f"/api/v1/files/{first['id']}/share",
        headers=owner.auth_headers,
        json={"shared_with": recipient.id, "permission": "viewer", "shared_by": owner.id},
    )
    assert share_response.status_code == 201, share_response.text
    share_id = share_response.json()["share"]["id"]

    activity_response = api_client.client.get("/api/v1/files/activity", headers=owner.auth_headers)
    assert activity_response.status_code == 200, activity_response.text
    items = activity_response.json()["items"]
    item_ids = {item["id"] for item in items}
    assert {f"upload-{first['id']}", f"upload-{second['id']}", f"share-{share_id}"} <= item_ids

    share_item = next(item for item in items if item["id"] == f"share-{share_id}")
    assert share_item["type"] == "share"
    assert share_item["resource_id"] == first["id"]
    assert share_item["resource_name"] == "first.txt"

    timestamps = [item["created_at"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True)

    limited_response = api_client.client.get(
        "/api/v1/files/activity",
        headers=owner.auth_headers,
        params={"limit": 1},
    )
    assert limited_response.status_code == 200, limited_response.text
    assert len(limited_response.json()["items"]) == 1

    recipient_activity = api_client.client.get("/api/v1/files/activity", headers=recipient.auth_headers)
    assert recipient_activity.status_code == 200, recipient_activity.text
    assert recipient_activity.json()["items"] == []


def test_folder_crud_and_nesting(api_client):
    owner = api_client.register_user("folder-crud")
    parent = api_client.create_folder(owner, f"Parent {api_client.run_id}")
    child = api_client.create_folder(owner, f"Child {api_client.run_id}", parent_id=parent["id"])
    assert parent["owner_id"] == owner.id
    assert parent["parent_id"] is None
    assert child["parent_id"] == parent["id"]

    get_response = api_client.client.get(f"/api/v1/folders/{child['id']}", headers=owner.auth_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["name"] == child["name"]

    root_response = api_client.client.get("/api/v1/folders", headers=owner.auth_headers)
    assert root_response.status_code == 200, root_response.text
    root_ids = [item["id"] for item in root_response.json()["folders"]]
    assert parent["id"] in root_ids
    assert child["id"] not in root_ids

    nested_response = api_client.client.get(
        "/api/v1/folders",
        headers=owner.auth_headers,
        params={"parent_id": parent["id"]},
    )
    assert nested_response.status_code == 200, nested_response.text
    assert [item["id"] for item in nested_response.json()["folders"]] == [child["id"]]

    rename_response = api_client.client.put(
        f"/api/v1/folders/{child['id']}",
        headers=owner.auth_headers,
        json={"name": "Renamed Child"},
    )
    assert rename_response.status_code == 200, rename_response.text
    renamed = rename_response.json()
    assert renamed["name"] == "Renamed Child"
    assert renamed["parent_id"] == parent["id"]

    delete_response = api_client.client.delete(f"/api/v1/folders/{child['id']}", headers=owner.auth_headers)
    assert delete_response.status_code == 204, delete_response.text
    api_client.created_folders.remove(child["id"])

    deleted_get_response = api_client.client.get(f"/api/v1/folders/{child['id']}", headers=owner.auth_headers)
    assert deleted_get_response.status_code == 404
    api_client.assert_json_error(deleted_get_response)

    update_deleted_response = api_client.client.put(
        f"/api/v1/folders/{child['id']}",
        headers=owner.auth_headers,
        json={"name": "ghost"},
    )
    assert update_deleted_response.status_code == 404


def test_file_and_folder_routes_return_json_errors_for_unknown_and_malformed_ids(api_client):
    owner = api_client.register_user("file-unknown-ids")
    missing_id = unknown_id()
    share_body = {"shared_with": owner.id, "permission": "viewer", "shared_by": owner.id}

    not_found_requests = [
        ("GET", f"/api/v1/files/{missing_id}", None),
        ("GET", f"/api/v1/files/{missing_id}/download", None),
        ("DELETE", f"/api/v1/files/{missing_id}", None),
        ("POST", f"/api/v1/files/{missing_id}/trash", None),
        ("POST", f"/api/v1/files/{missing_id}/restore", None),
        ("PATCH", f"/api/v1/files/{missing_id}/rename", {"name": "ghost.txt"}),
        ("PUT", f"/api/v1/files/{missing_id}/move", {"folder_id": None}),
        ("POST", f"/api/v1/files/{missing_id}/share", share_body),
        ("DELETE", f"/api/v1/files/{missing_id}/share/{owner.id}", None),
        ("GET", f"/api/v1/folders/{missing_id}", None),
        ("PUT", f"/api/v1/folders/{missing_id}", {"name": "ghost"}),
    ]
    for method, path, body in not_found_requests:
        response = api_client.client.request(method, path, headers=owner.auth_headers, json=body)
        assert response.status_code == 404, f"{method} {path}: {response.status_code} {response.text}"
        api_client.assert_json_error(response)

    malformed_requests = [
        ("GET", "/api/v1/files/not-a-uuid/download", None),
        ("DELETE", "/api/v1/files/not-a-uuid", None),
        ("POST", "/api/v1/files/not-a-uuid/trash", None),
        ("PATCH", "/api/v1/files/not-a-uuid/rename", {"name": "x.txt"}),
        ("DELETE", f"/api/v1/files/{missing_id}/share/not-a-uuid", None),
        ("GET", "/api/v1/folders/not-a-uuid", None),
    ]
    for method, path, body in malformed_requests:
        response = api_client.client.request(method, path, headers=owner.auth_headers, json=body)
        assert response.status_code == 400, f"{method} {path}: {response.status_code} {response.text}"
        api_client.assert_json_error(response)

    invalid_folder_upload = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": ("bad-folder.txt", b"body", "text/plain")},
        data={"folder_id": "not-a-uuid"},
    )
    assert invalid_folder_upload.status_code == 400, invalid_folder_upload.text
    api_client.assert_json_error(invalid_folder_upload)


def test_file_routes_require_authentication(api_client):
    owner = api_client.register_user("file-unauthenticated")
    file_metadata = api_client.upload_file(owner, "guarded.txt", b"guarded")
    file_id = file_metadata["id"]
    bad_token_headers = {"Authorization": "Bearer not-a-real-token"}

    unauthenticated_requests = [
        ("GET", "/api/v1/files", None),
        ("GET", f"/api/v1/files/{file_id}", None),
        ("GET", f"/api/v1/files/{file_id}/download", None),
        ("GET", "/api/v1/files/shared", None),
        ("GET", "/api/v1/files/trash", None),
        ("GET", "/api/v1/files/activity", None),
        ("DELETE", f"/api/v1/files/{file_id}", None),
        ("POST", f"/api/v1/files/{file_id}/trash", None),
        ("PATCH", f"/api/v1/files/{file_id}/rename", {"name": "pwned.txt"}),
        ("GET", "/api/v1/folders", None),
    ]
    for headers in ({}, bad_token_headers):
        for method, path, body in unauthenticated_requests:
            response = api_client.client.request(method, path, headers=headers, json=body)
            assert response.status_code == 401, f"{method} {path} headers={list(headers)}: {response.text}"

    get_response = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["name"] == "guarded.txt"
    assert get_response.json()["is_trashed"] is False


@pytest.mark.gap_revealer
def test_file_cross_owner_access_is_denied(api_client):
    owner = api_client.register_user("file-bola-owner")
    intruder = api_client.register_user("file-bola-intruder")
    file_metadata = api_client.upload_file(owner, "private.txt", b"owner only")
    file_id = file_metadata["id"]

    intrusion_requests = [
        ("GET", f"/api/v1/files/{file_id}", None),
        ("GET", f"/api/v1/files/{file_id}/download", None),
        ("GET", f"/api/v1/files/{file_id}/versions", None),
        ("PATCH", f"/api/v1/files/{file_id}/rename", {"name": "pwned.txt"}),
        ("PUT", f"/api/v1/files/{file_id}/move", {"folder_id": unknown_id()}),
        ("POST", f"/api/v1/files/{file_id}/share", {
            "shared_with": intruder.id,
            "permission": "editor",
            "shared_by": owner.id,
        }),
        ("POST", f"/api/v1/files/{file_id}/trash", None),
        ("POST", f"/api/v1/files/{file_id}/restore", None),
        ("DELETE", f"/api/v1/files/{file_id}", None),
    ]
    leaks = []
    for method, path, body in intrusion_requests:
        response = api_client.client.request(method, path, headers=intruder.auth_headers, json=body)
        if response.status_code not in {403, 404}:
            leaks.append(f"{method} {path} -> {response.status_code}")

    owner_view = api_client.client.get(f"/api/v1/files/{file_id}", headers=owner.auth_headers)
    if owner_view.status_code != 200:
        leaks.append(f"owner lost access to the file: {owner_view.status_code}")
    else:
        state = owner_view.json()
        if state["name"] != "private.txt" or state["folder_id"] is not None or state["shared_with"]:
            leaks.append(f"intruder mutated the file: {state}")

    assert not leaks, "cross-owner access was not denied:\n" + "\n".join(leaks)


@pytest.mark.gap_revealer
def test_share_permissions_are_enforced_for_recipients(api_client):
    owner = api_client.register_user("file-perm-owner")
    viewer = api_client.register_user("file-perm-viewer")
    bystander = api_client.register_user("file-perm-bystander")
    file_metadata = api_client.upload_file(owner, "viewable.txt", b"read only")
    file_id = file_metadata["id"]

    share_response = api_client.client.post(
        f"/api/v1/files/{file_id}/share",
        headers=owner.auth_headers,
        json={"shared_with": viewer.id, "permission": "viewer", "shared_by": bystander.id},
    )
    assert share_response.status_code == 201, share_response.text
    violations = []
    recorded_sharer = share_response.json()["share"]["shared_by"]
    if recorded_sharer != owner.id:
        violations.append(f"shared_by taken from the request body instead of the caller: {recorded_sharer}")

    for path in (f"/api/v1/files/{file_id}", f"/api/v1/files/{file_id}/download"):
        response = api_client.client.get(path, headers=viewer.auth_headers)
        assert response.status_code == 200, f"viewer should read {path}: {response.text}"

    forbidden_requests = [
        ("PATCH", f"/api/v1/files/{file_id}/rename", {"name": "viewer-edit.txt"}),
        ("POST", f"/api/v1/files/{file_id}/share", {
            "shared_with": bystander.id,
            "permission": "editor",
            "shared_by": viewer.id,
        }),
        ("POST", f"/api/v1/files/{file_id}/trash", None),
        ("DELETE", f"/api/v1/files/{file_id}", None),
    ]
    for method, path, body in forbidden_requests:
        response = api_client.client.request(method, path, headers=viewer.auth_headers, json=body)
        if response.status_code != 403:
            violations.append(f"{method} {path} -> {response.status_code}")
    assert not violations, "viewer exceeded share permission:\n" + "\n".join(violations)


@pytest.mark.gap_revealer
def test_folder_ownership_is_enforced(api_client):
    owner = api_client.register_user("folder-bola-owner")
    intruder = api_client.register_user("folder-bola-intruder")
    folder = api_client.create_folder(owner, f"Owner Folder {api_client.run_id}")

    spoofed_response = api_client.client.post(
        "/api/v1/folders",
        headers=intruder.auth_headers,
        json={"name": "planted", "owner_id": owner.id},
    )
    violations = []
    if spoofed_response.status_code == 201:
        spoofed = spoofed_response.json()
        api_client.created_folders.append(spoofed["id"])
        api_client.resource_headers[spoofed["id"]] = intruder.auth_headers
        if spoofed["owner_id"] != intruder.id:
            violations.append(f"folder created on behalf of another owner: {spoofed['owner_id']}")

    intrusion_requests = [
        ("GET", f"/api/v1/folders/{folder['id']}", None),
        ("PUT", f"/api/v1/folders/{folder['id']}", {"name": "pwned"}),
        ("DELETE", f"/api/v1/folders/{folder['id']}", None),
    ]
    for method, path, body in intrusion_requests:
        response = api_client.client.request(method, path, headers=intruder.auth_headers, json=body)
        if response.status_code not in {403, 404}:
            violations.append(f"{method} {path} -> {response.status_code}")

    foreign_folder_upload = api_client.client.post(
        "/api/v1/files/upload",
        headers=intruder.auth_headers,
        files={"file": ("dropped.txt", b"dropped", "text/plain")},
        data={"folder_id": folder["id"]},
    )
    if foreign_folder_upload.status_code == 201:
        dropped_id = foreign_folder_upload.json()["file"]["id"]
        api_client.created_files.append(dropped_id)
        api_client.resource_headers[dropped_id] = intruder.auth_headers
        violations.append("upload into another owner's folder was accepted")

    assert not violations, "folder ownership was not enforced:\n" + "\n".join(violations)
