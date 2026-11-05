import hashlib
import json
import os
import sys
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import psycopg2
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime
import source


def test_next_source_export_is_on_the_hour_before_the_task():
    now = datetime(2026, 11, 5, 23, 59, tzinfo=timezone.utc)
    assert runtime.next_export_at(now) == datetime(2026, 11, 6, tzinfo=timezone.utc)
    assert runtime.next_export_at(now.replace(minute=0)).hour == 0


def test_hourly_export_uses_runtime_attribution_and_does_not_reseed(monkeypatch):
    conn = MagicMock()
    exporter = MagicMock(return_value=Path("snapshot.json"))
    publisher = MagicMock()
    monkeypatch.setenv("POSTGRES_DSN", "local-test")
    monkeypatch.setattr(runtime.psycopg2, "connect", MagicMock(return_value=conn))
    monkeypatch.setattr(runtime, "source_export", exporter)
    monkeypatch.setattr(runtime, "publish", publisher)
    runtime.export_source()
    exporter.assert_called_once()
    publisher.assert_called_once_with(Path("snapshot.json"), phase="runtime")
    conn.close.assert_called_once()


def test_deployment_uses_a_separately_attributed_task_for_each_workload(
    tmp_path, monkeypatch
):
    nodes = {}
    compiled = tmp_path / "compiled" / "otterworks_pipeline" / "models"
    compiled.mkdir(parents=True)
    for model in runtime.MODELS.values():
        nodes[f"model.otterworks_pipeline.{model}"] = {"config": {}}
        (compiled / f"{model}.sql").write_text("select 1")
    (tmp_path / "manifest.json").write_text(json.dumps({"nodes": nodes}))
    monkeypatch.setenv("PIPELINE_DBT_TARGET", str(tmp_path))
    monkeypatch.setattr(runtime, "dbt", MagicMock())
    monkeypatch.setattr(runtime, "deploy_procedure", MagicMock())
    monkeypatch.setattr(runtime, "parameters", MagicMock(return_value={}))
    monkeypatch.setattr(runtime.snowflake.connector, "connect", MagicMock())
    deploy_sql = MagicMock(wraps=runtime.sf.task_deploy_sql)
    monkeypatch.setattr(runtime.sf, "task_deploy_sql", deploy_sql)
    runtime.deploy()
    assert deploy_sql.call_count == 3
    for call, workload in zip(deploy_sql.call_args_list, runtime.WORKLOADS):
        assert call.args[0].workload == workload
        assert call.kwargs["body"] == f"CALL {runtime.procedure_name(workload)}()"
        assert call.kwargs["schedule"] == "USING CRON 10 * * * * UTC"


