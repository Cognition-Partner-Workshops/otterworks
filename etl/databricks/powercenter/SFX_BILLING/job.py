"""Deploy one warehouse-only Job and capture sequential run and statement evidence."""

import argparse
import base64
import csv
import json
import os
import re
import time
import urllib.error
from pathlib import Path
from string import Template
from urllib.parse import urlencode

from run import HERE, ORDER, PARAMETERS, Runner, statements

TAGS = {"run_token": "dbx-d1111", "expires": "2026-11-24", "act": "scale"}
TERMINAL = {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}


def definition(workspace_dir, warehouse_id):
    return json.loads(Template((HERE / "jobs/wf_SFX_BILLING_DAILY.job.json").read_text()).substitute(
        WORKSPACE_DIR=workspace_dir, DATABRICKS_WAREHOUSE_ID=warehouse_id))


def sql_files():
    files = {}
    for name in ORDER:
        filename = "m_SFX_" + name + ".sql"
        text = Template((HERE / filename).read_text()).substitute(**PARAMETERS, STEP="job-run")
        for sql in statements(text):
            if not sql.startswith("/* run=dbx-d1111 act=scale step=job-run consumer=m_SFX_") or "${" in sql:
                raise ValueError("Invalid Job SQL header: " + filename)
        files[filename] = text
    files["em_GL_POSTING_ALERT.sql"] = (HERE / "jobs/em_GL_POSTING_ALERT.sql").read_text()
    return files


def assert_parity(report):
    corrected = [r for r in report if not (
        r["mapping"] == "GL_JOURNAL_LINE" and r["reference"].endswith("__pc_before"))]
    if len(corrected) != len(ORDER) or {r["mapping"] for r in corrected} != set(ORDER):
        raise ValueError("Incomplete parity report")
    for entry in corrected:
        left, right = entry["hash_rows"]
        if left[1:] != right[1:] or any(d["rows"] for d in entry["differences"]):
            raise ValueError("Business parity failed: " + entry["mapping"])
        print("Job parity", entry["mapping"], "count/hash", *left[1:], "MATCH", flush=True)


