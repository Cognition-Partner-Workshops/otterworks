"""Collect Snowflake query IDs without recording query text or credentials."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def update_query_record(
    path: str | Path,
    *,
    commit: str,
    run_ids: dict[str, str],
    step: str,
    query_ids: list[str],
) -> None:
    record_path = Path(path)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    if record_path.exists():
        record = json.loads(record_path.read_text())
    else:
        record = {"commit": commit, "run_ids": run_ids, "steps": {}}
    if record["commit"] != commit or any(
        record["run_ids"].get(name, run_id) != run_id for name, run_id in run_ids.items()
    ):
        raise ValueError("query record commit or run IDs do not match this run")
    record["run_ids"].update(run_ids)
    step_ids = record["steps"].setdefault(step, [])
    for query_id in query_ids:
        if query_id and query_id not in step_ids:
            step_ids.append(query_id)
    record["all_query_ids"] = sorted(
        {query_id for ids in record["steps"].values() for query_id in ids}
    )
    record_path.write_text(json.dumps(record, indent=2) + "\n")


class RecordingCursor:
    def __init__(
        self,
        cursor: Any,
        path: str | Path,
        *,
        commit: str,
        run_ids: dict[str, str],
        step: str,
    ) -> None:
        self._cursor = cursor
        self._path = path
        self._commit = commit
        self._run_ids = run_ids
        self._step = step

    def execute(self, *args: Any, **kwargs: Any) -> RecordingCursor:
        self._cursor.execute(*args, **kwargs)
        update_query_record(
            self._path,
            commit=self._commit,
            run_ids=self._run_ids,
            step=self._step,
            query_ids=[getattr(self._cursor, "sfqid", None)],
        )
        return self

    def executemany(self, *args: Any, **kwargs: Any) -> RecordingCursor:
        self._cursor.executemany(*args, **kwargs)
        update_query_record(
            self._path,
            commit=self._commit,
            run_ids=self._run_ids,
            step=self._step,
            query_ids=[getattr(self._cursor, "sfqid", None)],
        )
        return self

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)