def test_attributed_jwt_connection_keeps_key_only_in_memory(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setenv(
        "SNOWFLAKE_EXT_PRIVATE_KEY",
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
    )
    monkeypatch.setenv("SNOWFLAKE_EXT_ACCOUNT", "unit-test")
    monkeypatch.setenv("SNOWFLAKE_EXT_USER", "external-test-user")
    params = runtime.parameters("doc_search_api")
    assert params["authenticator"] == "SNOWFLAKE_JWT"
    assert params["role"] == "DEVIN_EXT_ROLE"
    assert params["application"] == "Devin_Demo"
    assert params["user"] == "external-test-user"
    assert isinstance(params["private_key"], bytes)
    assert "private_key_file" not in params
    tag = runtime.sf.parse_query_tag(params["session_parameters"]["QUERY_TAG"])
    assert tag["workload"] == "doc_search_api"
    assert tag["phase"] == "dev"
    assert tag["session_url"] == runtime.SESSION_URL
    assert params["session_parameters"]["TIMEZONE"] == "UTC"


def bundle_file(tmp_path, payload):
    text = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    path = tmp_path / f"snapshot_{hashlib.sha256(text.encode()).hexdigest()}.json"
    path.write_text(text + "\n")
    return path


def test_complete_immutable_bundle_is_required(tmp_path):
    payload = {
        "snapshot_date": "2026-11-02",
        "exported_at": "2026-11-02T00:00:00+00:00",
        "tables": {name: [] for name in source.TABLES},
    }
    path = bundle_file(tmp_path, payload)
    assert runtime.validate_bundle(path) == payload
    payload["tables"].pop("DOCUMENT_DOCUMENTS")
    with pytest.raises(ValueError, match="incomplete"):
        runtime.validate_bundle(bundle_file(tmp_path, payload))
    path.write_text("{}")
    with pytest.raises(ValueError, match="SHA256"):
        runtime.validate_bundle(path)


@pytest.mark.parametrize("workload", runtime.WORKLOADS)
def test_copy_and_merge_are_replay_safe_and_have_no_event_watermark(workload):
    assert "FORCE=FALSE" in runtime.copy_sql(workload)
    assert "ON_ERROR=ABORT_STATEMENT" in runtime.copy_sql(workload)
    statements = list(runtime.raw_merge_sql(workload))
    assert len(statements) == len(source.TABLES) == 8
    for statement in statements:
        assert "ROW_NUMBER() OVER(PARTITION BY _snapshot_date," in statement
        assert "ORDER BY _exported_at DESC,_row_hash DESC" in statement
        assert "WHEN NOT MATCHED THEN INSERT" in statement
        assert "t._snapshot_date=s._snapshot_date" in statement
        assert "CURRENT_DATE" not in statement
    ddl = "\n".join(runtime.bootstrap_sql(workload))
    assert "CREATE OR REPLACE TABLE" not in ddl
    assert "ALTER MASKING POLICY" not in ddl
    assert "SFEXT_20261105A" in ddl and "2026-11-19" in ddl


@pytest.mark.skipif(
    not os.environ.get("POSTGRES_DSN"), reason="requires isolated local Postgres"
)
def test_postgres_seed_export_is_deterministic_and_preserves_examples(tmp_path):
    with closing(psycopg2.connect(os.environ["POSTGRES_DSN"])) as conn:
        source.seed(conn)
        source.seed(conn)
        stamp = datetime(2026, 11, 2, tzinfo=timezone.utc)
        first = source.export(conn, tmp_path / "first", date(2026, 11, 2), stamp)
        second = source.export(conn, tmp_path / "second", date(2026, 11, 2), stamp)
        assert first.name == second.name
        assert first.read_bytes() == second.read_bytes()
        payload = runtime.validate_bundle(first)
        assert len(payload["tables"]["AUTH_USERS"]) == 2000
        assert len(payload["tables"]["DOCUMENT_DOCUMENTS"]) == 50000
        docs = payload["tables"]["DOCUMENT_DOCUMENTS"]
        assert (
            len(
                [
                    d
                    for d in docs
                    if d["owner_id"].endswith("101")
                    and not d["is_deleted"]
                    and not d["is_template"]
                ]
            )
            == 3
        )
        quotas = {q["user_id"]: q for q in payload["tables"]["ADMIN_STORAGE_QUOTAS"]}
        assert (
            quotas["00000000-0000-4000-8000-000000000101"]["used_bytes"] == 4563402752
        )


@pytest.mark.skipif(
    not os.environ.get("POSTGRES_DSN"), reason="requires local Postgres"
)
def test_monday_changes_before_first_export_preserve_source_history(
    tmp_path, monkeypatch
):
    schema = source.SOURCE_SCHEMA + "_history_test"
    monkeypatch.setattr(source, "SOURCE_SCHEMA", schema)
    with closing(psycopg2.connect(os.environ["POSTGRES_DSN"])) as conn:
        try:
            source.seed(conn)
            with conn, conn.cursor() as cur:
                cur.execute(
                    psycopg2.sql.SQL("SET LOCAL search_path TO {}").format(
                        psycopg2.sql.Identifier(schema)
                    )
                )
                cur.execute(
                    "UPDATE users SET last_login_at='2026-09-25', "
                    "updated_at='2026-11-01T01:00:00Z' WHERE id::text LIKE '%104'"
                )
                cur.execute(
                    "UPDATE admin_users SET status='suspended', "
                    "updated_at='2026-11-01T01:00:00Z' WHERE id::text LIKE '%104'"
                )
                cur.execute(
                    "UPDATE users SET last_login_at='2026-11-02T08:00:00Z', "
                    "updated_at='2026-11-02T08:00:00Z' WHERE id::text LIKE '%104'"
                )
                cur.execute(
                    "UPDATE admin_users SET status='deleted', "
                    "updated_at='2026-11-02T09:00:00Z' WHERE id::text LIKE '%104'"
                )
            first = source.export(
                conn,
                tmp_path,
                date(2026, 11, 2),
                datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
            )
            tables = runtime.validate_bundle(first)["tables"]
            user_id = "00000000-0000-4000-8000-000000000104"
            assert next(u for u in tables["AUTH_USERS"] if u["id"] == user_id)[
                "last_login_at"
            ].startswith("2026-11-02")
            assert (
                next(u for u in tables["ADMIN_ADMIN_USERS"] if u["id"] == user_id)[
                    "status"
                ]
                == "deleted"
            )
            cutoff = datetime(2026, 11, 2, tzinfo=timezone.utc)
            for table, field, expected in [
                ("AUTH_USER_STATE_HISTORY", "last_login_at", "2026-09-25"),
                ("ADMIN_USER_STATE_HISTORY", "status", "suspended"),
            ]:
                history = [
                    h
                    for h in tables[table]
                    if h["user_id"] == user_id
                    and datetime.fromisoformat(h["effective_at"]) < cutoff
                ]
                state = max(history, key=lambda h: (h["effective_at"], h["id"]))
                assert state[field].startswith(expected)
            with pytest.raises(psycopg2.errors.RaiseException, match="append-only"):
                with conn, conn.cursor() as cur:
                    cur.execute(
                        psycopg2.sql.SQL("DELETE FROM {}.user_state_history").format(
                            psycopg2.sql.Identifier(schema)
                        )
                    )
        finally:
            with conn, conn.cursor() as cur:
                cur.execute(
                    psycopg2.sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        psycopg2.sql.Identifier(schema)
                    )
                )
