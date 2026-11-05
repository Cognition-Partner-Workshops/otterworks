"""Attributed, forward-only Snowflake delivery and model/app rollback."""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from contextlib import closing, contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import snowflake.connector
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from schemachange.config.ChangeHistoryTable import ChangeHistoryTable
from schemachange.config.DeployConfig import DeployConfig
from schemachange.deploy import deploy as apply_migrations

REPO = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "workloads/attribution"))
import sf_attribution as sf  # noqa: E402
import validate_provenance as vp  # noqa: E402
from workloads.foundation import apply as foundation  # noqa: E402

WORKLOADS = ("doc_usage_dashboard", "doc_search_api", "churn_model")
APPEND_ONLY_AUDIT_TABLES = {"PIPELINE_REFRESH_RUNS": "REFRESHED_AT"}


def now():
    return datetime.now(timezone.utc).isoformat()


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args], text=True).strip()


def checked_commit(value, dry_run=False):
    if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
        raise ValueError("commit must be a real 40-hex git revision")
    if dry_run:
        exists = subprocess.run(["git", "-C", str(REPO), "cat-file", "-t", value],
                                capture_output=True, text=True)
        if exists.returncode or exists.stdout.strip() != "commit" or value.lower() != git("rev-parse", "HEAD"):
            raise ValueError("dry-run commit must exist locally and equal HEAD")
        return value.lower()
    refs = git("for-each-ref", "--format=%(refname)", "refs/remotes/origin").splitlines()
    if not any(subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", value, ref],
                              capture_output=True).returncode == 0 for ref in refs):
        raise ValueError("commit must be an ancestor of a pushed origin branch; fetch origin first")
    return value.lower()


def module(root, relative, name):
    spec = importlib.util.spec_from_file_location(name, root / relative)
    result = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str((root / relative).parent))
    spec.loader.exec_module(result)
    return result


def parameters(workload, commit, run_id, phase):
    session = os.environ.get("DEVIN_SESSION_URL")
    if phase == "dev" and not session:
        raise ValueError("DEVIN_SESSION_URL required outside GitHub Actions")
    params = sf.connection_params(sf.endpoint(sf.workload_csids(workload)[0]), phase=phase,
                                  account=os.environ["SNOWFLAKE_EXT_ACCOUNT"],
                                  private_key_file="in-memory-only", commit=commit,
                                  run_id=run_id, session_url=session if phase == "dev" else None,
                                  role="DEVIN_EXT_ROLE")
    params.pop("private_key_file")
    key = serialization.load_pem_private_key(os.environ["SNOWFLAKE_EXT_PRIVATE_KEY"].encode(), None)
    params.update(user=os.environ["SNOWFLAKE_EXT_USER"], private_key=der(key))
    return params


def der(key):
    return key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


class GateFailure(RuntimeError):
    def __init__(self, gate, tests=()):
        super().__init__(gate)
        self.gate, self.tests = gate, list(tests)


def installation_object(statement, phase="installer"):
    sql = re.sub(r"/\*.*?\*/|--[^\n]*", "", statement, flags=re.S).strip()
    name = r'([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)'
    ddl = re.match(r"(?:CREATE\s+(?:OR\s+REPLACE\s+)?|ALTER\s+|COMMENT\s+ON\s+|GRANT\s+.+?\s+ON\s+)"
                   r"(PROCEDURE|TASK|STREAMLIT|TABLE|STAGE|WAREHOUSE|DATABASE|SCHEMA|USER|RESOURCE\s+MONITOR)\s+"
                   r"(?:IF\s+NOT\s+EXISTS\s+)?" + name, sql, re.I | re.S)
    if ddl:
        kind = "migration" if phase == "migration" else re.sub(r"\s+", "_", ddl[1].lower())
        return kind, ddl[2].upper()
    call = re.match(r"CALL\s+" + name + r"\s*\(", sql, re.I)
    if call and ".REFRESH_" in call[1].upper():
        return "model_refresh", call[1].upper().replace(".REFRESH_", ".")
    put = re.match(r"PUT\s+.+?\s+@" + name, sql, re.I | re.S)
    if put:
        return "stage", put[1].upper()
    return None


