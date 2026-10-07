from __future__ import annotations

import ast
from types import SimpleNamespace
from unittest import mock

import pytest
from airflow.exceptions import AirflowException, AirflowFailException
from airflow.hooks.base import BaseHook
from airflow.models import Variable
from airflow.providers.http.hooks.http import HttpHook

from tests.conftest import AIRFLOW_ROOT, DAGS_FOLDER
from tests.search_fakes import FakeMeili, FakeUpstream, install
from tests.test_search_reindex import CONFIG

DAG_ID = "otterworks_search_reindex"
DAG_FILE = DAGS_FOLDER / f"{DAG_ID}.py"
PACKAGE = AIRFLOW_ROOT / "otterworks_etl" / "search_reindex"


def _doc(i, **extra):
    return {"document_id": "doc-%03d" % i, "title": "Doc %d" % i, "owner_id": "u", **extra}


def _file(i, **extra):
    return {"file_id": "file-%03d" % i, "file_name": "f%d.pdf" % i, "size_bytes": i, **extra}


def test_task_graph_and_schedule(dagbag):
    dag = dagbag.dags[DAG_ID]
    assert dag.schedule_interval == "0 4 * * 0"
    down = {t.task_id: set(t.downstream_task_ids) for t in dag.tasks}
    assert down == {
        "clear_indices": {"fetch_and_index_documents", "fetch_and_index_files"},
        "fetch_and_index_documents": {"validate_indices"},
        "fetch_and_index_files": {"validate_indices"},
        "validate_indices": set(),
    }
    assert {"search", "otterworks"} <= set(dag.tags)


def test_uses_http_hook_only():
    sources = [DAG_FILE, *sorted(PACKAGE.glob("*.py"))]
    for path in sources:
        tree = ast.parse(path.read_text())
        imported = {
            alias.name if isinstance(node, ast.Import) else (node.module or "")
            for node in ast.walk(tree)
            if isinstance(node, ast.Import | ast.ImportFrom)
            for alias in node.names
        }
        assert not {m for m in imported if m.split(".")[0] in {"requests", "urllib3", "httpx"}}
    assert "HttpHook(" in (PACKAGE / "meilisearch.py").read_text()
    assert "HttpHook(" in (PACKAGE / "reindex.py").read_text()


