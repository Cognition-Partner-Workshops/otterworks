"""Snowflake CD planning, provenance updates and query-history auditing."""

from __future__ import annotations

import argparse
import copy
import difflib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workloads/pipeline"))
sys.path.insert(0, str(ROOT / "workloads/attribution"))
from pipeline import CONSUMERS, attr  # noqa: E402
from query_recording import RecordingCursor, update_query_record  # noqa: E402

sys.path.insert(0, str(ROOT / "workloads/attribution"))
import validate_provenance as provenance_validator  # noqa: E402

WORKLOADS = tuple(CONSUMERS)
INVENTORY_TYPES = {
    "database", "schema", "warehouse", "user", "table", "view", "stage",
    "file_format", "procedure", "dbt_project", "task", "streamlit",
}
READ_ONLY_QUERY_TYPES = {
    "SELECT", "SHOW", "DESCRIBE", "USE", "ALTER_SESSION", "SET",
    "LIST", "GET", "EXPLAIN",
}
DEFAULT_RESULTS_DIR = Path("/home/ubuntu/notes/cd-logs/snowflake-cd")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_commit(path: Path) -> str:
    data = yaml.safe_load(path.read_text())
    return data["source"]["commit"]


def rollback_target(from_commit: str | None = None, repo: str | Path = ROOT) -> str:
    provenance_path = "workloads/doc_usage_dashboard/provenance.yaml"
    if from_commit is None:
        from_commit = source_commit(ROOT / provenance_path)
    shallow = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if shallow == "true":
        subprocess.run(
            ["git", "-C", str(repo), "fetch", "--unshallow", "origin"],
            check=True,
        )
    commits = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%H", "--", provenance_path],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    for commit in commits:
        contents = subprocess.run(
            ["git", "-C", str(repo), "show", f"{commit}:{provenance_path}"],
            check=True, capture_output=True, text=True,
        ).stdout
        data = yaml.safe_load(contents)
        candidate = data["source"]["commit"]
        if candidate != from_commit:
            return candidate
    raise ValueError(f"No earlier provenance source commit differs from {from_commit}")


def merge_provenance(
    provenance: dict[str, Any],
    inventory: Iterable[dict[str, str]],
    redeployed: Iterable[tuple[str, str]],
    *,
    commit: str,
    deployed_at: str,
) -> tuple[dict[str, Any], list[str]]:
    """Merge Snowflake's current inventory into a provenance document."""
    result = copy.deepcopy(provenance)
    result["source"]["commit"] = commit
    existing = result["deployed_objects"]
    by_key = {(item["type"], item["name"]): item for item in existing}
    deployed_keys = set(redeployed)
    inventory_by_key = {
        (item["type"], item["name"]): item for item in inventory
        if item.get("type") in INVENTORY_TYPES
    }
    warnings = []

    for key, found in inventory_by_key.items():
        item = by_key.get(key)
        if item is None:
            item = {"type": key[0], "name": key[1], "state": "deployed"}
            if key[0] in {"database", "warehouse", "task", "streamlit"}:
                item["devin_csid"] = found["devin_csid"]
            item["deployed_at"] = deployed_at
            item["deployed_commit"] = commit
            existing.append(item)
            by_key[key] = item
        elif key in deployed_keys:
            item.update(state="deployed", deployed_at=deployed_at, deployed_commit=commit)
            if key[0] in {"database", "warehouse", "task", "streamlit"}:
                item["devin_csid"] = found.get("devin_csid", item.get("devin_csid"))

    for item in existing:
        key = (item["type"], item["name"])
        if item["type"] in INVENTORY_TYPES and item["state"] == "deployed" and key not in inventory_by_key:
            item.update(state="dropped", deployed_at=deployed_at, deployed_commit=commit)
            warnings.append(f"Previously deployed object is absent from Snowflake: {key[0]} {key[1]}")
    return result, warnings


def _columns(cursor: Any) -> list[str]:
    return [
        (getattr(column, "name", None) or column[0]).lower()
        for column in cursor.description
    ]


