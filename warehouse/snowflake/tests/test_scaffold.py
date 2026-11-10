import csv
import importlib.util
import json
from pathlib import Path
import re
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sfx_conn import WORKLOADS, query_tag


def module(path):
    spec = importlib.util.spec_from_file_location("helper", ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_tag(monkeypatch):
    monkeypatch.setenv("SFX_COMMIT", "abc123")
    monkeypatch.setenv("SFX_RUN_ID", "test-run")
    monkeypatch.delenv("SFX_EXECUTED_BY", raising=False)
    monkeypatch.delenv("SFX_BUILT_WITH", raising=False)
    monkeypatch.delenv("SNOWFLAKE_RUN_TOKEN", raising=False)
    value = query_tag("load", "copy")
    assert json.loads(value) == dict(workload="load", phase="copy", commit="abc123",
        run_id="test-run", run_token="sfx-d1110", executed_by="manual", built_with="devin")
    assert " " not in value
    monkeypatch.setenv("SFX_EXECUTED_BY", "devin")
    assert json.loads(query_tag("ops", "deploy"))["executed_by"] == "devin"
    monkeypatch.delenv("SFX_RUN_ID")
    assert json.loads(query_tag("ops", "x"))["run_id"] == json.loads(query_tag("load", "y"))["run_id"]


def test_invalid_workload():
    with pytest.raises(ValueError):
        query_tag("", "x")


def test_mapping():
    assert WORKLOADS == {w: f"SFX_D1110_{w.upper()}_WH"
                        for w in ["load", "transform", "parity", "snowpark", "ops"]}


def test_migration_matches_spec():
    renderer = module("tools/render_raw.py")
    assert renderer.TARGET.read_text() == renderer.render()


def test_spec_and_fixture():
    spec = yaml.safe_load((ROOT / "landing_columns.yml").read_text())
    assert set(spec) == {"billing", "documents", "users", "audit"}
    for area, tables in spec.items():
        assert len(tables) == (12 if area == 'billing' else 10)
        for table, columns in tables.items():
            assert 5 <= len(columns) <= 10
            assert columns[table + "_ID"] == "BIGINT"
            assert all(re.fullmatch(r"BIGINT|INTEGER|NUMBER\(\d+,\d+\)|VARCHAR\(\d+\)|CHAR\(\d+\)|DATE|TIMESTAMP_NTZ", t) for t in columns.values())
            with (ROOT / "fixtures/landing" / area / table / "20261101.psv").open() as stream:
                reader = csv.DictReader(stream, delimiter="|")
                assert reader.fieldnames == list(columns)
                rows = list(reader)
            assert 20 <= len(rows) <= 50
            for i, row in enumerate(rows, 1):
                assert int(row[table + '_ID']) == i


def test_fixture_determinism_empty_error(tmp_path):
    fixture = module("fixtures/make_fixture.py")
    fixture.generate(20, 1110, tmp_path)
    for path in (ROOT / "fixtures/landing").rglob("*.psv"):
        assert path.read_bytes() == (tmp_path / path.relative_to(ROOT / "fixtures/landing")).read_bytes()
    fixture.generate(0, 1110, tmp_path)
    assert all(len(p.read_text().splitlines()) == 1 for p in tmp_path.rglob("*.psv"))
    with pytest.raises(ValueError):
        fixture.generate(-1, output=tmp_path)


def test_create_comments():
    for path in (ROOT / "migrations").glob("V*.sql"):
        statements = re.split(r"(?im)(?=^CREATE )", path.read_text())
        for statement in statements:
            if statement.startswith("CREATE "):
                assert re.search(r"COMMENT\s*=\s*'sfx-d1110[^']*'", statement)
    tasks = (ROOT / "migrations/V003__loaders_and_tasks.sql").read_text()
    assert "RESUME" not in tasks
    assert tasks.count('phase":"task"') == 4


def test_suspend_already_suspended(monkeypatch, capsys):
    import sfx_conn
    from snowflake.connector.errors import ProgrammingError

    class Cursor:
        description = [("state",)]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            if query.startswith("ALTER"):
                raise ProgrammingError(msg="Invalid state", errno=90064)

        def fetchall(self):
            return [("SUSPENDED",)]

    class Connection(Cursor):
        def cursor(self):
            return Cursor()

    monkeypatch.setattr(sfx_conn, "connect", lambda *args: Connection())
    sfx_conn.suspend_all()
    assert capsys.readouterr().out.count("already suspended") == 5

    monkeypatch.setattr(Cursor, "fetchall", lambda self: [("STARTED",)])
    with pytest.raises(ProgrammingError):
        sfx_conn.suspend_all()
