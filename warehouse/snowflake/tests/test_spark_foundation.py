import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock

from jinja2 import Environment
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sfx_conn
import spark_landing
import run_spark_job


def test_spark_tag(monkeypatch):
    monkeypatch.setenv("SFX_COMMIT", "test")
    original = json.loads(sfx_conn.query_tag("transform", "dbt"))
    tagged = json.loads(sfx_conn.query_tag("transform", "dbt", job="example"))
    assert tagged == {**original, "run": "sfx-d1110", "act": "spark", "job": "example"}
    monkeypatch.setenv("SFX_SPARK_JOB", "env_job")
    assert json.loads(sfx_conn.query_tag("ops", "measure"))["job"] == "env_job"
    with pytest.raises(ValueError):
        sfx_conn.query_tag("ops", "x", job="../bad")


def test_dbt_macro_preserves_extra_keys():
    class Returned(Exception):
        pass
    def return_value(value):
        raise Returned(value)
    tag = {"workload": "ops", "phase": "old", "run_token": "sfx-d1110", "run": "sfx-d1110", "act": "spark", "job": "_smoke", "extra": "retained"}
    env = Environment(extensions=["jinja2.ext.do"])
    module = env.from_string((ROOT.parent / "dbt/macros/query_tag.sql").read_text()).make_module({
        "fromjson": json.loads, "tojson": json.dumps, "env_var": lambda key: json.dumps(tag),
        "var": lambda key, default=None: {"phase": "dbt", "run_token": "sfx-d1110"}.get(key, default),
        "return": return_value,
    })
    with pytest.raises(Returned) as result:
        module.sfx_query_tag()
    assert json.loads(result.value.args[0]) == {**tag, "workload": "transform", "phase": "dbt"}


def test_sources_match_spark():
    sources = yaml.safe_load((ROOT.parent / "dbt/models/staging/spark/sources.yml").read_text())["sources"]
    assert {source["name"]: {table["name"]: [column["name"] for column in table["columns"]]
                            for table in source["tables"]} for source in sources} == {
        "spark_" + area: {table: [name for name, _ in spark_landing.SCHEMAS[table]] for table in tables}
        for area, tables in spark_landing.TABLES.items()
    }


def test_landing_inspection(tmp_path):
    directory = tmp_path / "billing/PLAN_CATALOG"
    directory.mkdir(parents=True)
    path = directory / "20261109.psv"
    path.write_text("PLAN_ID|PLAN_NAME|MONTHLY_PRICE\n1|basic|10.00\n")
    assert spark_landing.inspect_files(tmp_path, "billing", "PLAN_CATALOG")[1] == 1
    path.write_text("PLAN_ID|PLAN_NAME|MONTHLY_PRICE\n")
    assert spark_landing.inspect_files(tmp_path, "billing", "PLAN_CATALOG")[1] == 0
    path.write_text("wrong\n")
    with pytest.raises(ValueError, match="Header mismatch"):
        spark_landing.inspect_files(tmp_path, "billing", "PLAN_CATALOG")
    with pytest.raises(FileNotFoundError):
        spark_landing.inspect_files(tmp_path, "billing", "MISSING")


@pytest.mark.parametrize("count", [0, 1])
def test_landing_refresh(tmp_path, monkeypatch, count):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(name,) for name, _ in spark_landing.SCHEMAS["PLAN_CATALOG"]]
    cursor.fetchone.return_value = (count,)
    monkeypatch.setattr(spark_landing, "connect", lambda *args, **kwargs: connection)
    monkeypatch.setattr(spark_landing, "TABLES", {"billing": {"PLAN_CATALOG": ""}})
    monkeypatch.setattr(spark_landing, "inspect_files", lambda *args: ([], count, "digest"))
    assert spark_landing.load(tmp_path) == [("SPARK_RAW_BILLING.PLAN_CATALOG", count, count)]
    sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("INSERT OVERWRITE INTO SPARK_RAW_BILLING.PLAN_CATALOG" in statement for statement in sql)
    assert "DROP TABLE IF EXISTS" in sql[-1]


