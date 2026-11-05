import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

SPEC = importlib.util.spec_from_file_location("snowflake_cd", Path(__file__).parents[1] / "cd.py")
cd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cd)


def attempt(status="succeeded"):
    return dict(commit="a" * 40, mode="deploy", run_id="test-run", started_at=cd.now(),
                finished_at=cd.now(), status=status, failed_step="dbt_test" if status == "failed" else None,
                gate="dbt_test" if status == "failed" else None, failing_tests=[])


def deployed():
    return dict(commit="b" * 40, mode="deploy", run_id="old-run", deployed_at=cd.now(), objects=[])


def installed(name="DB.APP.REFRESH_MODEL", revision="b" * 40):
    return dict(type="procedure", name=name, revision=revision, run_id="install-run", status="installed",
                installed_at=cd.now(), query_ids=["install-query"], readback=dict(status="not_checked", reason="No readback"))


def test_install_writer_replaces_same_object_and_preserves_others(tmp_path):
    path = tmp_path / "churn_model/provenance.yaml"
    path.parent.mkdir()
    path.write_text((cd.REPO / "workloads/churn_model/provenance.yaml").read_text())
    previous_entries = yaml.safe_load(path.read_text())["deployment"]["installed"]
    first, other = installed(), installed("DB.APP.OTHER")
    cd.provenance(path, attempt(), deployed(), True, installed=[first, other])
    replacement = installed(revision="c" * 40)
    cd.provenance(path, attempt("failed"), None, True, installed=[replacement])
    entries = yaml.safe_load(path.read_text())["deployment"]["installed"]
    assert [e for e in entries if e["name"] == first["name"]] == [replacement]
    assert other in entries
    assert all(entry in entries for entry in previous_entries)
    assert yaml.safe_load(path.read_text())["deployment"]["deployed"] is not None


@pytest.mark.parametrize("append", [False, True])
def test_runtime_source_history_is_append_only(tmp_path, append):
    path = tmp_path / "doc_usage_dashboard/provenance.yaml"
    path.parent.mkdir()
    doc = yaml.safe_load((cd.REPO / "workloads/doc_usage_dashboard/provenance.yaml").read_text())
    source = "workloads/doc_usage_dashboard/responder/freshness.py"
    records = [e for e in doc["deployment"]["installed"] if e["type"] == "runtime_source" and e["name"] == source]
    assert len(records) == 2
    first, second = records
    incoming = dict(second, revision="c" * 40) if append else second
    if append:
        next(e for e in doc["endpoints"] if e["csid"] == "cs_doc_usage_dashboard_freshness_responder")["runtime_source"]["revision"] = incoming["revision"]
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    cd.provenance(path, attempt(), deployed(), True, installed=[incoming, incoming])
    written = yaml.safe_load(path.read_text())
    history = [e for e in written["deployment"]["installed"] if e["type"] == "runtime_source" and e["name"] == source]
    assert history == [first, second] + ([incoming] if append else [])
    responder = cd.module(cd.REPO, "workloads/doc_usage_dashboard/responder/freshness.py", "history_responder")
    assert responder.deployed_revision(path) == incoming["revision"]
    assert cd.vp.validate(written, path) == []


@pytest.fixture
def fork_repo(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init")
    git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "base")
    base = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/origin/main", base)
    git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-m", "fork")
    head = git("rev-parse", "HEAD")
    git("checkout", "--detach", head)
    monkeypatch.setattr(cd, "REPO", tmp_path)
    return base, head


def test_fork_head_dry_run(fork_repo):
    with patch.object(cd, "run_workload", return_value=True) as run:
        assert cd.main(["dry-run", "--workload", "doc_search_api"]) == 0
    assert run.call_args.args[3] == fork_repo[1]


@pytest.mark.parametrize("mode", ["deploy", "rollback"])
def test_fork_head_untrusted_for_deployment(fork_repo, mode):
    with pytest.raises(ValueError, match="pushed"):
        cd.main([mode])


@pytest.mark.parametrize("revision", ["base", "missing"])
def test_dry_run_requires_existing_head(fork_repo, revision):
    value = fork_repo[0] if revision == "base" else "f" * 40
    with pytest.raises(ValueError):
        cd.main(["dry-run", "--commit", value])


