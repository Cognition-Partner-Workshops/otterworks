import json
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from harness.stub_http import ServiceStub


def test_pages_like_the_services():
    docs = [{"id": "doc-%d" % i} for i in range(5)]
    with ServiceStub({"documents": docs}) as stub:

        def get(path):
            with urlopen(stub.url + path) as resp:
                return json.load(resp)

        assert (
            get("/document-service/api/v1/documents?page=1&size=2")["documents"]
            == docs[:2]
        )
        assert (
            get("/document-service/api/v1/documents?page=3&size=2")["documents"]
            == docs[4:]
        )
        assert (
            get("/document-service/api/v1/documents?page=4&size=2")["documents"] == []
        )
        assert get("/file-service/api/v1/files?page=1&size=100")["files"] == []
    assert len(stub.requests) == 4


def test_files_page_size_and_injected_errors():
    files = [{"id": "file-%d" % i} for i in range(5)]
    data = {"files": files, "errors": {"files": {"2": 500}}}
    with ServiceStub(data) as stub:
        with urlopen(
            stub.url + "/file-service/api/v1/files?page=1&page_size=3"
        ) as resp:
            assert json.load(resp)["files"] == files[:3]
        with pytest.raises(HTTPError) as err:
            urlopen(stub.url + "/file-service/api/v1/files?page=2&page_size=3")
        assert err.value.code == 500


def test_scenario_http_reads_the_committed_seed():
    from harness import stub_http

    data = stub_http.scenario_http("search_reindex_weekly/smoke")
    assert [d.get("document_id") or d.get("id") for d in data["documents"]] == [
        "doc-1",
        "doc-2",
    ]
    assert [f["file_id"] for f in data["files"]] == ["file-1"]