def _show(cursor: Any, sql: str) -> list[dict[str, Any]]:
    cursor.execute(sql)
    names = _columns(cursor)
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def inventory_workload(cursor: Any, workload: str) -> list[dict[str, str]]:
    names = attr.names([workload])
    database = names[f"db_{workload}"]
    endpoint_csids = [CONSUMERS[workload][0]]
    objects: dict[tuple[str, str], dict[str, str]] = {}

    def add(kind: str, name: str, *, csid: str | None = None) -> None:
        full_name = name.upper().strip('"')
        item = {"type": kind, "name": full_name}
        if csid:
            item["devin_csid"] = csid
        objects[(kind, full_name)] = item

    if any(row.get("name", "").upper() == database for row in _show(cursor, f"SHOW DATABASES LIKE '{database}'")):
        add("database", database, csid=endpoint_csids[0])
        for row in _show(cursor, f"SHOW SCHEMAS IN DATABASE {database}"):
            if row["name"].upper() != "INFORMATION_SCHEMA":
                add("schema", f"{database}.{row['name']}")
        for row in _show(cursor, f"SHOW TABLES IN DATABASE {database}"):
            if row.get("schema_name", "").upper() != "INFORMATION_SCHEMA":
                add("table", f"{database}.{row['schema_name']}.{row['name']}")
        for row in _show(cursor, f"SHOW VIEWS IN DATABASE {database}"):
            if row.get("schema_name", "").upper() != "INFORMATION_SCHEMA":
                add("view", f"{database}.{row['schema_name']}.{row['name']}")
        for row in _show(cursor, f"SHOW STAGES IN DATABASE {database}"):
            if row.get("schema_name", "").upper() != "INFORMATION_SCHEMA":
                add("stage", f"{database}.{row['schema_name']}.{row['name']}")
        for row in _show(cursor, f"SHOW FILE FORMATS IN DATABASE {database}"):
            if row.get("schema_name", "").upper() != "INFORMATION_SCHEMA":
                add("file_format", f"{database}.{row['schema_name']}.{row['name']}")
        for row in _show(cursor, f"SHOW PROCEDURES IN DATABASE {database}"):
            if not row.get("schema_name"):
                continue
            proc_name = str(row["name"]).split("(", 1)[0]
            add("procedure", f"{database}.{row['schema_name']}.{proc_name}")
        for row in _show(cursor, f"SHOW DBT PROJECTS IN SCHEMA {database}.ANALYTICS"):
            add("dbt_project", f"{database}.ANALYTICS.{row['name']}")
        for row in _show(cursor, f"SHOW TASKS IN DATABASE {database}"):
            if row.get("schema_name", "").upper() != "INFORMATION_SCHEMA":
                add("task", f"{database}.{row['schema_name']}.{row['name']}", csid=endpoint_csids[0])
        for row in _show(cursor, f"SHOW STREAMLITS IN SCHEMA {database}.ANALYTICS"):
            add("streamlit", f"{database}.ANALYTICS.{row['name']}", csid=endpoint_csids[0])

    warehouse = names[f"wh_{workload}"]
    if any(row.get("name", "").upper() == warehouse for row in _show(cursor, f"SHOW WAREHOUSES LIKE '{warehouse}'")):
        add("warehouse", warehouse, csid=endpoint_csids[0])
    user = attr.service_user(endpoint_csids[0])
    if _show(cursor, f"SHOW USERS LIKE '{user}'"):
        add("user", user)
    return list(objects.values())


def redeployed_from_results(results_dir: Path) -> tuple[set[tuple[str, str]], list[str]]:
    redeployed: set[tuple[str, str]] = set()
    query_ids: list[str] = []
    for workload in WORKLOADS:
        target = results_dir / workload
        run_results_path = target / "run_results.json"
        manifest_path = target / "manifest.json"
        if not run_results_path.exists():
            run_results = {}
        else:
            run_results = json.loads(run_results_path.read_text())
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        nodes = manifest.get("nodes", {})
        if not run_results_path.exists():
            for node in nodes.values():
                if node.get("resource_type") == "model" and node.get("relation_name"):
                    name = node["relation_name"].replace('"', "").upper()
                    materialized = (node.get("config") or {}).get("materialized", "view")
                    kind = "table" if materialized in {"table", "incremental"} else "view"
                    redeployed.add((kind, name))
            continue
        for result in run_results.get("results", []):
            response = result.get("adapter_response") or {}
            query_id = response.get("query_id") or response.get("QUERY_ID")
            if query_id:
                query_ids.append(str(query_id))
            node = nodes.get(result.get("unique_id"), {})
            if node.get("resource_type") != "model" or result.get("status") not in {"success", "pass"}:
                continue
            relation = node.get("relation_name")
            if not relation:
                continue
            name = relation.replace('"', "").upper()
            materialized = (node.get("config") or {}).get("materialized", "view")
            kind = "table" if materialized in {"table", "incremental"} else "view"
            redeployed.add((kind, name))
    return redeployed, query_ids


