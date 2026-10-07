import json
from urllib.request import urlopen

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
