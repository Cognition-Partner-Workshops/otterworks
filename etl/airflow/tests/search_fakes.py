"""In-memory MeiliSearch and upstream services behind ``HttpHook.run``."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace

from airflow.exceptions import AirflowException

MEILI = "otterworks_meilisearch"
DOCUMENT_SERVICE = "otterworks_document_service"
FILE_SERVICE = "otterworks_file_service"
VALID_ID = re.compile(r"^[A-Za-z0-9_-]{1,511}$")


def response(body, status=200):
    return SimpleNamespace(ok=status < 400, status_code=status, json=lambda: body)


class FakeMeili:
    """Indexes and tasks; each task reports ``processing`` for ``polls_until_done`` polls."""

    def __init__(self, polls_until_done=1):
        self.indexes: dict[str, dict] = {}
        self.tasks: dict[int, dict] = {}
        self.polls: dict[int, int] = {}
        self.polls_until_done = polls_until_done
        self.calls: list[tuple[str, str]] = []
        self.headers: list[dict] = []

    def _task(self, kind, index, error=None):
        uid = len(self.tasks)
        task = {"uid": uid, "indexUid": index, "type": kind, "status": "succeeded"}
        if error:
            task.update(status="failed", error={"code": error, "message": error})
        self.tasks[uid] = task
        self.polls[uid] = 0
        return response({"taskUid": uid}, 202)

    def handle(self, method, endpoint, body):
        self.calls.append((method, endpoint))
        parts = endpoint.split("/")
        if parts[0] == "tasks":
            uid = int(parts[1])
            self.polls[uid] += 1
            if self.polls[uid] <= self.polls_until_done:
                return response({**self.tasks[uid], "status": "processing"})
            return response(self.tasks[uid])
        if method == "POST" and endpoint == "indexes":
            uid = body["uid"]
            if uid in self.indexes:
                return self._task("indexCreation", uid, "index_already_exists")
            self.indexes[uid] = {"primaryKey": body["primaryKey"], "settings": {}, "docs": {}}
            return self._task("indexCreation", uid)
        index = parts[1]
        if method == "DELETE":
            if self.indexes.pop(index, None) is None:
                return self._task("indexDeletion", index, "index_not_found")
            return self._task("indexDeletion", index)
        if index not in self.indexes:
            return response({"code": "index_not_found"}, 404)
        if method == "PATCH" and parts[2] == "settings":
            self.indexes[index]["settings"] = body
            return self._task("settingsUpdate", index)
        if method == "POST" and parts[2] == "documents":
            if not all(isinstance(d.get("id"), str) and VALID_ID.match(d["id"]) for d in body):
                return self._task("documentAdditionOrUpdate", index, "invalid_document_id")
            for doc in body:
                self.indexes[index]["docs"][doc["id"]] = doc
            return self._task("documentAdditionOrUpdate", index)
        if method == "GET" and parts[2] == "stats":
            return response({"numberOfDocuments": len(self.indexes[index]["docs"])})
        raise AssertionError(f"unexpected MeiliSearch call {method} {endpoint}")

    def docs(self, index):
        return list(self.indexes[index]["docs"].values())


class FakeUpstream:
    """A paged list endpoint; ``errors`` maps a page number to an HTTP status."""

    def __init__(self, endpoint, key, size_param, items=(), errors=None):
        self.endpoint, self.key, self.size_param = endpoint, key, size_param
        self.items = [dict(i) for i in items]
        self.errors = dict(errors or {})
        self.requests: list[dict] = []

    def handle(self, method, endpoint, params):
        assert (method, endpoint) == ("GET", self.endpoint)
        self.requests.append(dict(params))
        page, size = params["page"], params[self.size_param]
        if page in self.errors:
            return response({"error": "boom"}, self.errors[page])
        start = (page - 1) * size
        return response({self.key: self.items[start : start + size], "page": page})


def install(meili, documents, files):
    """A replacement for ``HttpHook.run`` routing by Connection id."""

    def run(hook, endpoint=None, data=None, headers=None, extra_options=None, **kwargs):
        if hook.http_conn_id == MEILI:
            meili.headers.append(dict(headers or {}))
            body = json.loads(data) if data is not None else None
            resp = meili.handle(hook.method, endpoint, body)
        elif hook.http_conn_id == DOCUMENT_SERVICE:
            resp = documents.handle(hook.method, endpoint, data)
        elif hook.http_conn_id == FILE_SERVICE:
            resp = files.handle(hook.method, endpoint, data)
        else:
            raise AssertionError(f"unexpected connection {hook.http_conn_id}")
        if (extra_options or {}).get("check_response", True) and not resp.ok:
            raise AirflowException(f"{resp.status_code}:error")
        return resp

    return run