def deployment_objects(results_dir: Path) -> set[tuple[str, str]]:
    objects, _ = redeployed_from_results(results_dir)
    names = attr.names(["doc_usage_dashboard"])
    objects.update({
        ("dbt_project", names["dbt_project_doc_usage_dashboard"]),
        ("stage", names["dbt_stage_doc_usage_dashboard"]),
        ("stage", f"{names['db_doc_usage_dashboard']}.ANALYTICS.DOC_USAGE_DASHBOARD_APP_STAGE"),
        ("task", names["task_doc_usage_dashboard"]),
        ("streamlit", attr.streamlit_name("doc_usage_dashboard")),
    })
    return objects


def _provenance_path(workload: str) -> Path:
    return ROOT / "workloads" / workload / "provenance.yaml"


def provenance_changes(
    commit: str,
    results_dir: Path,
    *,
    mode: str,
    record_path: Path | None = None,
) -> tuple[dict[Path, str], list[str]]:
    changes: dict[Path, str] = {}
    warnings: list[str] = []
    redeployed = deployment_objects(results_dir)
    timestamp = utc_now()
    for workload in WORKLOADS:
        path = _provenance_path(workload)
        original_text = path.read_text()
        current = yaml.safe_load(original_text)
        if record_path:
            from pipeline import connect

            connection = connect(workload)
            try:
                cursor = connection.cursor()
                cursor = RecordingCursor(
                    cursor, record_path, commit=commit,
                    run_ids=run_ids_from_env(), step="provenance",
                )
                inventory = inventory_workload(cursor, workload)
            finally:
                connection.close()
        else:
            raise ValueError("Snowflake inventory is required to calculate provenance")
        updated, dropped = merge_provenance(
            current,
            inventory,
            redeployed,
            commit=commit,
            deployed_at=timestamp,
        )
        errors = provenance_validator.validate(updated, path, root=ROOT)
        if errors:
            raise ValueError(f"Invalid provenance for {workload}: {errors}")
        rendered = yaml.safe_dump(updated, sort_keys=False, allow_unicode=True)
        if rendered != original_text:
            changes[path] = rendered
        warnings.extend(dropped)
    return changes, warnings


def print_provenance_diff(changes: dict[Path, str]) -> None:
    for path, replacement in changes.items():
        before = path.read_text().splitlines(keepends=True)
        after = replacement.splitlines(keepends=True)
        print("".join(difflib.unified_diff(
            before, after, fromfile=str(path.relative_to(ROOT)), tofile=str(path.relative_to(ROOT)),
        )))


def run_ids_from_env() -> dict[str, str]:
    result = {"platform": os.environ.get("SF_RUN_ID", "")}
    for workload in WORKLOADS:
        result[workload] = os.environ.get(f"SF_RUN_ID_{workload.upper()}", "")
    return result


def prepare_run_environment(commit: str, phase: str = "runtime") -> tuple[dict[str, str], dict[str, str]]:
    if phase != "runtime":
        raise ValueError("Snowflake CD workflows must use SF_PHASE=runtime")
    env = os.environ.copy()
    for name in ("ACCOUNT", "USER", "ROLE"):
        value = env.get(f"SFNFR_{name}")
        if value:
            env[f"SNOWFLAKE_{name}"] = value
    env.pop("SNOWFLAKE_HOST", None)
    env["SF_PHASE"] = phase
    env["SF_COMMIT"] = commit
    env["SF_RUN_ID"] = env.get("SF_RUN_ID") or attr.make_run_id("platform", phase)
    for workload in WORKLOADS:
        key = f"SF_RUN_ID_{workload.upper()}"
        env[key] = env.get(key) or attr.make_run_id(workload, phase)
    os.environ.update(env)
    return env, {
        "platform": env["SF_RUN_ID"],
        **{workload: env[f"SF_RUN_ID_{workload.upper()}"] for workload in WORKLOADS},
    }


def write_query_record(path: Path, commit: str, run_ids: dict[str, str]) -> None:
    update_query_record(path, commit=commit, run_ids=run_ids, step="init", query_ids=[])


