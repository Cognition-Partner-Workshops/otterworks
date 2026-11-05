"""Hourly dashboard freshness checks and narrowly scoped fault recovery."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import snowflake.connector
import yaml
from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "attribution"))
import sf_attribution as sf  # noqa: E402

EP = sf.endpoint("cs_doc_usage_dashboard_freshness_responder")
ROLE = "ROLE_CS_DOC_USAGE_DASHBOARD_FRESHNESS_RESPONDER"
TASK = sf.task_name(EP.workload)
OPS = f"{EP.database}.OPS"
MONITOR = sf.resource_monitor_name(EP.workload)
SOURCE = "workloads/doc_usage_dashboard/responder/freshness.py"
PROVENANCE = Path(__file__).resolve().parents[1] / "provenance.yaml"
TABLES = {"ACCOUNT_STORAGE_USAGE", "PIPELINE_REFRESH_RUNS"}
CREDIT_STOP = Decimal("8.5")


class ResponderError(RuntimeError):
    pass


def deployed_revision(path=PROVENANCE):
    doc = yaml.safe_load(Path(path).read_text())
    records = [r for r in doc.get("deployment", {}).get("installed", [])
               if r["type"] == "runtime_source" and r["name"] == SOURCE and r["status"] == "installed"]
    if not records or not sf.COMMIT_RE.fullmatch(records[-1]["revision"]):
        raise ResponderError("An installed responder source revision is required")
    revision = records[-1]["revision"]
    endpoint = next(e for e in doc["endpoints"] if e["csid"] == EP.csid)
    if endpoint.get("runtime_source") != {"path": SOURCE, "revision": revision}:
        raise ResponderError("Endpoint runtime source must match the installed revision")
    return revision


def connection_parameters(path=PROVENANCE, env=None):
    env = os.environ if env is None else env
    params = sf.connection_params(
        EP, phase="runtime", account=env["SNOWFLAKE_EXT_ACCOUNT"],
        private_key_file="in-memory-only", commit=deployed_revision(path),
        run_id=sf.make_run_id(EP.workload, "runtime"), role=ROLE,
    )
    params.pop("private_key_file")
    key = serialization.load_pem_private_key(env["SNOWFLAKE_EXT_SRE_PRIVATE_KEY"].encode(), None)
    params.update(user=env["SNOWFLAKE_EXT_SRE_USER"], private_key=key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    if params["user"].upper() != EP.service_user:
        raise ResponderError("Responder service identity required")
    params["session_parameters"].update(DEFAULT_SECONDARY_ROLES="NONE", TIMEZONE="UTC")
    params.update(login_timeout=30, network_timeout=60)
    return params


def secondary_roles_empty(value):
    value = json.loads(value) if isinstance(value, str) else value
    return isinstance(value, dict) and value.get("roles") in ("", []) and value.get("value") in ("", [])


def history_sql():
    return (
        "SELECT NAME, STATE, SCHEDULED_TIME, QUERY_START_TIME, COMPLETED_TIME, QUERY_ID, "
        "ERROR_CODE, ERROR_MESSAGE, GRAPH_RUN_GROUP_ID FROM TABLE("
        f"{EP.database}.INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME=>'REFRESH_DOC_USAGE_DASHBOARD', "
        "SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP(), RESULT_LIMIT=>10)) ORDER BY SCHEDULED_TIME DESC"
    )


def scheduled_history_sql():
    return (
        "SELECT STATE, SCHEDULED_TIME FROM TABLE("
        f"{EP.database}.INFORMATION_SCHEMA.TASK_HISTORY(TASK_NAME=>'REFRESH_DOC_USAGE_DASHBOARD', "
        "SCHEDULED_TIME_RANGE_START=>CURRENT_TIMESTAMP(), "
        "SCHEDULED_TIME_RANGE_END=>DATEADD('hour',2,CURRENT_TIMESTAMP()), RESULT_LIMIT=>100)) "
        "WHERE STATE = 'SCHEDULED' ORDER BY SCHEDULED_TIME"
    )


def validate_faults(rows):
    active = [r for r in rows if r["cleared_at"] is None]
    if len(active) != 1 or any(r["target_task"] != TASK or r["mode"] != "user_task_timeout_ms" for r in active):
        raise ResponderError("Recovery requires exactly one active dashboard user_task_timeout_ms fault")


def parse_recovery_timestamp(value):
    parsed = datetime.fromisoformat(value.replace(" Z", "+00:00").replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class Responder:
    def __init__(self, connection):
        self.connection = connection
        self.output = {"query_ids": [], "queries": []}

    def query(self, sql):
        with self.connection.cursor() as cursor:
            try:
                cursor.execute(sql)
                columns = [d[0].lower() for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            finally:
                self.output["queries"].append({"sql": sql, "query_id": cursor.sfqid})
                if cursor.sfqid:
                    self.output["query_ids"].append(cursor.sfqid)

    def identify(self):
        self.query("USE SECONDARY ROLES NONE")
        rows = self.query("SELECT CURRENT_USER() AS USER_NAME, CURRENT_ROLE() AS ROLE_NAME, "
                          "CURRENT_SECONDARY_ROLES() AS SECONDARY_ROLES")
        if len(rows) != 1:
            raise ResponderError("Missing session identity")
        identity = rows[0]
        self.output["identity"] = identity
        if (identity["user_name"] != EP.service_user or identity["role_name"] != ROLE
                or not secondary_roles_empty(identity["secondary_roles"])):
            raise ResponderError("Unexpected identity or nonempty secondary roles")

    def credit_guard(self):
        rows = self.query("SHOW RESOURCE MONITORS")
        monitor = [r for r in rows if r["name"] == MONITOR]
        if len(monitor) != 1 or monitor[0]["used_credits"] is None:
            raise ResponderError("Dashboard monitor usage unavailable")
        self.output["resource_monitor"] = monitor[0]
        if Decimal(str(monitor[0]["used_credits"])) >= CREDIT_STOP:
            raise ResponderError("Dashboard resource monitor reached 8.5-credit stop")

    def check(self):
        self.credit_guard()
        fresh = self.query(f"SELECT * FROM {OPS}.WORKLOAD_TABLE_FRESHNESS ORDER BY TABLE_NAME")
        history = self.query(history_sql())
        faults = self.query(f"SELECT * FROM {OPS}.DASHBOARD_FAULT_CONTROL ORDER BY ARMED_AT DESC")
        scheduled = self.query(scheduled_history_sql())
        task = {"name": TASK, "state": "resumed" if scheduled else "suspended",
                "next_scheduled_time": scheduled[0]["scheduled_time"] if scheduled else None}
        finished = next((r for r in history if r["state"] in ("SUCCEEDED", "FAILED", "CANCELLED", "SKIPPED")), None)
        self.output.update(freshness=fresh, task_history=history, faults=faults, task=task,
                           scheduled_task_history=scheduled, latest_finished_run=finished)
        problems = []
        if len(fresh) != len(TABLES) or {r["table_name"] for r in fresh} != TABLES:
            problems.append("missing_freshness_rows")
        if any(r["stale"] is not False for r in fresh):
            problems.append("stale")
        if finished is None:
            problems.append("latest_task_run_not_succeeded")
        elif finished["state"] != "SUCCEEDED":
            problems.append({"problem": "latest_task_run_not_succeeded", "state": finished["state"],
                             "error_code": finished.get("error_code"), "error_message": finished.get("error_message")})
        problems.extend({"problem": "armed_fault", "fault": row} for row in faults if row["cleared_at"] is None)
        if not scheduled:
            problems.append("task_suspended")
        self.output.update(problems=problems, healthy=not problems)
        return not problems

    def recover(self, timeout=300, interval=5):
        self.credit_guard()
        faults = self.query(f"SELECT * FROM {OPS}.DASHBOARD_FAULT_CONTROL ORDER BY ARMED_AT DESC")
        validate_faults(faults)
        rows = self.query(f"CALL {OPS}.RECOVER_DASHBOARD_TASK()")
        result = next(iter(rows[0].values()))
        result = json.loads(result) if isinstance(result, str) else result
        self.output["recovery"] = result
        self.output["query_ids"].extend(result.get("query_ids", []))
        if result["target_task"] != TASK:
            raise ResponderError("Recovery returned a non-dashboard target")
        started = parse_recovery_timestamp(result["recovery_started_at"])
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.credit_guard()
            history = self.query(history_sql())
            runs = [r for r in history if r["scheduled_time"] >= started]
            self.output["recovery_history"] = runs
            if runs and runs[0]["state"] in ("SUCCEEDED", "FAILED", "CANCELLED", "SKIPPED"):
                healthy = self.check()
                return runs[0]["state"] == "SUCCEEDED" and healthy
            time.sleep(interval)
        raise ResponderError("Timed out waiting for dashboard recovery execution")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "recover"))
    args = parser.parse_args(argv)
    output = {"query_ids": []}
    try:
        params = connection_parameters()
        output["query_tag"] = json.loads(params["session_parameters"]["QUERY_TAG"])
        with closing(snowflake.connector.connect(**params)) as conn:
            responder = Responder(conn)
            responder.output.update(output)
            output = responder.output
            responder.identify()
            healthy = responder.check() if args.command == "check" else responder.recover()
            code = 0 if healthy else 1
    except Exception as exc:
        output.update(healthy=False, error=type(exc).__name__, message=str(exc))
        code = 2
    print(json.dumps(output, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