def test_landing_load_error(tmp_path, monkeypatch):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(name,) for name, _ in spark_landing.SCHEMAS["PLAN_CATALOG"]]
    def execute(sql):
        if sql.startswith("COPY INTO"):
            raise RuntimeError("copy failed")
    cursor.execute.side_effect = execute
    monkeypatch.setattr(spark_landing, "connect", lambda *args, **kwargs: connection)
    monkeypatch.setattr(spark_landing, "TABLES", {"billing": {"PLAN_CATALOG": ""}})
    monkeypatch.setattr(spark_landing, "inspect_files", lambda *args: ([], 1, "digest"))
    with pytest.raises(RuntimeError, match="copy failed"):
        spark_landing.load(tmp_path)
    sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any("INSERT OVERWRITE" in statement for statement in sql)
    assert "DROP TABLE IF EXISTS" in sql[-1]


@pytest.mark.parametrize("count", [0, 1])
def test_landing_subset(tmp_path, monkeypatch, count):
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [(name,) for name, _ in spark_landing.SCHEMAS["PLAN_CATALOG"]]
    cursor.fetchone.return_value = (count,)
    monkeypatch.setattr(spark_landing, "connect", lambda *args, **kwargs: connection)
    inspect = MagicMock(return_value=([], count, "digest"))
    monkeypatch.setattr(spark_landing, "inspect_files", inspect)
    assert spark_landing.load(tmp_path, ["billing.PLAN_CATALOG"]) == [
        ("SPARK_RAW_BILLING.PLAN_CATALOG", count, count)]
    inspect.assert_called_once_with(tmp_path, "billing", "PLAN_CATALOG")


@pytest.mark.parametrize("tables", [[], ["billing.UNKNOWN"], ["unknown.PLAN_CATALOG"], "billing.PLAN_CATALOG"])
def test_landing_invalid_subset(tmp_path, monkeypatch, tables):
    connect = MagicMock()
    monkeypatch.setattr(spark_landing, "connect", connect)
    with pytest.raises(ValueError):
        spark_landing.load(tmp_path, tables)
    connect.assert_not_called()


def test_registry_dispatch(tmp_path, monkeypatch):
    registry = tmp_path / "etl/spark/jobs/registry"
    registry.mkdir(parents=True)
    path = registry / "example.yaml"
    path.write_text(json.dumps({"status": "snowflake", "command": "echo example"}))
    monkeypatch.setattr(run_spark_job, "ROOT", tmp_path)
    execute = MagicMock()
    monkeypatch.setattr(run_spark_job.subprocess, "run", execute)
    run_spark_job.run("example")
    assert execute.call_args.kwargs["env"]["SFX_SPARK_JOB"] == "example"
    for entry in ({"status": "legacy"}, {"status": "retired"}, {"status": "snowflake", "command": ""}):
        path.write_text(json.dumps(entry))
        with pytest.raises(ValueError):
            run_spark_job.run("example")
    with pytest.raises(ValueError):
        run_spark_job.run("../bad")


def test_snowpark_runner(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("spark_runner", ROOT.parent / "snowpark/run_job.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    (tmp_path / "example.py").write_text("def run(session):\n    return 42\n")
    connect = MagicMock()
    monkeypatch.setattr(runner, "connect", connect)
    session = MagicMock()
    monkeypatch.setattr("snowflake.snowpark.Session.builder", session)
    assert runner.run("example") == 42
    assert connect.call_args.kwargs["job"] == "example"
    active = session.configs.return_value.create.return_value.__enter__.return_value
    assert json.loads(active.query_tag)["job"] == "example"
    assert json.loads(active.query_tag)["act"] == "spark"
    assert any('SET TAG' in call.args[0] and "= 'sfx-d1110'" in call.args[0]
               for call in active.sql.call_args_list)
    with pytest.raises(FileNotFoundError):
        runner.run("missing")
    with pytest.raises(ValueError):
        runner.run("")