class Job(Runner):
    def __init__(self, output, ledger):
        super().__init__("job-run", output, ledger)
        self.state_path = output / "job.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}

    def api(self, method, path, body=None):
        try:
            return super().api(method, path, body)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"{method} {path}: {error.code} {error.read().decode()}") from error

    def save(self):
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def deploy(self):
        if self.state:
            raise ValueError("Job already deployed in this output directory; use run or collect")
        warehouse = self.api("GET", "/api/2.0/sql/warehouses/" + os.environ["DATABRICKS_WAREHOUSE_ID"])
        if not warehouse.get("enable_serverless_compute"):
            raise ValueError("The supplied SQL warehouse is not serverless")
        user = self.api("GET", "/api/2.0/preview/scim/v2/Me")["userName"]
        workspace_dir = "/Users/" + user + "/dbx-d1111/SFX_BILLING"
        settings = definition(workspace_dir, os.environ["DATABRICKS_WAREHOUSE_ID"])
        existing = self.api("GET", "/api/2.1/jobs/list?" + urlencode({"name": settings["name"]}))
        if existing.get("jobs"):
            raise ValueError("A Job with this name already exists; refusing to create a duplicate")
        self.api("POST", "/api/2.0/workspace/mkdirs", {"path": workspace_dir})
        for name, sql in sql_files().items():
            self.api("POST", "/api/2.0/workspace/import", {
                "path": workspace_dir + "/" + name, "format": "AUTO", "overwrite": True,
                "content": base64.b64encode(sql.encode()).decode()})
        result = self.api("POST", "/api/2.1/jobs/create", settings)
        self.state = {"job_id": result["job_id"], "workspace_dir": workspace_dir,
                      "tags": TAGS, "runs": []}
        self.save()
        print("Created job", self.state["job_id"], "workspace", workspace_dir, flush=True)

    def run_once(self):
        settings = self.api("GET", "/api/2.1/jobs/get?job_id=" + str(self.state["job_id"]))["settings"]
        if settings.get("tags") != TAGS:
            raise ValueError("Job tags no longer match the run contract")
        (self.output / "settings.json").write_text(json.dumps(settings, indent=2))
        if any(r.get("state", {}).get("life_cycle_state") not in TERMINAL for r in self.state["runs"]):
            raise ValueError("A previous run is unfinished; collect it before starting another")
        response = self.api("POST", "/api/2.1/jobs/run-now", {
            "job_id": self.state["job_id"], "job_parameters": TAGS})
        run = {"run_id": response["run_id"], "tags": TAGS}
        self.state["runs"].append(run)
        self.save()
        self.collect(run)
        self.record_statements(run)
        if run["state"].get("result_state") != "SUCCESS":
            raise RuntimeError("Job failed; see saved run and task output evidence")

    def collect(self, run):
        while True:
            detail = self.api("GET", "/api/2.1/jobs/runs/get?run_id=" + str(run["run_id"]))
            run.update(detail)
            self.save()
            if detail["state"]["life_cycle_state"] in TERMINAL:
                break
            time.sleep(10)
        outputs = {}
        for task in detail.get("tasks", []):
            print("Run", run["run_id"], task["task_key"], task["state"].get("result_state"), flush=True)
            if "sql_task" in task and task["state"].get("result_state") not in ("EXCLUDED", "UPSTREAM_FAILED", "UPSTREAM_CANCELED"):
                outputs[task["task_key"]] = self.api(
                    "GET", "/api/2.1/jobs/runs/get-output?run_id=" + str(task["run_id"]))
        (self.output / (str(run["run_id"]) + "-outputs.json")).write_text(json.dumps(outputs, indent=2))
        self.save()

    def record_statements(self, run):
        outputs = json.loads((self.output / (str(run["run_id"]) + "-outputs.json")).read_text())
        parameters = {
            "filter_by.query_start_time_range.start_time_ms": run["start_time"],
            "filter_by.query_start_time_range.end_time_ms": run["end_time"],
            "filter_by.warehouse_ids": os.environ["DATABRICKS_WAREHOUSE_ID"],
            "max_results": 100, "include_metrics": "true"}
        history = []
        while True:
            page = self.api("GET", "/api/2.0/sql/history/queries?" + urlencode(parameters))
            history.extend(page.get("res", []))
            if not page.get("has_next_page"):
                break
            parameters["page_token"] = page["next_page_token"]
        (self.output / (str(run["run_id"]) + "-history.json")).write_text(json.dumps(history, indent=2))
        by_key = {r["lookup_key"]: r for r in history if r.get("lookup_key")}
        rows = []
        evidence = []
        resolved = {}
        for task_key, output in outputs.items():
            file_output = output.get("sql_output", {}).get("file_output", {})
            sql = statements(file_output.get("query_text", ""))
            executed = file_output.get("sql_statements", [])
            if len(executed) > len(sql):
                raise ValueError("Incomplete SQL task statement evidence: " + task_key)
            for index, text in enumerate(sql):
                match = re.match(r"/\* run=dbx-d1111 act=scale step=job-run consumer=(\S+) \*/", text)
                if not match:
                    raise ValueError("Invalid statement header: " + task_key)
                result = executed[index] if index < len(executed) else {}
                query = by_key.get(result.get("lookup_key"))
                executed_id = result.get("statement_id") or result.get("query_id") or result.get("lookup_key")
                item = {"task_key": task_key, "sql": text, "lookup_key": result.get("lookup_key"),
                        "statement_id": query["query_id"] if query else executed_id,
                        "state": "PENDING", "query_history": "available" if query else "missing"}
                evidence.append(item)
                purpose = f"job {run['run_id']} {task_key}"
                if query is None:
                    if executed_id:
                        rows.append(["job-run", match[1], purpose, executed_id, "PENDING"])
                    continue
                if executed_id:
                    resolved[executed_id] = query["query_id"]
                if not query["query_text"].startswith(match[0]):
                    raise ValueError("Query history header mismatch: " + task_key)
                state = {"FINISHED": "SUCCEEDED", "FAILED": "FAILED", "CANCELED": "CANCELED"}.get(query["status"])
                if state is None:
                    rows.append(["job-run", match[1], purpose, query["query_id"], "PENDING"])
                    continue
                item["state"] = state
                rows.append(["job-run", match[1], f"job {run['run_id']} {task_key}", query["query_id"], state])
        (self.output / (str(run["run_id"]) + "-statements.json")).write_text(json.dumps(evidence, indent=2))
        if not evidence:
            raise ValueError("No SQL statements found")
        fields = ["step", "consumer", "purpose", "statement_id", "state"]
        prior = {}
        if self.ledger.exists():
            with self.ledger.open() as f:
                prior = {r["statement_id"]: [r[field] for field in fields] for r in csv.DictReader(f, delimiter="\t")}
        for executed_id, statement_id in resolved.items():
            if executed_id != statement_id and executed_id in prior and prior[executed_id][4] == "PENDING":
                del prior[executed_id]
        for row in rows:
            if row[4] != "PENDING" or row[3] not in prior:
                prior[row[3]] = row
        with self.ledger.open("w", newline="") as f:
            writer = csv.writer(f, delimiter="\t", lineterminator="\n")
            writer.writerow(fields)
            writer.writerows(prior.values())
        print("Recorded", len(rows), "Job SQL statement IDs for run", run["run_id"], flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["deploy", "run", "collect", "parity"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=Path("/home/ubuntu/dbx/statements.tsv"))
    args = parser.parse_args()
    job = Job(args.output, args.ledger)
    if args.mode == "deploy":
        job.deploy()
    elif args.mode == "run":
        job.run_once()
    elif args.mode == "collect":
        job.collect(job.state["runs"][-1])
        job.record_statements(job.state["runs"][-1])
    else:
        runner = Runner("job-parity", args.output / "parity", args.ledger)
        runner.parity(2)
        assert_parity(json.loads((runner.output / "parity.json").read_text()))


if __name__ == "__main__":
    main()
