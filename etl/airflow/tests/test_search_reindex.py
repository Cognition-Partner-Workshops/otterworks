from __future__ import annotations

from unittest import mock

import pytest
from airflow.hooks.base import BaseHook
from airflow.providers.http.hooks.http import HttpHook

from otterworks_etl.search_reindex import (
    DOCUMENT_SETTINGS,
    FILE_SETTINGS,
    MeiliSearch,
    MeiliTaskTimeout,
    batches,
    count_mismatches,
    is_last_page,
    map_document,
    map_file,
    page_items,
    parse_config,
    recreate_index,
    wait_for_task,
)
from tests.search_fakes import MEILI, FakeMeili, FakeUpstream, install

CONFIG = {
    "search_reindex_documents_index": "documents",
    "search_reindex_files_index": "files",
    "search_reindex_api_page_size": "100",
    "search_reindex_bulk_batch_size": "500",
    "search_reindex_task_timeout_seconds": "60",
    "search_reindex_bulk_task_timeout_seconds": "120",
}


def test_map_document_prefers_document_id_and_keeps_legacy_defaults():
    doc = {
        "document_id": "doc-1",
        "id": "ignored",
        "title": "T",
        "content": "C",
        "owner_id": "u",
        "tags": ["a"],
        "created_at": "2026-01-01",
        "updated_at": "2026-01-02",
        "extra_field": "dropped",
    }
    assert map_document(doc) == {
        "id": "doc-1",
        "title": "T",
        "content": "C",
        "owner_id": "u",
        "tags": ["a"],
        "type": "document",
        "created_at": "2026-01-01",
        "updated_at": "2026-01-02",
    }
    assert map_document({"id": "doc-2"})["id"] == "doc-2"
    assert map_document({}) == {
        "id": "",
        "title": "",
        "content": "",
        "owner_id": "",
        "tags": [],
        "type": "document",
        "created_at": None,
        "updated_at": None,
    }


def test_map_document_keeps_explicit_nulls():
    assert map_document({"document_id": None, "id": "x", "tags": None})["id"] is None
    assert map_document({"tags": None})["tags"] is None


def test_map_file_prefers_service_field_names_and_keeps_legacy_defaults():
    f = {"file_id": "f-1", "id": "x", "file_name": "a.pdf", "name": "b", "size_bytes": 7, "size": 1}
    mapped = map_file({**f, "mime_type": "application/pdf", "folder_id": "fo", "tags": ["t"]})
    assert mapped["id"] == "f-1" and mapped["name"] == "a.pdf" and mapped["size"] == 7
    assert mapped["mime_type"] == "application/pdf" and mapped["folder_id"] == "fo"
    alt = map_file({"id": "f-2", "name": "c.txt", "size": 2})
    assert (alt["id"], alt["name"], alt["size"]) == ("f-2", "c.txt", 2)
    assert map_file({}) == {
        "id": "",
        "name": "",
        "owner_id": "",
        "mime_type": "",
        "folder_id": "",
        "size": 0,
        "tags": [],
        "type": "file",
        "created_at": None,
        "updated_at": None,
    }


def test_settings_match_legacy():
    assert DOCUMENT_SETTINGS["searchableAttributes"] == ["title", "content", "tags"]
    assert DOCUMENT_SETTINGS["sortableAttributes"] == ["updated_at", "created_at"]
    assert FILE_SETTINGS["searchableAttributes"] == ["name", "tags", "mime_type"]
    assert FILE_SETTINGS["sortableAttributes"] == ["updated_at", "created_at", "size"]
    assert "folder_id" in FILE_SETTINGS["filterableAttributes"]
    assert DOCUMENT_SETTINGS["rankingRules"] == FILE_SETTINGS["rankingRules"]


def test_page_items_and_paging():
    assert page_items({"documents": [{"a": 1}]}, "documents") == [{"a": 1}]
    assert page_items({"items": [{"b": 2}]}, "documents") == [{"b": 2}]
    assert page_items({}, "files") == [] and page_items({"files": None}, "files") == []
    assert is_last_page([1] * 50, 100) and not is_last_page([1] * 100, 100)


