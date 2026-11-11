"""Small Statement Execution client; credentials are read only from the environment."""
import json
import os
import re
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "local-evidence"


def api(method, path, body=None):
    req = urllib.request.Request(
        os.environ["DATABRICKS_HOST"].rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + os.environ["DATABRICKS_TOKEN"],
                 "Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def sql(statement, consumer, step, label=None, fail=True):
    statement = re.sub(r"^/\* run=dbx-d1111 act=scale.*?\*/\s*", "", statement.strip(), count=1)
    statement = f"/* run=dbx-d1111 act=scale step={step} consumer={consumer} */\n" + statement
    r = api("POST", "/api/2.0/sql/statements", {
        "warehouse_id": os.environ["DATABRICKS_WAREHOUSE_ID"],
        "statement": statement, "wait_timeout": "50s", "on_wait_timeout": "CONTINUE",
        "disposition": "INLINE", "format": "JSON_ARRAY"})
    while r["status"]["state"] in ("PENDING", "RUNNING"):
        time.sleep(2)
        r = api("GET", "/api/2.0/sql/statements/" + r["statement_id"])
    EVIDENCE.mkdir(exist_ok=True)
    record = {"consumer": consumer, "step": step, "label": label, "sql": statement, "response": r}
    (EVIDENCE / (r["statement_id"] + ".json")).write_text(json.dumps(record, indent=2))
    with (EVIDENCE / "statements.jsonl").open("a") as f:
        f.write(json.dumps(record) + "\n")
    if fail and r["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(json.dumps({"statement_id": r["statement_id"], "status": r["status"]}))
    return r


def rows(response):
    names = [c["name"] for c in response.get("manifest", {}).get("schema", {}).get("columns", [])]
    return [dict(zip(names, r)) for r in response.get("result", {}).get("data_array", [])]


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("file", type=Path)
    p.add_argument("--consumer", required=True)
    p.add_argument("--step", default="inspect")
    a = p.parse_args()
    r = sql(a.file.read_text(), a.consumer, a.step)
    print(json.dumps({"statement_id": r["statement_id"], "rows": rows(r)}))
