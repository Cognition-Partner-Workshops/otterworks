"""Stage large intermediate data in S3 and pass only the key through XCom.

Hooks are passed in, so these helpers never open a connection at import time and unit tests
can use a fake with ``load_bytes`` / ``read_key`` semantics of ``S3Hook``.
"""

from __future__ import annotations

import gzip
import json
import re
from typing import Any, Protocol

STAGING_PREFIX = "airflow-staging"

_UNSAFE = re.compile(r"[^A-Za-z0-9._=-]+")


class S3BytesHook(Protocol):
    def load_bytes(
        self, bytes_data: bytes, key: str, bucket_name: str | None = ..., replace: bool = ...
    ) -> None: ...

    def get_key(self, key: str, bucket_name: str | None = ...) -> Any: ...


def _segment(value: str) -> str:
    cleaned = _UNSAFE.sub("_", value).strip("_")
    if not cleaned:
        raise ValueError(f"empty staging key segment from {value!r}")
    return cleaned


def staging_key(dag_id: str, run_id: str, task_id: str, name: str) -> str:
    """Deterministic key per DAG run and task, so a retry overwrites its own output."""
    parts = (dag_id, run_id, task_id, name)
    return "/".join([STAGING_PREFIX, *(_segment(p) for p in parts)]) + ".json.gz"


def stage_json(hook: S3BytesHook, bucket: str, key: str, payload: Any) -> str:
    """Write ``payload`` as gzip JSON and return the S3 key to hand to the next task."""
    body = gzip.compress(json.dumps(payload, sort_keys=True, default=str).encode("utf-8"), mtime=0)
    hook.load_bytes(body, key=key, bucket_name=bucket, replace=True)
    return key


def load_staged_json(hook: S3BytesHook, bucket: str, key: str) -> Any:
    """Read back a payload written by :func:`stage_json`."""
    body = hook.get_key(key, bucket_name=bucket).get()["Body"].read()
    return json.loads(gzip.decompress(body).decode("utf-8"))