class Log:
    def __init__(self, path, revision=None, run_id=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.queries = []
        self.revision, self.run_id = revision, run_id
        self.installed = {}
        self.phase = "installer"

    def record(self, statement, query_id=None, success=True):
        recorded_at = now()
        obj = installation_object(statement, self.phase) if self.revision else None
        if obj and query_id:
            entry = self.installed.get(obj)
            if entry is None:
                entry = dict(type=obj[0], name=obj[1], revision=self.revision, run_id=self.run_id,
                             status="installed", installed_at=recorded_at, query_ids=[],
                             timestamp_source="statement_completed_at", readback={
                                 "status": "not_checked", "reason": "Statement execution recorded; independent readback not performed."})
                self.installed[obj] = entry
            if query_id not in entry["query_ids"]:
                entry["query_ids"].append(query_id)
                entry["installed_at"] = recorded_at
                if not success:
                    entry["status"] = "failed"
        if success:
            self.queries.append((statement, query_id))
        with self.path.open("a") as handle:
            handle.write(json.dumps({"statement": statement, "query_id": query_id, "success": success,
                                     "recorded_at": recorded_at,
                                     "installation_query_id_unavailable": bool(obj and not query_id)}) + "\n")


@contextmanager
def trace_queries(log):
    from snowflake.connector.cursor import SnowflakeCursor

    original = SnowflakeCursor.execute

    def traced(cursor, command, *args, **kwargs):
        success = False
        try:
            result = original(cursor, command, *args, **kwargs)
            success = True
            return result
        finally:
            log.record(command, cursor.sfqid, success)

    with patch.object(SnowflakeCursor, "execute", traced):
        yield


def execute(conn, sql, log):
    with conn.cursor() as cur:
        success = False
        try:
            cur.execute(sql)
            success = True
            return cur.fetchall()
        finally:
            log.record(sql, cur.sfqid, success)


def snapshot(conn, log, audit_cutoff=None):
    db = sf.database_name("churn_model")
    tables = execute(conn, f"SELECT TABLE_NAME FROM {db}.INFORMATION_SCHEMA.TABLES "
                     "WHERE TABLE_SCHEMA='APP' AND TABLE_TYPE='BASE TABLE' "
                     "AND TABLE_NAME <> 'WEEKLY_CHURN_SCORES' ORDER BY TABLE_NAME", log)
    result = {}
    for (table,) in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        predicate = ""
        if table in APPEND_ONLY_AUDIT_TABLES:
            if audit_cutoff is None:
                raise GateFailure("audit_snapshot_cutoff_missing")
            predicate = f" WHERE {APPEND_ONLY_AUDIT_TABLES[table]} < {sf.sql_string(audit_cutoff)}::TIMESTAMP_LTZ"
        result[table] = execute(conn, f"SELECT COUNT(*), HASH_AGG(*) FROM {db}.APP.{quoted}{predicate}", log)[0]
    if not result:
        raise GateFailure("churn_retained_tables_missing")
    log.record("retained_table_snapshot " + json.dumps(result, default=str))
    return result


def migrate(root, workload, params, log):
    history = ChangeHistoryTable(table_name=workload.upper(), schema_name="CHANGE_HISTORY",
                                 database_name=foundation.HISTORY_DATABASE)
    original = snowflake.connector.connect

    def connect(**kwargs):
        kwargs["private_key"] = params["private_key"]
        return original(**kwargs)

    with patch("snowflake.connector.connect", side_effect=connect):
        session = foundation.new_session(params, history)
    original_query = session.execute_snowflake_query
    original_record = session.record_change_history
    applied = []

    def query(query, *args, **kwargs):
        try:
            cursors = original_query(query, *args, **kwargs)
            for cur in cursors:
                log.record(cur.query, cur.sfqid)
            return cursors
        except Exception as exc:
            log.record(str(query), getattr(exc, "sfqid", None), False)
            raise

    def record(*args, **kwargs):
        original_record(*args, **kwargs)
        script = kwargs.get("script", args[0] if args else None)
        status = kwargs.get("status", args[3] if len(args) > 3 else None)
        if status == "Success":
            entry = {"version": str(getattr(script, "version", "")), "script": script.name}
            applied.append(entry)
            log.record("migration_applied " + json.dumps(entry))

    try:
        with patch.object(session, "execute_snowflake_query", side_effect=query), \
                patch.object(session, "record_change_history", side_effect=record):
            apply_migrations(config=DeployConfig(root_folder=root / "workloads" / workload / "migrations",
                             change_history_table=history, create_change_history_table=False,
                             config_vars=foundation.template_vars(workload)), session=session)
        return applied
    finally:
        session.con.close()


def dbt(runtime, workload, command, selector, params, log, artifacts):
    with patch.object(runtime, "parameters", return_value=params), patch.dict(os.environ, {
        "PIPELINE_DBT_TARGET": str(artifacts / "target"), "PIPELINE_DBT_LOG": str(artifacts / "logs")
    }):
        try:
            result = runtime.dbt(workload, command, selector)
        except RuntimeError:
            path = artifacts / "target/run_results.json"
            data = json.loads(path.read_text()) if path.exists() else {"results": []}
            failures = [r["unique_id"] for r in data["results"] if r["status"] not in ("pass", "success")]
            raise GateFailure(f"dbt_{command}", failures) from None
    rows = getattr(result.result, "results", result.result)
    for row in rows if isinstance(rows, list) else []:
        log.record(str(getattr(row.node, "compiled_code", row.node.name)),
                   getattr(row, "adapter_response", {}).get("query_id"))
    count = len(rows) if isinstance(rows, list) else 0
    if count == 0:
        raise GateFailure(f"dbt_{command}_empty_selection")
    return count


def streamlit(app, params, commit, log):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                          serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    with closing(snowflake.connector.connect(**params)) as admin:
        try:
            execute(admin, f"ALTER USER {app.EP.service_user} SET RSA_PUBLIC_KEY_2 = "
                    f"{sf.sql_string(app._key_body(public))}", log)
            service = {**params, "user": app.EP.service_user, "role": app.APP_ROLE, "private_key": der(key)}
            with tempfile.TemporaryDirectory() as stage, closing(snowflake.connector.connect(**service)) as conn:
                app.build_stage_dir(stage, commit, sf.make_run_id("doc_usage_dashboard", "runtime"))
                for sql in app.deploy_sql(stage):
                    execute(conn, sql, log)
        finally:
            execute(admin, f"ALTER USER {app.EP.service_user} UNSET RSA_PUBLIC_KEY_2", log)


def replace_block(text, key, value):
    node = yaml.compose(text)
    for i, (k, v) in enumerate(node.value):
        if k.value == key:
            end = node.value[i + 1][0].start_mark.index if i + 1 < len(node.value) else len(text)
            # Node end marks include trailing comments; keep those comments verbatim.
            content = text[k.start_mark.index:end]
            trailing = re.search(r"((?:[ \t]*#.*\n|[ \t]*\n)+)$", content)
            suffix = trailing.group(0) if trailing else ""
            # Keep following top-level comments and every unrelated byte intact.
            return text[:k.start_mark.index] + yaml.safe_dump({key: value}, sort_keys=False) + suffix + text[end:]
    return text.rstrip() + "\n" + yaml.safe_dump({key: value}, sort_keys=False)


def mark_configuration(text, queries):
    query_id = next((qid for sql, qid in queries if qid and
                     re.search(r"ALTER\s+WAREHOUSE\s+WH_DOC_SEARCH_API\s+SET\s+AUTO_SUSPEND\s*=\s*900", sql, re.I)), None)
    if not query_id:
        return text
    node = yaml.compose(text)
    for key, entries in node.value:
        if key.value != "configuration_changes":
            continue
        for entry in reversed(entries.value):
            fields = {k.value: v for k, v in entry.value}
            if fields["migration"].value.endswith("V1.0.1__restore_auto_suspend.sql"):
                status = fields["status"]
                text = text[:status.start_mark.index] + "applied" + text[status.end_mark.index:]
                # The query id is new metadata, never rewrite the existing entry/comments.
                end = text.index("\n", status.start_mark.index)
                if "applied_query_id" not in fields:
                    text = text[:end] + f"\n    applied_query_id: {query_id}" + text[end:]
    return text


def provenance(path, attempted, deployed, write=False, queries=(), installed=()):
    text = path.read_text()
    doc = vp.load(path)
    previous = doc.get("deployment", {}).get("deployed")
    block = {"attempted": attempted, "deployed": deployed if deployed is not None else previous}
    entries = []
    positions = {}
    for entry in doc.get("deployment", {}).get("installed", []):
        key = (entry["type"], entry["name"])
        if entry["type"] != "runtime_source" and key in positions:
            entries[positions[key]] = entry
        else:
            positions[key] = len(entries)
            entries.append(entry)
    for entry in installed:
        key = (entry["type"], entry["name"])
        if entry["type"] == "runtime_source":
            if entry not in entries:
                entries.append(entry)
        elif key in positions:
            entries[positions[key]] = entry
        else:
            positions[key] = len(entries)
            entries.append(entry)
    if entries or "installed" in doc.get("deployment", {}):
        block["installed"] = entries
    updated = replace_block(mark_configuration(text, queries), "deployment", block)
    errors = vp.validate(yaml.safe_load(updated), path)
    if errors:
        raise ValueError("invalid deployment provenance: " + "; ".join(errors))
    print("".join(difflib.unified_diff(text.splitlines(True), updated.splitlines(True),
                                     fromfile=str(path), tofile=str(path))))
    if write:
        path.write_text(updated)


def offline(root, runtime, workload, artifacts):
    env = {**os.environ, "PIPELINE_DATABASE": sf.database_name(workload)}
    for cmd in ("parse", "ls"):
        args = [str(Path(sys.executable).with_name("dbt")), cmd, "--project-dir", str(root / "workloads/pipeline"),
                "--profiles-dir", str(root / "workloads/pipeline"),
                "--target-path", str(artifacts / "target"), "--log-path", str(artifacts / "logs")]
        if cmd == "ls":
            args += ["--select", f"{runtime.MODELS[workload]} tag:dq_{workload}",
                     "--output", "json"]
        result = subprocess.run(args, env=env, check=True, text=True, capture_output=True)
        print(result.stdout)
        if cmd == "ls":
            nodes = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{"')]
            if not any(node.get("resource_type") == "model" and node["name"] == runtime.MODELS[workload]
                       for node in nodes):
                raise GateFailure("dbt_model_empty_selection")
            tests = [node for node in nodes if node.get("resource_type") == "test"]
            if not tests:
                raise GateFailure("dbt_test_empty_selection")
            return len(tests)


def install(runtime, workload, params, commit, artifacts, dry_run=False):
    class RenderCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            print(sql)
            obj = installation_object(sql)
            if obj:
                print("planned_install " + json.dumps(dict(type=obj[0], name=obj[1], revision=commit)))

        def fetchall(self):
            return []

    class RenderConnection:
        def cursor(self):
            return RenderCursor()

        def close(self):
            pass

    original_dbt = runtime.dbt

    def compile_model(workload, command, selector):
        if not dry_run:
            return original_dbt(workload, command, selector)
        arguments = ["compile", "--no-introspect", "--no-populate-cache", "--project-dir", str(runtime.ROOT),
                     "--profiles-dir", str(runtime.ROOT), "--target-path", str(artifacts / "target"),
                     "--log-path", str(artifacts / "logs"), "--select", selector]
        with patch("snowflake.connector.connect", side_effect=AssertionError("offline connection forbidden")):
            result = runtime.dbtRunner().invoke(arguments)
        if not result.success:
            raise GateFailure("offline_compile")
        return result

    with patch.object(runtime, "WORKLOADS", (workload,)), \
            patch.object(runtime, "MODELS", {workload: runtime.MODELS[workload]}), \
            patch.object(runtime, "parameters", return_value=params), \
            patch.object(runtime, "dbt", side_effect=compile_model), \
            patch.object(runtime.sf, "resolve_commit", return_value=commit), \
            patch.dict(os.environ, {"PIPELINE_DBT_TARGET": str(artifacts / "target"),
                                    "PIPELINE_DBT_LOG": str(artifacts / "logs"),
                                    "PIPELINE_DATABASE": sf.database_name(workload),
                                    "SNOWFLAKE_EXT_USER": os.environ.get("SNOWFLAKE_EXT_USER", "offline")}), \
            (patch("snowflake.connector.connect", return_value=RenderConnection()) if dry_run else nullcontext()):
        runtime.deploy()


def run_workload(root, workload, args, commit, attempted_commit):
    phase = "runtime" if os.environ.get("GITHUB_ACTIONS") == "true" else "dev"
    run_id = sf.make_run_id(workload, phase)
    attempted = dict(commit=attempted_commit, mode=args.mode, run_id=run_id, started_at=now(),
                     finished_at=now(), status="succeeded", failed_step=None, gate=None, failing_tests=[])
    deployed = None
    objects = []
    failed_gates = []
    runtime = module(root, "workloads/pipeline/runtime.py", "cd_runtime")
    app = module(root, "workloads/doc_usage_dashboard/deploy.py", "cd_app")
    step = "migrations"
    log = None
    try:
        if args.dry_run:
            versions = []
            for name, sql in foundation.render(root / "workloads" / workload / "migrations",
                                                foundation.template_vars(workload)):
                print(f"-- {name}\n{sql}")
                versions.append(name)
            if args.mode != "rollback":
                objects.append(dict(type="migrations", name=workload,
                                    detail="planned; applied history checked only during deploy: " + ", ".join(versions)))
            with tempfile.TemporaryDirectory() as folder:
                step = "offline_dbt"
                count = offline(root, runtime, workload, Path(folder))
                install(runtime, workload, {}, commit, Path(folder), dry_run=True)
                objects.append(dict(type="model", name=runtime.MODELS[workload], detail="planned build"))
                objects.append(dict(type="tests", name=workload, detail=f"{count} selected; planned gate"))
                if workload == "doc_usage_dashboard":
                    app.build_stage_dir(folder, commit, sf.make_run_id(workload, "runtime"))
                    print("\n".join(app.deploy_sql(folder)))
                    objects.append(dict(type="streamlit", name=app.APP, detail="planned live version"))
        else:
            log = Log(Path(args.log_dir) / f"{workload}-{args.mode}-{run_id}.jsonl", commit, run_id)
            params = parameters(workload, commit, run_id, phase)
            with trace_queries(log), closing(snowflake.connector.connect(**params)) as conn:
                step = "churn_retained_baseline"
                cutoff = attempted["started_at"]
                if workload == "churn_model":
                    attempted["retained_table_policy"] = (
                        "PIPELINE_REFRESH_RUNS append-only audit: preserve rows with REFRESHED_AT < " + cutoff
                        + "; full-table equality for every other retained table")
                before = snapshot(conn, log, cutoff) if workload == "churn_model" else None
                primary_error = None
                try:
                    step = "migrations"
                    if args.mode != "rollback":
                        log.phase = "migration"
                        try:
                            versions = migrate(root, workload, params, log)
                        finally:
                            log.phase = "installer"
                        objects.append(dict(type="migrations", name=workload, detail=json.dumps(versions, default=str)))
                    step = "install_runtime"
                    install(runtime, workload, params, commit, log.path.parent / run_id)
                    objects.append(dict(type="procedure", name=runtime.procedure_name(workload), detail="installed from selected commit"))
                    objects.append(dict(type="task", name=sf.task_name(workload), detail="installed from selected commit"))
                    step = "dbt_run"
                    dbt(runtime, workload, "run", runtime.MODELS[workload], params, log, log.path.parent / run_id)
                    objects.append(dict(type="model", name=runtime.MODELS[workload], detail="built"))
                    step = "dbt_test"
                    count = dbt(runtime, workload, "test", f"{runtime.MODELS[workload]} tag:dq_{workload}",
                                params, log, log.path.parent / run_id)
                    objects.append(dict(type="tests", name=workload, detail=f"{count} passed"))
                except Exception as exc:
                    primary_error = exc
                finally:
                    if before is not None:
                        try:
                            after = snapshot(conn, log, cutoff)
                        except Exception as exc:
                            failed_gates.append({
                                "gate": "retained_tables_unchanged",
                                "detail": "after snapshot failed: " + type(exc).__name__,
                            })
                        else:
                            if after != before:
                                changed = sorted(set(before) | set(after))
                                changed = [name for name in changed if before.get(name) != after.get(name)]
                                failed_gates.append({
                                    "gate": "retained_tables_unchanged",
                                    "detail": "changed tables: " + ", ".join(changed),
                                })
                        attempted["retained_table_result"] = "failed" if failed_gates else "passed"
                if failed_gates and primary_error is None:
                    step = "churn_retained_tables"
                    primary_error = GateFailure("retained_tables_unchanged")
                if primary_error is not None:
                    raise primary_error
                if workload == "doc_usage_dashboard":
                    step = "streamlit"
                    streamlit(app, params, commit, log)
                    objects.append(dict(type="streamlit", name=app.APP, detail="live version"))
        deployed = dict(commit=commit, mode=args.mode, run_id=run_id, deployed_at=now(), objects=objects)
    except Exception as exc:
        attempted.update(status="failed", failed_step=step,
                         gate=exc.gate if isinstance(exc, GateFailure) else step,
                         failing_tests=exc.tests if isinstance(exc, GateFailure) else [])
        if failed_gates:
            attempted["failed_gates"] = failed_gates
        print(f"{workload}: named gate failure {attempted['gate']} ({type(exc).__name__})")
    finally:
        attempted["finished_at"] = now()
        if log:
            log.record("deployment_attempt " + json.dumps(attempted))
        provenance(REPO / "workloads" / workload / "provenance.yaml", attempted, deployed,
                   args.write_provenance and not args.dry_run, log.queries if log else (),
                   installed=list(log.installed.values()) if log else ())
    return attempted["status"] == "succeeded"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dry-run", "deploy", "rollback"))
    parser.add_argument("--workload", choices=("all", *WORKLOADS), default="all")
    parser.add_argument("--commit")
    parser.add_argument("--to")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-provenance", action="store_true")
    parser.add_argument("--log-dir", default=str(Path.home() / ".local/share/otterworks-cd"))
    args = parser.parse_args(argv)
    args.dry_run = args.dry_run or args.mode == "dry-run"
    value = args.commit or git("rev-parse", "HEAD")
    commit = checked_commit(value, dry_run=True) if args.mode == "dry-run" else checked_commit(value)
    target = None
    if args.mode != "dry-run":
        target = checked_commit(args.to or git("rev-parse", f"{commit}^1"))
        print(f"Rollback target: {target}; migrations are forward-only")
    selected = WORKLOADS if args.workload == "all" else (args.workload,)
    if not args.dry_run or args.mode == "rollback" or commit != git("rev-parse", "HEAD"):
        with tempfile.TemporaryDirectory(prefix="otterworks-cd-") as folder:
            tree = Path(folder) / "tree"
            deployed_commit = target if args.mode == "rollback" else commit
            if args.dry_run:
                tree.mkdir()
                archive = subprocess.check_output(
                    ["git", "-C", str(REPO), "archive", deployed_commit, "--", "workloads"]
                )
                with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                    tar.extractall(tree, filter="data")
            else:
                git("worktree", "add", "--detach", str(tree), deployed_commit)
            try:
                results = [run_workload(tree, w, args, deployed_commit, commit) for w in selected]
            finally:
                if not args.dry_run:
                    git("worktree", "remove", str(tree))
    else:
        results = [run_workload(REPO, w, args, commit, commit) for w in selected]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