class Env:
    def __init__(self, dagbag, documents=(), files=(), doc_errors=None, **variables):
        self.dag = dagbag.dags[DAG_ID]
        self.meili = FakeMeili()
        self.documents = FakeUpstream(
            "api/v1/documents", "documents", "size", documents, doc_errors
        )
        self.files = FakeUpstream("api/v1/files", "files", "page_size", files)
        self.variables = {**CONFIG, **{k: str(v) for k, v in variables.items()}}
        self.variable_reads: list[str] = []

    def _variable(self, key, default_var=None, deserialize_json=False):
        self.variable_reads.append(key)
        return self.variables[key]

    def __enter__(self):
        self.patches = [
            mock.patch.object(Variable, "get", side_effect=self._variable),
            mock.patch.object(HttpHook, "run", install(self.meili, self.documents, self.files)),
            mock.patch.object(
                BaseHook, "get_connection", return_value=SimpleNamespace(password="k")
            ),
            mock.patch("otterworks_etl.search_reindex.meilisearch.time.sleep", lambda s: None),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()

    def call(self, task_id, *args, try_number=1):
        task = self.dag.get_task(task_id)
        if task_id.startswith("fetch_and_index"):
            return task.python_callable(*args, ti=SimpleNamespace(try_number=try_number))
        return task.python_callable(*args)

    def run(self):
        indices = self.call("clear_indices")
        documents = self.call("fetch_and_index_documents", indices)
        files = self.call("fetch_and_index_files", indices)
        return indices, documents, files, self.call("validate_indices", documents, files)


def test_smoke_indexes_mapped_records_and_validates(dagbag, caplog):
    docs = [_doc(1, tags=["a"]), {"id": "doc-2", "title": "Two"}]
    with Env(dagbag, docs, [_file(1)]) as env, caplog.at_level("INFO"):
        indices, documents, files, counts = env.run()
    assert indices == {"documents": "documents", "files": "files"}
    assert counts == {"documents": 2, "files": 1}
    assert documents == {
        "index": "documents",
        "fetched": 2,
        "pages": 1,
        "batches": 1,
        "failed_batches": 0,
    }
    assert env.meili.docs("documents")[1] == {
        "id": "doc-2",
        "title": "Two",
        "content": "",
        "owner_id": "",
        "tags": [],
        "type": "document",
        "created_at": None,
        "updated_at": None,
    }
    assert env.meili.docs("files")[0]["size"] == 1
    assert env.documents.requests == [{"page": 1, "size": 100}]
    assert env.files.requests == [{"page": 1, "page_size": 100}]
    assert not [r for r in caplog.records if r.levelname == "WARNING"]
    assert set(env.variable_reads) == set(CONFIG)


def test_pagination_stops_on_a_short_or_empty_page(dagbag):
    docs = [_doc(i) for i in range(250)]
    files = [_file(i) for i in range(200)]
    with Env(dagbag, docs, files) as env:
        _, documents, file_result, counts = env.run()
    assert [r["page"] for r in env.documents.requests] == [1, 2, 3]
    assert [r["page"] for r in env.files.requests] == [1, 2, 3]
    assert (documents["pages"], file_result["pages"]) == (3, 2)
    assert counts == {"documents": 250, "files": 200}


def test_empty_upstreams_leave_empty_configured_indices(dagbag):
    with Env(dagbag) as env:
        _, _, _, counts = env.run()
    assert counts == {"documents": 0, "files": 0}
    assert env.meili.indexes["files"]["settings"]["sortableAttributes"][-1] == "size"


def test_variables_drive_index_names_page_and_batch_sizes(dagbag):
    docs = [_doc(i) for i in range(25)]
    variables = {
        "search_reindex_documents_index": "docs_v2",
        "search_reindex_api_page_size": "10",
        "search_reindex_bulk_batch_size": "4",
    }
    with Env(dagbag, docs, **variables) as env:
        indices, documents, _, counts = env.run()
    assert indices["documents"] == "docs_v2" and counts["docs_v2"] == 25
    assert env.documents.requests[0] == {"page": 1, "size": 10}
    assert documents["pages"] == 3 and documents["batches"] == 3 + 3 + 2


def test_failing_page_raises_and_keeps_earlier_pages(dagbag):
    docs = [_doc(i) for i in range(150)]
    with Env(dagbag, docs, doc_errors={2: 500}) as env:
        indices = env.call("clear_indices")
        with pytest.raises(AirflowException, match="500"):
            env.call("fetch_and_index_documents", indices)
    assert len(env.meili.docs("documents")) == 100


def test_retry_recreates_the_index_and_starts_from_page_one(dagbag):
    docs = [_doc(i) for i in range(150)]
    with Env(dagbag, docs, doc_errors={2: 500}) as env:
        indices = env.call("clear_indices")
        with pytest.raises(AirflowException):
            env.call("fetch_and_index_documents", indices)
        env.meili.indexes["documents"]["docs"]["stale"] = {"id": "stale"}
        env.documents.errors.clear()
        result = env.call("fetch_and_index_documents", indices, try_number=2)
    assert result["fetched"] == 150
    assert {d["id"] for d in env.meili.docs("documents")} == {"doc-%03d" % i for i in range(150)}
    assert env.meili.indexes["documents"]["settings"]["searchableAttributes"][0] == "title"


def test_duplicate_ids_fail_validation(dagbag):
    docs = [_doc(1), _doc(2), _doc(1, title="Second copy")]
    with Env(dagbag, docs) as env:
        with pytest.raises(AirflowFailException, match="documents: 2 documents, expected 3"):
            env.run()
    assert env.meili.indexes["documents"]["docs"]["doc-001"]["title"] == "Second copy"


def test_rejected_batch_only_warns_and_then_fails_validation(dagbag, caplog):
    docs = [_doc(1), {"title": "no id"}, _doc(3)]
    with Env(dagbag, docs, [_file(1)]) as env, caplog.at_level("WARNING"):
        indices = env.call("clear_indices")
        documents = env.call("fetch_and_index_documents", indices)
        files = env.call("fetch_and_index_files", indices)
        assert documents["fetched"] == 3 and documents["failed_batches"] == 1
        with pytest.raises(AirflowFailException, match="documents: 0 documents, expected 3"):
            env.call("validate_indices", documents, files)
    assert "invalid_document_id" in caplog.text
    assert env.meili.docs("documents") == [] and len(env.meili.docs("files")) == 1


def test_invalid_variable_fails_without_retry(dagbag):
    with Env(dagbag, search_reindex_api_page_size="lots") as env:
        with pytest.raises(AirflowFailException, match="search_reindex_api_page_size"):
            env.call("clear_indices")
    assert env.meili.calls == []