def query_history(
    run_ids: dict[str, str],
    *,
    since: str,
    record_path: Path,
    step: str,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    from pipeline import connect

    commit = os.environ["SF_COMMIT"]
    connection = connect(WORKLOADS[0])
    try:
        cursor = RecordingCursor(
            connection.cursor(), record_path, commit=commit, run_ids=run_ids, step=step,
        )
        cursor.execute(
            "SELECT QUERY_ID, QUERY_TYPE, QUERY_TAG, START_TIME "
            "FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER("
            "END_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s),RESULT_LIMIT=>10000))",
            (since,),
        )
        names = _columns(cursor)
        rows = [dict(zip(names, row)) for row in cursor.fetchall()]
        if len(rows) >= 10000:
            raise RuntimeError("QUERY_HISTORY_BY_USER reached its 10000 row limit")
        for workload in WORKLOADS:
            database = attr.names([workload])[f"db_{workload}"]
            warehouse = attr.names([workload])[f"wh_{workload}"]
            cursor.execute(
                f"SELECT QUERY_ID, QUERY_TYPE, QUERY_TAG, START_TIME "
                f"FROM TABLE({database}.INFORMATION_SCHEMA.QUERY_HISTORY_BY_WAREHOUSE("
                f"WAREHOUSE_NAME=>'{warehouse}',END_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s),"
                "RESULT_LIMIT=>10000))",
                (since,),
            )
            warehouse_rows = [dict(zip(_columns(cursor), row)) for row in cursor.fetchall()]
            if len(warehouse_rows) >= 10000:
                raise RuntimeError(f"QUERY_HISTORY_BY_WAREHOUSE reached its limit for {workload}")
            rows.extend(warehouse_rows)
        expected_ids = set(run_ids.values())
        matches_by_id = {}
        for row in rows:
            query_tag = _query_tag(row)
            if query_tag.get("run_id") in expected_ids:
                matches_by_id[row["query_id"]] = row
        matches = list(matches_by_id.values())
        update_query_record(
            record_path, commit=commit, run_ids=run_ids, step=step,
            query_ids=[str(row["query_id"]) for row in matches],
        )
        return matches, Counter(str(row.get("query_type") or "UNKNOWN").upper() for row in matches)
    finally:
        connection.close()


def _query_tag(row: dict[str, Any]) -> dict[str, Any]:
    try:
        tag = json.loads(row.get("query_tag") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return tag if isinstance(tag, dict) else {}


def audit_plan(run_ids: dict[str, str], *, since: str, record_path: Path) -> Counter[str]:
    rows, counts = query_history(
        run_ids, since=since, record_path=record_path, step="plan_audit",
    )
    non_read_only = [row for row in rows if str(row.get("query_type") or "").upper() not in READ_ONLY_QUERY_TYPES]
    for run_id in run_ids.values():
        count = sum(1 for row in rows if _query_tag(row).get("run_id") == run_id)
        print(f"AUDIT run_id={run_id} query_count={count}")
    print(f"AUDIT query_types={json.dumps(dict(sorted(counts.items())), sort_keys=True)}")
    print(f"AUDIT non_read_only={len(non_read_only)}")
    if non_read_only:
        raise RuntimeError(f"Read-only plan audit found non-read-only queries: {non_read_only}")
    return counts


def _run_step(name: str, command: list[str], *, env: dict[str, str], results_dir: Path) -> None:
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    log_dir = results_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{name}.log"
    log_path.write_text(completed.stdout + completed.stderr)
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="")
    if completed.returncode:
        raise subprocess.CalledProcessError(completed.returncode, command)


def plan(results_dir: Path) -> int:
    commit = os.environ.get("SF_COMMIT") or attr.current_commit(str(ROOT))
    env, run_ids = prepare_run_environment(commit)
    results_dir.mkdir(parents=True, exist_ok=True)
    record_path = results_dir / "query_ids.json"
    write_query_record(record_path, commit, run_ids)
    started = utc_now()
    apply = str(ROOT / "workloads/snowflake/apply.sh")
    _run_step(
        "foundation_dry_run", [apply, "builder"], env={**env, "DRY_RUN": "1", "PIPELINE": "0"},
        results_dir=results_dir,
    )
    query_history(run_ids, since=started, record_path=record_path, step="foundation_dry_run")
    _run_step(
        "pipeline_migrations_dry_run", [apply, "builder"],
        env={**env, "DRY_RUN": "1", "PIPELINE": "1"}, results_dir=results_dir,
    )
    query_history(run_ids, since=started, record_path=record_path, step="pipeline_migrations_dry_run")
    _run_step(
        "dbt_compile",
        ["uv", "run", "--python", "3.12", "--with", "dbt-snowflake==1.9.4",
         "python", "workloads/dbt/run.py", "--compile-only", "--results-dir", str(results_dir)],
        env=env, results_dir=results_dir,
    )
    query_history(run_ids, since=started, record_path=record_path, step="dbt_compile")

    from deploy_usage_app import streamlit_ddl
    from deploy_usage_task import task_sql

    task_run_id = run_ids["doc_usage_dashboard"]
    endpoint = attr.Endpoint.from_csid(CONSUMERS["doc_usage_dashboard"][0], "doc_usage_dashboard")
    print("RENDERED TASK DDL:")
    print(task_sql(commit, task_run_id))
    print("RENDERED STREAMLIT DDL:")
    print(streamlit_ddl(commit, task_run_id))
    print("RENDERED STREAMLIT QUERY TAG SQL:")
    print(attr.streamlit_query_tag_sql(endpoint, commit=commit, run_id=task_run_id))
    print(f"ROLLBACK_TARGET {rollback_target()}")
    changes, warnings = provenance_changes(commit, results_dir, mode="deploy", record_path=record_path)
    for warning in warnings:
        print(f"WARNING: {warning}")
    print("PROVENANCE DIFF:")
    print_provenance_diff(changes)
    audit_plan(run_ids, since=started, record_path=record_path)
    rows, _ = query_history(
        run_ids, since=started, record_path=record_path, step="final_query_history",
    )
    print(f"QUERY_IDS {json.dumps([row['query_id'] for row in rows])}")
    print(f"RESULTS {results_dir}")
    return 0


def record_dbt_results(results_dir: Path, record_path: Path, commit: str) -> None:
    _, query_ids = redeployed_from_results(results_dir)
    update_query_record(
        record_path, commit=commit, run_ids=run_ids_from_env(),
        step="dbt_build", query_ids=query_ids,
    )


def provenance_command(args: argparse.Namespace) -> int:
    changes, warnings = provenance_changes(
        args.commit, args.results, mode=args.mode, record_path=args.record,
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    print_provenance_diff(changes)
    if args.write:
        for path, rendered in changes.items():
            path.write_text(rendered)
        print(f"Updated {len(changes)} provenance files")
    elif changes:
        print(f"{len(changes)} provenance files would change")
        return 1
    return 0


def collect_command(args: argparse.Namespace) -> int:
    run_ids = run_ids_from_env()
    rows, counts = query_history(
        run_ids, since=args.since, record_path=args.record, step=args.step,
    )
    print(f"QUERY_HISTORY step={args.step} counts={json.dumps(dict(counts), sort_keys=True)}")
    print(f"QUERY_IDS {json.dumps([row['query_id'] for row in rows])}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    provenance = sub.add_parser("provenance")
    provenance.add_argument("--commit", required=True)
    provenance.add_argument("--mode", required=True, choices=("deploy", "rollback"))
    provenance.add_argument("--results", type=Path, required=True)
    provenance.add_argument("--record", type=Path)
    mode = provenance.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    rollback = sub.add_parser("rollback-target")
    rollback.add_argument("--from", dest="from_commit")
    init = sub.add_parser("init-record")
    init.add_argument("--commit", required=True)
    init.add_argument("--record", type=Path, required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--record", type=Path, required=True)
    collect.add_argument("--step", required=True)
    collect.add_argument("--since", default="1970-01-01T00:00:00Z")
    dbt = sub.add_parser("record-dbt-results")
    dbt.add_argument("--commit", required=True)
    dbt.add_argument("--results", type=Path, required=True)
    dbt.add_argument("--record", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "rollback-target":
        print(rollback_target(args.from_commit))
        return 0
    if args.command == "init-record":
        _, run_ids = prepare_run_environment(args.commit)
        write_query_record(args.record, args.commit, run_ids)
        return 0
    if args.command == "collect":
        return collect_command(args)
    if args.command == "record-dbt-results":
        record_dbt_results(args.results, args.record, args.commit)
        return 0
    if args.command == "provenance":
        return provenance_command(args)
    return plan(args.results_dir)


if __name__ == "__main__":
    raise SystemExit(main())
