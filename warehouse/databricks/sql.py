"""Bounded SQL Statement Execution client. No local or replay fallback."""
import json
import os
import re
import time
from urllib.request import Request, urlopen


def identifier(value):
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]*", value):
        raise ValueError("invalid SQL identifier")
    return f"`{value}`"


class Warehouse:
    def __init__(self, *, act, consumer="platform", host=None, warehouse_id=None,
                 token=None, run=None):
        self.host = (host or os.environ["DATABRICKS_HOST"]).rstrip("/")
        if not self.host.startswith("https://"):
            raise ValueError("DATABRICKS_HOST must use HTTPS")
        self.warehouse_id = warehouse_id or os.environ["DATABRICKS_WAREHOUSE_ID"]
        self.token = token or os.environ["DATABRICKS_TOKEN"]
        self.run = run or os.environ.get("DATABRICKS_RUN_TOKEN", "dbx-d1111")
        self.act, self.consumer = act, consumer
        for value in (self.run, act, consumer):
            if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
                raise ValueError("invalid query tag")
        self.statements = []

    def _request(self, path, body=None):
        # Paths come from Statement Execution; never follow external result URLs.
        if not path.startswith("/api/2.0/sql/statements/"):
            raise ValueError("invalid statement result path")
        req = Request(self.host + path,
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={"Authorization": "Bearer " + self.token,
                               "Content-Type": "application/json"})
        with urlopen(req, timeout=60) as response:
            return json.load(response)

    def execute(self, statement, *, step, parameters=None, timeout=600):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", step):
            raise ValueError("invalid query step")
        tag = f"/* run={self.run} act={self.act} step={step} consumer={self.consumer} */"
        body = {"warehouse_id": self.warehouse_id, "statement": tag + "\n" + statement,
                "wait_timeout": "10s", "disposition": "INLINE", "format": "JSON_ARRAY"}
        if parameters:
            body["parameters"] = parameters
        result = self._request("/api/2.0/sql/statements/", body)
        sid = result["statement_id"]
        self.statements.append(sid)
        deadline = time.monotonic() + timeout
        while result["status"]["state"] in {"PENDING", "RUNNING"}:
            if time.monotonic() >= deadline:
                self._request(f"/api/2.0/sql/statements/{sid}/cancel", {})
                raise TimeoutError(f"statement {sid} cancelled after timeout")
            time.sleep(1)
            result = self._request(f"/api/2.0/sql/statements/{sid}")
        if result["status"]["state"] != "SUCCEEDED":
            error = result["status"].get("error", {})
            raise RuntimeError(f"statement {sid}: {error.get('error_code', 'FAILED')}: "
                               + error.get("message", "SQL failed"))
        if result.get("manifest", {}).get("truncated"):
            raise RuntimeError(f"statement {sid}: truncated result cannot prove parity")
        chunk = result.get("result", {})
        rows = list(chunk.get("data_array", []))
        while chunk.get("next_chunk_internal_link"):
            chunk = self._request(chunk["next_chunk_internal_link"])
            rows.extend(chunk.get("data_array", []))
        return {"statement_id": sid,
                "columns": [c["name"] for c in result.get("manifest", {}).get("schema", {}).get("columns", [])],
                "rows": rows}
