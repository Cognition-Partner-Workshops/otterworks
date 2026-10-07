"""MeiliSearch through ``HttpHook``: requests, the task-polling helper and index lifecycle.

The ``otterworks_meilisearch`` Connection's password is the optional API key, sent as
``Authorization: Bearer <password>`` like legacy.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from airflow.providers.http.hooks.http import HttpHook

from otterworks_etl.common.log import get_logger, log_event
from otterworks_etl.search_reindex.mapping import PRIMARY_KEY

TERMINAL_STATUSES = frozenset({"succeeded", "failed", "canceled"})
INDEX_NOT_FOUND = "index_not_found"
POLL_INTERVAL_SECONDS = 1.0

logger = get_logger(__name__)


class MeiliTaskTimeout(Exception):
    """A MeiliSearch task did not reach a terminal status within its timeout."""


class MeiliSearch:
    def __init__(self, conn_id: str):
        self.conn_id = conn_id
        self._hooks: dict[str, HttpHook] = {}
        self._headers: dict[str, str] | None = None

    @property
    def headers(self) -> dict[str, str]:
        if self._headers is None:
            api_key = HttpHook.get_connection(self.conn_id).password
            self._headers = {"Content-Type": "application/json"}
            if api_key:
                self._headers["Authorization"] = f"Bearer {api_key}"
        return self._headers

    def _hook(self, method: str) -> HttpHook:
        if method not in self._hooks:
            self._hooks[method] = HttpHook(method=method, http_conn_id=self.conn_id)
        return self._hooks[method]

    def request(self, method: str, endpoint: str, body: Any = None, *, check: bool = True):
        """Send ``body`` as JSON; with ``check`` a non-2xx/3xx answer raises AirflowException."""
        return self._hook(method).run(
            endpoint,
            data=None if body is None else json.dumps(body),
            headers=self.headers,
            extra_options={"check_response": check},
        )

    def task(self, uid: int) -> dict[str, Any]:
        return self.request("GET", f"tasks/{uid}").json()

    def number_of_documents(self, index: str) -> int:
        return self.request("GET", f"indexes/{index}/stats").json().get("numberOfDocuments", 0)


def wait_for_task(
    meili: MeiliSearch,
    uid: int | None,
    timeout: float,
    *,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Poll ``tasks/<uid>`` until it succeeds, fails or is canceled, and return it.

    Raises MeiliTaskTimeout after ``timeout`` seconds (legacy carried on blind instead).
    A missing ``uid`` (nothing was enqueued) counts as succeeded.
    """
    if uid is None:
        return {"status": "succeeded"}
    deadline = clock() + timeout
    while True:
        task = meili.task(uid)
        status = task.get("status")
        if status in TERMINAL_STATUSES:
            return task
        if clock() >= deadline:
            raise MeiliTaskTimeout(f"MeiliSearch task {uid} still {status!r} after {timeout}s")
        sleep(poll_interval)


def submit(meili: MeiliSearch, method: str, endpoint: str, body: Any, timeout: float) -> dict:
    """Send a request that enqueues a MeiliSearch task and wait for that task."""
    uid = meili.request(method, endpoint, body).json().get("taskUid")
    return wait_for_task(meili, uid, timeout)


def task_error(task: Mapping[str, Any]) -> dict[str, Any]:
    return dict(task.get("error") or {})


def recreate_index(
    meili: MeiliSearch, index: str, settings: Mapping[str, Sequence[str]], timeout: float
) -> None:
    """Delete ``index``, create it with primary key ``id`` and apply ``settings``.

    As in legacy, a failed delete, create or settings task is logged and the run carries on;
    an index that does not exist yet is the expected case and logs at INFO.
    """
    resp = meili.request("DELETE", f"indexes/{index}", check=False)
    if resp.ok:
        task = wait_for_task(meili, resp.json().get("taskUid"), timeout)
        error = task_error(task)
        if task.get("status") == "succeeded":
            log_event(logger, "index_deleted", index=index)
        elif error.get("code") == INDEX_NOT_FOUND:
            log_event(logger, "index_did_not_exist", index=index)
        else:
            _warn_task(index, "delete", task)
    else:
        log_event(
            logger, "index_delete_rejected", logging.WARNING, index=index, status=resp.status_code
        )

    task = submit(meili, "POST", "indexes", {"uid": index, "primaryKey": PRIMARY_KEY}, timeout)
    if task.get("status") != "succeeded":
        _warn_task(index, "create", task)
    task = submit(meili, "PATCH", f"indexes/{index}/settings", dict(settings), timeout)
    if task.get("status") != "succeeded":
        _warn_task(index, "settings", task)
    log_event(logger, "index_configured", index=index)


def _warn_task(index: str, step: str, task: Mapping[str, Any]) -> None:
    log_event(
        logger,
        "meilisearch_task_failed",
        logging.WARNING,
        index=index,
        step=step,
        task_uid=task.get("uid"),
        status=task.get("status"),
        error=task_error(task),
    )
