"""Account-scoped document indexing after an opt-in drive seed."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, call

import pytest
import requests

DRIVE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DRIVE_DIR))

import generate_drive  # noqa: E402


def response(data, status=200):
    result = Mock(status_code=status)
    result.json.return_value = data
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError("request failed")
    return result


def document(identifier="doc-1", owner="owner-1"):
    return {
        "id": identifier, "owner_id": owner, "title": "Existing document",
        "content": "Document body", "is_deleted": False,
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-02T00:00:00Z",
    }


@pytest.fixture
def client():
    client = generate_drive.Client("http://gateway", "demo@example.test", "unused")
    client.owner_id = "owner-1"
    client.token = "test-token"
    client.s = Mock(spec=requests.Session)
    return client


def test_paginated_sweep_indexes_existing_documents_with_duplicate_titles(client):
    docs = [document(), document("doc-2")]
    client.s.get.side_effect = [
        response({"items": [doc], "total": 2}) for doc in docs
    ]
    client.s.post.side_effect = [
        response({"status": "indexed", "id": doc["id"], "type": "document"}, 201)
        for doc in docs
    ]

    assert client.index_documents() == 2
    assert client.s.get.call_args_list == [
        call("http://gateway/api/v1/documents", headers=client.h,
             params={"owner_id": "owner-1", "page": page, "size": 100}, timeout=30)
        for page in (1, 2)
    ]
    assert client.s.post.call_args_list == [
        call("http://gateway/api/v1/search/index/document", headers=client.h,
             json={key: value for key, value in doc.items() if key != "is_deleted"}
             | {"tags": []}, timeout=60)
        for doc in docs
    ]


def test_empty_account_does_not_write(client):
    client.s.get.return_value = response({"items": [], "total": 0})
    assert client.index_documents() == 0
    client.s.post.assert_not_called()


@pytest.mark.parametrize("bad_doc", [
    document("doc-2", "another-owner"),
    {**document("doc-2"), "is_deleted": True},
    document(),
])
def test_entire_sweep_is_validated_before_writes(client, bad_doc):
    client.s.get.side_effect = [
        response({"items": [document()], "total": 2}),
        response({"items": [bad_doc], "total": 2}),
    ]
    with pytest.raises(ValueError):
        client.index_documents()
    client.s.post.assert_not_called()


def test_missing_login_identity_cannot_index(client):
    client.owner_id = None
    client.s.get.return_value = response({"items": [document(owner=None)], "total": 1})
    with pytest.raises(ValueError, match="owner"):
        client.index_documents()
    client.s.post.assert_not_called()


@pytest.mark.parametrize("second_page", [
    {"items": [], "total": 2},
    {"items": [document("doc-2")], "total": 3},
    {"items": [document("doc-2"), document("doc-3")], "total": 2},
])
def test_incomplete_or_changed_pagination_fails_before_writes(client, second_page):
    client.s.get.side_effect = [
        response({"items": [document()], "total": 2}), response(second_page)
    ]
    with pytest.raises(ValueError):
        client.index_documents()
    client.s.post.assert_not_called()


def test_document_read_failure_propagates(client):
    client.s.get.return_value = response({}, 503)
    with pytest.raises(requests.HTTPError):
        client.index_documents()
    client.s.post.assert_not_called()


@pytest.mark.parametrize("status,payload,error", [
    (500, {}, requests.HTTPError),
    (200, {"status": "indexed", "id": "doc-1", "type": "document"}, ValueError),
    (201, {"status": "indexed", "id": "wrong-id", "type": "document"}, ValueError),
])
def test_indexing_failure_propagates(client, status, payload, error):
    client.s.get.return_value = response({"items": [document()], "total": 1})
    client.s.post.return_value = response(payload, status)
    with pytest.raises(error):
        client.index_documents()


@pytest.fixture
def seed(monkeypatch, client):
    monkeypatch.setattr(client, "login", Mock(return_value=client))
    factory = Mock(return_value=client)
    monkeypatch.setattr(generate_drive, "Client", factory)
    monkeypatch.setattr(generate_drive, "FolderCache", Mock())
    monkeypatch.setattr(generate_drive, "run_department", Mock(return_value=(0, 0)))
    monkeypatch.setattr(generate_drive, "upload_assets", Mock(return_value=0))
    index = Mock(return_value=2)
    monkeypatch.setattr(client, "index_documents", index)
    return client, index, [
        "--gateway", "http://gateway", "--email", "demo@example.test", "--password", "unused"
    ]


@pytest.mark.parametrize("enabled", [False, True])
def test_seed_indexes_only_when_opted_in_even_without_new_documents(seed, capsys, enabled):
    client, index, args = seed
    assert generate_drive.main(args + (["--index-documents"] if enabled else [])) == 0
    assert index.call_count == int(enabled)
    output = capsys.readouterr().out
    assert ("indexed documents=2" in output) == enabled
    if enabled:
        assert output.index("indexed documents=2") < output.index("DONE")


def test_dry_run_never_indexes(seed):
    _, index, args = seed
    assert generate_drive.main(args + ["--dry-run", "--index-documents"]) == 0
    index.assert_not_called()


def test_failed_seed_never_indexes(seed, monkeypatch):
    _, index, args = seed
    monkeypatch.setattr(generate_drive, "upload_assets", Mock(side_effect=RuntimeError("failed")))
    with pytest.raises(RuntimeError):
        generate_drive.main(args + ["--index-documents"])
    index.assert_not_called()


def test_index_failure_fails_seed_without_success_message(seed, capsys):
    _, index, args = seed
    index.side_effect = requests.HTTPError("index failed")
    with pytest.raises(requests.HTTPError):
        generate_drive.main(args + ["--index-documents"])
    assert "DONE" not in capsys.readouterr().out


@pytest.mark.parametrize("opt_in", [None, "false", "true"])
def test_seed_job_flag_is_opt_in_and_preserves_runtime_arguments(tmp_path, opt_in):
    config_dir = tmp_path / "testdata/generated/retail-drive"
    config_dir.mkdir(parents=True)
    (config_dir / "tenant-seed.conf").write_text(
        "SEED_BRANCH=demo-example\nSEED_PROFILE=retail\nDRIVE_EMAIL=demo@example.test\n"
        "DRIVE_PASSWORD=unused-test-value\nSEED_SCALE=1.0\n"
    )
    if opt_in is not None:
        (config_dir / "tenant-seed-search.conf").write_text(f"SEED_INDEX_DOCUMENTS={opt_in}\n")
    source = (DRIVE_DIR.parents[2] / "scripts/deploy-tenant.sh").read_text()
    function = "seed_drive() {" + source.split("seed_drive() {", 1)[1].split("\nseed_drive\n", 1)[0]
    harness = """
set -eu
REPO_ROOT=$1
TENANT_BRANCH_ARG=$2
NS=fixture
log() { :; }
warn() { printf '%s\\n' "$*" >&2; }
tar() { printf archive; }
kubectl() {
  if [ "$3" = apply ]; then
    cat
  fi
}
""" + function + "\nseed_drive\n"
    result = subprocess.run(["bash", "-c", harness, "fixture", str(tmp_path), "demo-example"],
                            capture_output=True, text=True, check=True)
    assert f'value: "{opt_in or "false"}"' in result.stdout
    assert '"$@"' in result.stdout
    result = subprocess.run(["bash", "-c", harness, "fixture", str(tmp_path), "another-branch"],
                            capture_output=True, text=True, check=True)
    assert result.stdout == ""

    flags = source.split("              set --\n", 1)[1].split(
        "              /work/venv/bin/python", 1)[0].replace("\\$", "$")
    result = subprocess.run([
        "bash", "-c", 'SEED_INDEX_DOCUMENTS=$1; set --;\n' + flags + '\nprintf "%s" "$*"',
        "fixture", opt_in or "false",
    ], capture_output=True, text=True, check=True)
    assert result.stdout == ("--index-documents" if opt_in == "true" else "")