@pytest.mark.parametrize("failure", [None, "dbt_test", "install_runtime"])
def test_partial_installs_are_written_on_every_outcome(tmp_path, failure):
    root = tmp_path / "repo"
    path = root / "workloads/doc_search_api/provenance.yaml"
    path.parent.mkdir(parents=True)
    doc = yaml.safe_load((cd.REPO / "workloads/doc_search_api/provenance.yaml").read_text())
    doc["deployment"]["deployed"] = None
    doc["deployment"]["installed"] = []
    path.write_text(yaml.safe_dump(doc))
    log = cd.Log(tmp_path / "run.jsonl", "a" * 40, "run")
    runtime = SimpleNamespace(MODELS={"doc_search_api": "top_search_items"}, procedure_name=lambda w: "DB.APP.P")
    args = SimpleNamespace(mode="deploy", dry_run=False, write_provenance=True, log_dir=str(tmp_path))

    def install(*args):
        log.record("CREATE OR REPLACE PROCEDURE DB.APP.P() RETURNS VARCHAR LANGUAGE SQL AS $$ BEGIN RETURN 'ok'; END $$", "query-1")
        if failure == "install_runtime":
            raise RuntimeError("later installation failed")

    def dbt(runtime, workload, command, *args):
        if command == "test" and failure == "dbt_test":
            raise cd.GateFailure("dbt_test", ["test.bad"])
        return 1

    with patch.object(cd, "REPO", root), patch.object(cd, "module", return_value=runtime), \
            patch.object(cd, "Log", return_value=log), patch.object(cd, "parameters", return_value={}), \
            patch.object(cd.snowflake.connector, "connect", return_value=MagicMock()), \
            patch.object(cd, "migrate", return_value=[]), patch.object(cd, "install", side_effect=install), \
            patch.object(cd, "dbt", side_effect=dbt):
        assert cd.run_workload(root, "doc_search_api", args, "a" * 40, "a" * 40) == (failure is None)
    deployment = yaml.safe_load(path.read_text())["deployment"]
    assert deployment["installed"][0]["query_ids"] == ["query-1"]
    assert deployment["installed"][0]["revision"] == "a" * 40
    assert (deployment["deployed"] is None) == (failure is not None)


def test_statement_evidence_groups_ids_and_records_failure(tmp_path):
    log = cd.Log(tmp_path / "run.jsonl", "b" * 40, "rollback-run")
    log.record("CREATE OR REPLACE TASK DB.APP.T AS SELECT 1", "create-id")
    log.record("ALTER TASK DB.APP.T RESUME", "resume-id", False)
    log.record("ALTER TASK DB.APP.T RESUME", "resume-id", False)
    entry = log.installed[("task", "DB.APP.T")]
    assert entry["status"] == "failed"
    assert entry["query_ids"] == ["create-id", "resume-id"]
    assert entry["revision"] == "b" * 40 and entry["run_id"] == "rollback-run"
    log.phase = "migration"
    log.record("ALTER WAREHOUSE WH_DOC_SEARCH_API SET AUTO_SUSPEND=900", "migration-id")
    assert ("migration", "WH_DOC_SEARCH_API") in log.installed
    log.record("CREATE TABLE DB.APP.MISSING_ID (X INT)")
    assert all(e["name"] != "DB.APP.MISSING_ID" for e in log.installed.values())


@pytest.mark.parametrize("sha", ["", "main", "a" * 39, "g" * 40])
def test_bad_sha(sha):
    with pytest.raises(ValueError, match="40-hex"):
        cd.checked_commit(sha)