def test_batches():
    assert [len(b) for b in batches([{}] * 250, 100)] == [100, 100, 50]
    assert list(batches([], 10)) == []
    with pytest.raises(ValueError):
        list(batches([{}], 0))


def test_count_mismatches_counts_fetched_records_not_unique_ids():
    assert count_mismatches({"documents": 3, "files": 1}, {"documents": 3, "files": 1}) == []
    assert count_mismatches({"documents": 3, "files": 0}, {"documents": 2, "files": 0}) == [
        "documents: 2 documents, expected 3"
    ]


def test_parse_config():
    config = parse_config(CONFIG)
    assert config.indices == {"documents": "documents", "files": "files"}
    assert (config.api_page_size, config.bulk_batch_size) == (100, 500)
    assert (config.task_timeout, config.bulk_task_timeout) == (60.0, 120.0)
    for key, bad in [
        ("search_reindex_api_page_size", "ten"),
        ("search_reindex_bulk_batch_size", "0"),
        ("search_reindex_task_timeout_seconds", "-1"),
        ("search_reindex_files_index", "documents"),
        ("search_reindex_documents_index", " "),
    ]:
        with pytest.raises(ValueError):
            parse_config({**CONFIG, key: bad})


@pytest.fixture
def meili():
    fake = FakeMeili(polls_until_done=2)
    run = install(fake, FakeUpstream("x", "x", "size"), FakeUpstream("y", "y", "size"))
    conn = mock.Mock(password="secret-key")
    with (
        mock.patch.object(HttpHook, "run", run),
        mock.patch.object(BaseHook, "get_connection", return_value=conn),
        mock.patch("otterworks_etl.search_reindex.meilisearch.time.sleep"),
    ):
        yield fake


def test_wait_for_task_polls_until_terminal(meili):
    client = MeiliSearch(MEILI)
    uid = client.request("POST", "indexes", {"uid": "documents", "primaryKey": "id"}).json()
    task = wait_for_task(client, uid["taskUid"], 60)
    assert task["status"] == "succeeded" and meili.polls[uid["taskUid"]] == 3
    assert meili.headers[-1] == {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret-key",
    }
    assert wait_for_task(client, None, 60) == {"status": "succeeded"}


def test_wait_for_task_times_out(meili):
    meili.polls_until_done = 10**6
    client = MeiliSearch(MEILI)
    uid = client.request("POST", "indexes", {"uid": "files", "primaryKey": "id"}).json()["taskUid"]
    ticks = iter(range(0, 1000, 10))
    with pytest.raises(MeiliTaskTimeout, match="still 'processing' after 30"):
        wait_for_task(client, uid, 30, clock=lambda: next(ticks), sleep=lambda s: None)
    assert meili.polls[uid] == 3


def test_no_api_key_sends_no_authorization(meili):
    with mock.patch.object(BaseHook, "get_connection", return_value=mock.Mock(password="")):
        MeiliSearch(MEILI).request("DELETE", "indexes/documents", check=False)
    assert meili.headers[-1] == {"Content-Type": "application/json"}


def test_recreate_index_treats_a_missing_index_as_expected(meili, caplog):
    with caplog.at_level("INFO"):
        recreate_index(MeiliSearch(MEILI), "documents", DOCUMENT_SETTINGS, 60)
    assert meili.indexes["documents"]["primaryKey"] == "id"
    assert meili.indexes["documents"]["settings"] == DOCUMENT_SETTINGS
    assert "index_did_not_exist" in caplog.text
    assert not [r for r in caplog.records if r.levelname == "WARNING"]


def test_recreate_index_drops_existing_documents(meili):
    client = MeiliSearch(MEILI)
    recreate_index(client, "files", FILE_SETTINGS, 60)
    meili.indexes["files"]["docs"]["f"] = {"id": "f"}
    recreate_index(client, "files", FILE_SETTINGS, 60)
    assert meili.docs("files") == []
    assert [c for c in meili.calls if c[0] != "GET"][-3:] == [
        ("DELETE", "indexes/files"),
        ("POST", "indexes"),
        ("PATCH", "indexes/files/settings"),
    ]