def test_sha_must_be_pushed():
    with patch.object(cd, "git", return_value="refs/remotes/origin/main"), \
            patch.object(cd.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
        with pytest.raises(ValueError, match="pushed"):
            cd.checked_commit("a" * 40)


def test_pushed_sha():
    with patch.object(cd, "git", return_value="refs/remotes/origin/main"), \
            patch.object(cd.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
        assert cd.checked_commit("a" * 40) == "a" * 40


def test_parameters_are_in_memory_and_attributed(monkeypatch):
    key = cd.rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(cd.serialization.Encoding.PEM, cd.serialization.PrivateFormat.PKCS8,
                            cd.serialization.NoEncryption()).decode()
    monkeypatch.setenv("SNOWFLAKE_EXT_ACCOUNT", "account")
    monkeypatch.setenv("SNOWFLAKE_EXT_USER", "external")
    monkeypatch.setenv("SNOWFLAKE_EXT_PRIVATE_KEY", pem)
    monkeypatch.setenv("DEVIN_SESSION_URL", "https://example.com/sessions/" + "a" * 32)
    for phase in ("dev", "runtime"):
        run_id = cd.sf.make_run_id("doc_search_api", phase)
        params = cd.parameters("doc_search_api", "a" * 40, run_id, phase)
        assert params["private_key"] == cd.der(key)
        assert "private_key_file" not in params
        assert params["application"] == "Devin_Demo"
        assert params["authenticator"] == "SNOWFLAKE_JWT"
        assert params["role"] == "DEVIN_EXT_ROLE"
        tag = json.loads(params["session_parameters"]["QUERY_TAG"])
        assert tag["phase"] == phase and tag["commit"] == "a" * 40
        assert ("session_url" in tag) == (phase == "dev")


def test_dev_requires_session(monkeypatch):
    monkeypatch.delenv("DEVIN_SESSION_URL", raising=False)
    with pytest.raises(ValueError, match="DEVIN_SESSION_URL"):
        cd.parameters("doc_search_api", "a" * 40, "run", "dev")


def test_failed_provenance_preserves_deployed_and_comments(tmp_path):
    path = tmp_path / "provenance.yaml"
    original = (cd.REPO / "workloads/churn_model/provenance.yaml").read_text()
    path.write_text(original)
    with patch.object(cd.vp, "validate", return_value=[]):
        cd.provenance(path, attempt(), deployed(), True)
        cd.provenance(path, attempt("failed"), None, True)
    text = path.read_text()
    assert text.startswith(original.split("\ndeployment:", 1)[0].rstrip())
    doc = yaml.safe_load(text)
    assert doc["deployment"]["deployed"] == deployed() | {"deployed_at": doc["deployment"]["deployed"]["deployed_at"]}
    assert doc["deployment"]["attempted"]["status"] == "failed"


def test_configuration_query_evidence():
    text = (cd.REPO / "workloads/doc_search_api/provenance.yaml").read_text()
    text = "\n".join(line for line in text.splitlines() if "applied_query_id:" not in line) + "\n"
    text = text.replace("status: applied", "status: planned")
    assert cd.mark_configuration(text, []) == text
    updated = cd.mark_configuration(text, [("ALTER WAREHOUSE WH_DOC_SEARCH_API SET AUTO_SUSPEND = 900", "qid")])
    entry = yaml.safe_load(updated)["configuration_changes"][0]
    assert entry["status"] == "applied" and entry["applied_query_id"] == "qid"
    assert "query_id: 01c8331c" in updated


def test_snapshot_discovers_all_retained_tables():
    with patch.object(cd, "execute", side_effect=[[("CHURN_MODEL_EVALUATION",), ("SCORES",)], [(3, 42)], [(5, 99)]]) as execute:
        assert cd.snapshot(MagicMock(), MagicMock()) == {"CHURN_MODEL_EVALUATION": (3, 42), "SCORES": (5, 99)}
        assert "WEEKLY_CHURN_SCORES" in execute.call_args_list[0].args[1]
        assert "HASH_AGG(*)" in execute.call_args_list[1].args[1]


def test_snapshot_empty_fails_closed():
    with patch.object(cd, "execute", return_value=[]), pytest.raises(cd.GateFailure, match="missing"):
        cd.snapshot(MagicMock(), MagicMock())


def test_only_explicit_audit_table_uses_frozen_cutoff():
    with patch.object(cd, "execute", side_effect=[[("CHURN_MODEL_EVALUATION",), ("PIPELINE_REFRESH_RUNS",)],
                                                [(1, 42)], [(18, 99)]]) as execute:
        cd.snapshot(MagicMock(), MagicMock(), "2026-11-05T12:00:00Z")
    assert " WHERE " not in execute.call_args_list[1].args[1]
    assert "WHERE REFRESHED_AT < '2026-11-05T12:00:00Z'::TIMESTAMP_LTZ" in execute.call_args_list[2].args[1]


def test_audit_snapshot_requires_cutoff():
    with patch.object(cd, "execute", return_value=[("PIPELINE_REFRESH_RUNS",)]), \
            pytest.raises(cd.GateFailure, match="audit_snapshot_cutoff_missing"):
        cd.snapshot(MagicMock(), MagicMock())


@pytest.mark.parametrize("dry_run", [False, True])
def test_install_reuses_selected_runtime_installer(tmp_path, capsys, dry_run):
    runtime = cd.module(cd.REPO, "workloads/pipeline/runtime.py", "test_installer_runtime")
    name = runtime.MODELS["doc_search_api"]

    def compile(*args):
        target = tmp_path / "target"
        compiled = target / "compiled/otterworks_pipeline/models"
        compiled.mkdir(parents=True, exist_ok=True)
        node = {"config": {"period": "window_end_date", "column_ddl": "x NUMBER", "columns_order": ["x"]}}
        (target / "manifest.json").write_text(json.dumps({"nodes": {f"model.otterworks_pipeline.{name}": node}}))
        (compiled / f"{name}.sql").write_text("SELECT 'selected commit model'")
        return SimpleNamespace(success=True)

    connection = MagicMock()
    with patch.object(runtime, "dbt", side_effect=compile), \
            patch.object(runtime, "dbtRunner", return_value=SimpleNamespace(invoke=compile)), \
            patch.object(cd.snowflake.connector, "connect", return_value=connection):
        cd.install(runtime, "doc_search_api", {"private_key": b"memory"}, "b" * 40, tmp_path, dry_run)
    if dry_run:
        sql = capsys.readouterr().out
    else:
        sql = "\n".join(c.args[0] for c in connection.cursor.return_value.__enter__.return_value.execute.call_args_list)
    assert "CREATE OR REPLACE PROCEDURE DB_DOC_SEARCH_API" in sql
    assert "SELECT 'selected commit model'" in sql
    if dry_run:
        assert 'planned_install {"type": "procedure"' in sql
    assert "CREATE OR REPLACE TASK" in sql and "b" * 40 in sql
    assert "DB_CHURN_MODEL" not in sql


def test_ephemeral_slot_cleanup_on_deploy_failure():
    app = SimpleNamespace(EP=SimpleNamespace(service_user="SVC_TEST"), APP_ROLE="APP_ROLE",
                          _key_body=lambda pem: "public-only", build_stage_dir=MagicMock(side_effect=RuntimeError("broken")))
    with patch.object(cd.snowflake.connector, "connect", return_value=MagicMock()), \
            patch.object(cd, "execute") as execute, pytest.raises(RuntimeError):
        cd.streamlit(app, {}, "a" * 40, MagicMock())
    statements = [c.args[1] for c in execute.call_args_list]
    assert "SET RSA_PUBLIC_KEY_2" in statements[0]
    assert statements[-1] == "ALTER USER SVC_TEST UNSET RSA_PUBLIC_KEY_2"
    assert all("SET RSA_PUBLIC_KEY =" not in sql for sql in statements)


def test_dbt_failure_names_failing_tests(tmp_path):
    (tmp_path / "target").mkdir()
    (tmp_path / "target/run_results.json").write_text(json.dumps({"results": [
        {"unique_id": "test.dq_freshness", "status": "fail"}, {"unique_id": "test.ok", "status": "pass"}]}))
    runtime = SimpleNamespace(parameters=MagicMock(), dbt=MagicMock(side_effect=RuntimeError("failure")))
    with pytest.raises(cd.GateFailure) as exc:
        cd.dbt(runtime, "churn_model", "test", "weekly_churn_scores tag:dq_churn_model", {}, MagicMock(), tmp_path)
    assert exc.value.tests == ["test.dq_freshness"]


def test_dbt_empty_fails(tmp_path):
    runtime = SimpleNamespace(parameters=MagicMock(), dbt=MagicMock(return_value=SimpleNamespace(result=[])))
    with pytest.raises(cd.GateFailure, match="empty_selection"):
        cd.dbt(runtime, "doc_search_api", "test", "model", {}, MagicMock(), tmp_path)


def test_dry_run_no_connection_no_provenance_write(tmp_path):
    args = SimpleNamespace(mode="dry-run", dry_run=True, write_provenance=True, log_dir=str(tmp_path))
    runtime = SimpleNamespace(MODELS={"doc_search_api": "top_search_items"})
    with patch.object(cd, "module", return_value=runtime), patch.object(cd, "offline") as offline, patch.object(cd, "install"), \
            patch.object(cd.snowflake.connector, "connect") as connect, patch.object(cd, "provenance") as provenance:
        assert cd.run_workload(cd.REPO, "doc_search_api", args, "a" * 40, "a" * 40)
    connect.assert_not_called()
    offline.assert_called_once()
    assert provenance.call_args.args[3] is False
    assert not provenance.call_args.kwargs["installed"]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("failure", ["migrations", "dbt_run", "dbt_test", "retained"])
def test_workload_stops_at_first_failure(tmp_path, failure):
    args = SimpleNamespace(mode="deploy", dry_run=False, write_provenance=False, log_dir=str(tmp_path))
    runtime = SimpleNamespace(MODELS={"churn_model": "weekly_churn_scores"}, procedure_name=lambda w: "proc")
    calls = []

    def migrate(*a):
        calls.append("migrations")
        if failure == "migrations":
            raise cd.GateFailure("migration_error")
        return []

    def dbt(runtime, workload, cmd, *a):
        calls.append("dbt_" + cmd)
        if failure == "dbt_" + cmd:
            raise cd.GateFailure("named_test", ["test.bad"])
        return 5

    with patch.object(cd, "module", return_value=runtime), patch.object(cd, "parameters", return_value={}), patch.object(cd, "install"), \
            patch.object(cd.snowflake.connector, "connect", return_value=MagicMock()), \
            patch.object(cd, "migrate", side_effect=migrate), patch.object(cd, "dbt", side_effect=dbt), \
            patch.object(cd, "snapshot", side_effect=[{"scores": (1, 2)}, {"scores": (2, 3)}]), \
            patch.object(cd, "provenance") as provenance:
        assert not cd.run_workload(cd.REPO, "churn_model", args, "a" * 40, "a" * 40)
    assert calls == ["migrations", "dbt_run", "dbt_test"][:{"migrations": 1, "dbt_run": 2, "dbt_test": 3, "retained": 3}[failure]]
    assert provenance.call_args.args[1]["status"] == "failed"
    assert provenance.call_args.args[2] is None
    if failure == "dbt_test":
        assert provenance.call_args.args[1]["failed_gates"] == [{
            "gate": "retained_tables_unchanged", "detail": "changed tables: scores"}]


@pytest.mark.parametrize("command", ["run", "test"])
@pytest.mark.parametrize("after", [{"scores": (1, 2)}, {"scores": (2, 3)}, RuntimeError("unavailable")])
def test_churn_after_snapshot_preserves_dbt_failure(tmp_path, command, after):
    args = SimpleNamespace(mode="deploy", dry_run=False, write_provenance=False, log_dir=str(tmp_path))
    runtime = SimpleNamespace(MODELS={"churn_model": "weekly_churn_scores"}, procedure_name=lambda w: "proc")

    def dbt(runtime, workload, cmd, *args):
        if cmd == command:
            raise cd.GateFailure("dbt_" + cmd, ["test.bad"])
        return 1

    with patch.object(cd, "module", return_value=runtime), patch.object(cd, "parameters", return_value={}), patch.object(cd, "install"), \
            patch.object(cd.snowflake.connector, "connect", return_value=MagicMock()), \
            patch.object(cd, "migrate", return_value=[]), patch.object(cd, "dbt", side_effect=dbt), \
            patch.object(cd, "snapshot", side_effect=[{"scores": (1, 2)}, after]) as snapshot, \
            patch.object(cd, "provenance") as provenance:
        assert not cd.run_workload(cd.REPO, "churn_model", args, "a" * 40, "a" * 40)
    assert snapshot.call_count == 2
    attempted = provenance.call_args.args[1]
    assert attempted["gate"] == "dbt_" + command
    assert attempted["failing_tests"] == ["test.bad"]
    assert bool(attempted.get("failed_gates")) == (after != {"scores": (1, 2)})


def test_rollback_skips_migrations_and_uses_target_root(tmp_path):
    args = SimpleNamespace(mode="rollback", dry_run=False, write_provenance=False, log_dir=str(tmp_path))
    runtime = SimpleNamespace(MODELS={"doc_search_api": "old_model"}, procedure_name=lambda w: "proc")
    with patch.object(cd, "module", return_value=runtime) as load, \
            patch.object(cd, "parameters", return_value={}), patch.object(cd, "install") as install, \
            patch.object(cd.snowflake.connector, "connect", return_value=MagicMock()), \
            patch.object(cd, "migrate") as migrate, patch.object(cd, "dbt", return_value=3) as dbt, \
            patch.object(cd, "provenance") as provenance, patch.object(cd, "Log", wraps=cd.Log) as log:
        assert cd.run_workload(tmp_path, "doc_search_api", args, "b" * 40, "a" * 40)
    migrate.assert_not_called()
    assert load.call_args_list[0].args[0] == tmp_path
    assert dbt.call_args_list[0].args[3] == "old_model"
    assert install.call_args.args[:4] == (runtime, "doc_search_api", {}, "b" * 40)
    assert log.call_args.args[1] == "b" * 40
    assert provenance.call_args.args[1]["commit"] == "a" * 40
    assert provenance.call_args.args[2]["commit"] == "b" * 40


def test_migrations_receive_in_memory_key_and_record_versions(tmp_path):
    session = MagicMock()
    cursor = SimpleNamespace(query="ALTER WAREHOUSE WH_DOC_SEARCH_API SET AUTO_SUSPEND = 900", sfqid="qid")
    session.execute_snowflake_query.return_value = [cursor]
    params = {"private_key": b"memory-key", "session_parameters": {"QUERY_TAG": "{}"}}
    log = cd.Log(tmp_path / "run.jsonl")

    def apply(*, config, session):
        assert config.change_history_table.fully_qualified.endswith(".CHANGE_HISTORY.DOC_SEARCH_API")
        assert config.create_change_history_table is False
        session.execute_snowflake_query("ALTER", None)
        session.record_change_history(script=SimpleNamespace(version="1.0.1", name="V1.0.1__restore_auto_suspend.sql"),
                                      checksum="hash", execution_time=1, status="Success", logger=None)

    def new_session(params, history):
        cd.snowflake.connector.connect(account="test", session_parameters=params["session_parameters"])
        return session

    with patch.object(cd.snowflake.connector, "connect") as connect, \
            patch.object(cd.foundation, "new_session", side_effect=new_session), \
            patch.object(cd, "apply_migrations", side_effect=apply):
        versions = cd.migrate(cd.REPO, "doc_search_api", params, log)
    assert connect.call_args.kwargs["private_key"] == b"memory-key"
    assert versions == [{"version": "1.0.1", "script": "V1.0.1__restore_auto_suspend.sql"}]
    assert log.queries[0] == (cursor.query, "qid")
    assert "migration_applied" in log.queries[1][0]
    session.con.close.assert_called_once()


def test_migrations_close_connection_on_failure(tmp_path):
    session = MagicMock()
    with patch.object(cd.foundation, "new_session", return_value=session), \
            patch.object(cd, "apply_migrations", side_effect=RuntimeError("migration failed")), \
            pytest.raises(RuntimeError):
        cd.migrate(cd.REPO, "churn_model", {"private_key": b"key"}, cd.Log(tmp_path / "log.jsonl"))
    session.con.close.assert_called_once()


def test_query_log_contains_ids_but_not_credentials(tmp_path):
    log = cd.Log(tmp_path / "log.jsonl")
    cursor = MagicMock(sfqid="query-123")
    cursor.fetchall.return_value = [(1,)]
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    assert cd.execute(conn, "SELECT COUNT(*) FROM retained", log) == [(1,)]
    content = json.loads(log.path.read_text())
    assert content["query_id"] == "query-123"
    assert content["statement"] == "SELECT COUNT(*) FROM retained"
    assert "private_key" not in log.path.read_text()


def test_failed_ddl_does_not_mark_configuration_applied(tmp_path):
    log = cd.Log(tmp_path / "log.jsonl")
    log.record("ALTER WAREHOUSE WH_DOC_SEARCH_API SET AUTO_SUSPEND = 900", "failed-id", False)
    text = (cd.REPO / "workloads/doc_search_api/provenance.yaml").read_text()
    assert cd.mark_configuration(text, log.queries) == text


def test_rollback_dry_run_uses_archive_without_git_worktree():
    calls = []

    def git(*args):
        calls.append(args)
        return "a" * 40

    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w"):
        pass
    with patch.object(cd, "git", side_effect=git), patch.object(cd, "checked_commit", side_effect=lambda s: s), \
            patch.object(cd.subprocess, "check_output", return_value=archive.getvalue()) as archive_cmd, \
            patch.object(cd, "run_workload", return_value=True) as run:
        assert cd.main(["rollback", "--dry-run", "--to", "b" * 40, "--workload", "doc_search_api"]) == 0
    assert not any(c[0] == "worktree" for c in calls)
    assert archive_cmd.call_args.args[0][-2:] == ["--", "workloads"]
    assert run.call_args.args[3] == "b" * 40
