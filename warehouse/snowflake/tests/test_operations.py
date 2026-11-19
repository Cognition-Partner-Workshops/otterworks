
import sys as _run_sys
from pathlib import Path as _RunPath
_run_sys.path.insert(0, str(_RunPath(__file__).resolve().parents[3]))
from warehouse.run_config import render as _run_render

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import re

import pytest
from snowflake.connector.errors import ProgrammingError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ledger
import teardown
spec = importlib.util.spec_from_file_location("roles_plan", ROOT / "roles/dry_run.py")
roles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roles)
HOUR = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


class Cursor:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.description = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        self.description = [(column,) for column in response[0]]
        self.rows = response[1]
        return self

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0]


def query(qid="q1", execution=100, **kw):
    return dict(query_id=qid, start_time=HOUR, hour=HOUR,
                warehouse_name=_run_render("__RUN_DATABASE___LOAD_WH"), workload="load", phase="copy",
                executed_by="devin", built_with="other", execution_time=execution,
                credits_used_cloud_services=0.1, hour_execution=400, **kw)


def meter(credits=2):
    return dict(warehouse_name=_run_render("__RUN_DATABASE___LOAD_WH"), hour=HOUR,
                end_time=HOUR + timedelta(hours=1), credits_used_compute=credits)


def test_ledger_allocation_and_dimensions():
    q1 = query()
    q2 = query("q2", 200)
    q2.update(executed_by="other", built_with="devin")
    result = ledger.summarize([q1, q2], [meter()], [], HOUR)
    assert result["groups"]["total"][0]["credits"] == 1.7
    executed = {r["executed_by"]: r["credits"] for r in result["groups"]["executed_by"]}
    built = {r["built_with"]: r["credits"] for r in result["groups"]["built_with"]}
    assert executed == {"devin": 0.6, "other": 1.1}
    assert built == {"devin": 1.1, "other": 0.6}


def test_ledger_pending_zero_and_empty():
    q = query()
    assert ledger.summarize([q], [], [], HOUR)["groups"]["total"][0]["credits"] == "pending"
    q.update(execution_time=0, credits_used_cloud_services=0)
    assert ledger.summarize([q], [meter(0)], [], HOUR)["groups"]["total"][0]["credits"] == 0
    newer = query("new")
    newer["start_time"] = HOUR + timedelta(minutes=10)
    result = ledger.summarize([q], [meter()], [newer], HOUR)
    assert result["groups"]["total"][0]["credits"] == "pending"
    assert result["recent_not_in_account_usage"] == 1
    stale = ledger.summarize([q], [meter()], [q], HOUR - timedelta(seconds=1))
    assert stale["groups"]["total"][0]["credits"] == "pending"
    assert ledger.summarize([], [], [], None)["groups"]["total"] == []


def test_ledger_cursor_and_token_filter():
    columns = list(query())
    cur = Cursor([
        (columns, [tuple(query().values())]),
        (list(meter()), [tuple(meter().values())]),
        (["QUERY_MAX_START"], [(HOUR,)]),
        (columns, []),
    ])
    report = ledger.summarize(*ledger.read_usage(cur, _run_render("__RUN_TOKEN__"), 14))
    assert report["groups"]["total"][0]["credits"] == 0.6
    for index in (0, 3):
        sql, params = cur.calls[index]
        assert "ILIKE %s" in sql and ":run_token::VARCHAR = %s" in sql
        assert ":run::VARCHAR = %s" in sql
        assert params[-3:] == (_run_render("%__RUN_TOKEN__%"), _run_render("__RUN_TOKEN__"), _run_render("__RUN_TOKEN__"))
    assert "SUM(EXECUTION_TIME)" in cur.calls[0][0]


def test_roles_plan_and_guards():
    plan = roles.validate(roles.statements())
    assert len(plan) > 50
    for path, line, sql in plan:
        assert _run_render((ROOT / "roles" / path).read_text()).splitlines()[line - 1] == sql
    for statement in (
        _run_render("GRANT CREATE ROLE ON ACCOUNT TO ROLE __RUN_DATABASE___OPS;"),
        _run_render("GRANT USAGE ON WAREHOUSE OTHER_WH TO ROLE __RUN_DATABASE___LOADER;"),
        _run_render("GRANT USAGE ON SCHEMA __RUN_DATABASE__.MISSING TO ROLE __RUN_DATABASE___OPS;"),
        _run_render("GRANT USAGE ON DATABASE __RUN_DATABASE__ TO ROLE OTHER;"),
        _run_render("DROP ROLE __RUN_DATABASE___OPS;"),
        _run_render("CREATE ROLE IF NOT EXISTS __RUN_DATABASE___OPS;"),
    ):
        with pytest.raises(ValueError):
            roles.validate([("bad.sql", 1, statement)])
    cur = Cursor([
        (["CURRENT_ROLE()"], [(_run_render("__RUN_DATABASE___ROLE"),)]),
        (["privilege", "granted_on", "name"], [("CREATE DATABASE", "ACCOUNT", "account")]),
    ])
    assert not roles.has_create_role(cur)
    assert all(not sql.startswith(("CREATE ", "GRANT ")) for sql, _ in cur.calls)
    cur = Cursor([
        (["CURRENT_ROLE()"], [(_run_render("__RUN_DATABASE___ROLE"),)]),
        (["privilege", "granted_on", "name"], [("USAGE", "ROLE", "PARENT")]),
        (["privilege", "granted_on", "name"], [("CREATE ROLE", "ACCOUNT", "account")]),
    ])
    assert roles.has_create_role(cur)


def test_analyst_dry_run_is_read_only_and_curated():
    plan = roles.validate(roles.statements())
    grants = [sql for _, _, sql in plan
              if sql.startswith("GRANT ") and sql.endswith(_run_render(" TO ROLE __RUN_DATABASE___ANALYST;"))]
    assert grants
    for sql in grants:
        privileges = re.match(r"GRANT (.+?) ON ", sql).group(1)
        assert not re.search(r"\b(ALL|INSERT|UPDATE|DELETE|TRUNCATE|OWNERSHIP|CREATE|MANAGE)\b", privileges)
        assert not re.search(r"RAW_|LANDING|SCHEMACHANGE", sql)
    expected = {
        _run_render("GRANT USAGE ON DATABASE __RUN_DATABASE__ TO ROLE __RUN_DATABASE___ANALYST;"),
        _run_render("GRANT USAGE ON WAREHOUSE __RUN_DATABASE___TRANSFORM_WH TO ROLE __RUN_DATABASE___ANALYST;"),
    }
    for schema in ("MART", "MART_SPARK", "COMPAT"):
        expected.add(_run_render(f"GRANT USAGE ON SCHEMA __RUN_DATABASE__.{schema} TO ROLE __RUN_DATABASE___ANALYST;"))
        for scope in ("ALL", "FUTURE"):
            for kind in ("TABLES", "VIEWS"):
                expected.add(_run_render(f"GRANT SELECT ON {scope} {kind} IN SCHEMA __RUN_DATABASE__.{schema} TO ROLE __RUN_DATABASE___ANALYST;"))
    assert set(grants) == expected
    assert len(grants) == len(expected)
    assert roles.validate([]) == []


@pytest.mark.parametrize("privilege,scope", [
    ("ALL", _run_render("DATABASE __RUN_DATABASE__")),
    ("ALL PRIVILEGES", _run_render("DATABASE __RUN_DATABASE__")),
    ("INSERT", _run_render("FUTURE TABLES IN SCHEMA __RUN_DATABASE__.CORE_BILLING")),
    ("UPDATE", _run_render("FUTURE TABLES IN SCHEMA __RUN_DATABASE__.CORE_BILLING")),
    ("DELETE", _run_render("FUTURE TABLES IN SCHEMA __RUN_DATABASE__.CORE_BILLING")),
    ("TRUNCATE", _run_render("FUTURE TABLES IN SCHEMA __RUN_DATABASE__.CORE_BILLING")),
    ("OWNERSHIP", _run_render("FUTURE TABLES IN SCHEMA __RUN_DATABASE__.CORE_BILLING")),
    ("CREATE TABLE", _run_render("SCHEMA __RUN_DATABASE__.CORE_BILLING")),
    ("MANAGE GRANTS", "ACCOUNT"),
])
def test_analyst_dry_run_rejects_write_privileges(privilege, scope):
    sql = _run_render(f"GRANT {privilege} ON {scope} TO ROLE __RUN_DATABASE___ANALYST;")
    with pytest.raises(ValueError):
        roles.validate([("bad.sql", 1, sql)])


@pytest.mark.parametrize("schema", [
    "RAW_BILLING", "RAW_DOCUMENTS", "RAW_USERS", "RAW_AUDIT", "LANDING", "SCHEMACHANGE",
    "CORE_BILLING", "CORE_DOCUMENTS", "CORE_USERS", "CORE_AUDIT", "SPARK_RAW_USERS",
])
@pytest.mark.parametrize("privilege,kind", [("USAGE", "SCHEMA"), ("SELECT", "FUTURE TABLES IN SCHEMA")])
def test_analyst_dry_run_rejects_non_curated_schemas(schema, privilege, kind):
    sql = _run_render(f"GRANT {privilege} ON {kind} __RUN_DATABASE__.{schema} TO ROLE __RUN_DATABASE___ANALYST;")
    with pytest.raises(ValueError, match="Analyst grants must be read-only and curated"):
        roles.validate([("bad.sql", 1, sql)])


@pytest.mark.parametrize("sql", [
    _run_render("GRANT USAGE ON FUTURE SCHEMAS IN DATABASE __RUN_DATABASE__ TO ROLE __RUN_DATABASE___ANALYST;"),
    _run_render("GRANT USAGE ON ALL PROCEDURES IN SCHEMA __RUN_DATABASE__.CORE_BILLING TO ROLE __RUN_DATABASE___ANALYST;"),
    _run_render("GRANT ROLE __RUN_DATABASE___LOADER TO ROLE __RUN_DATABASE___ANALYST;"),
])
def test_analyst_dry_run_rejects_broad_scopes_and_inheritance(sql):
    with pytest.raises(ValueError):
        roles.validate([("bad.sql", 1, sql)])


def test_role_plan_removes_existing_and_future_analyst_privileges():
    plan = roles.statements()
    reset = [sql for _, _, sql in plan if sql.startswith("REVOKE ")]
    assert reset
    for scope in (_run_render("DATABASE __RUN_DATABASE__"), _run_render("ALL SCHEMAS IN DATABASE __RUN_DATABASE__"),
                  _run_render("FUTURE SCHEMAS IN DATABASE __RUN_DATABASE__"),
                  _run_render("ALL TABLES IN DATABASE __RUN_DATABASE__"), _run_render("ALL VIEWS IN DATABASE __RUN_DATABASE__"),
                  _run_render("FUTURE TABLES IN DATABASE __RUN_DATABASE__"), _run_render("FUTURE VIEWS IN DATABASE __RUN_DATABASE__")):
        assert _run_render(f"REVOKE ALL PRIVILEGES ON {scope} FROM ROLE __RUN_DATABASE___ANALYST;") in reset
    schemas = set()
    for path in (ROOT / "migrations").glob("V*.sql"):
        schemas.update(re.findall(r"CREATE SCHEMA IF NOT EXISTS (\w+)", _run_render(path.read_text())))
    for schema in schemas:
        for kind in ("TABLES", "VIEWS"):
            assert (_run_render(f"REVOKE ALL PRIVILEGES ON FUTURE {kind} IN SCHEMA "
                    f"__RUN_DATABASE__.{schema} FROM ROLE __RUN_DATABASE___ANALYST;")) in reset
    assert all(sql.endswith(_run_render(" FROM ROLE __RUN_DATABASE___ANALYST;")) for sql in reset)
    schema_plan = [sql for path, _, sql in plan if path == "03_schema_grants.sql"]
    assert all(sql.startswith("REVOKE ") for sql in schema_plan[:len(reset)])


@pytest.mark.parametrize("sql", [
    _run_render("REVOKE ALL PRIVILEGES ON DATABASE OTHER FROM ROLE __RUN_DATABASE___ANALYST;"),
    _run_render("REVOKE ALL PRIVILEGES ON DATABASE __RUN_DATABASE__ FROM ROLE __RUN_DATABASE___TRANSFORMER;"),
    _run_render("REVOKE ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA __RUN_DATABASE__.MISSING FROM ROLE __RUN_DATABASE___ANALYST;"),
    _run_render("REVOKE ALL PRIVILEGES ON FUTURE TABLES IN DATABASE __RUN_DATABASE__.MART FROM ROLE __RUN_DATABASE___ANALYST;"),
    _run_render("REVOKE OWNERSHIP ON DATABASE __RUN_DATABASE__ FROM ROLE __RUN_DATABASE___ANALYST;"),
])
def test_role_plan_rejects_unscoped_resets(sql):
    with pytest.raises(ValueError):
        roles.validate([("bad.sql", 1, sql)])


def test_complexity_fragments_absent():
    assert not list((ROOT.parents[1] / "demos/app/complexity").glob("sfx-*.json"))


def test_make_uses_separate_snowflake_and_teradata_environments():
    env = os.environ.copy()
    for key in ('MAKEFLAGS', 'MFLAGS', 'MAKEOVERRIDES', 'SFX_TEST_PYTHON', 'SFX_VENV'):
        env.pop(key, None)
    for target, own, other in (
        ('sfx-snowflake-test', 'warehouse/snowflake/.venv', 'warehouse/.venv'),
        ('sfx-teradata-test', 'warehouse/.venv', 'warehouse/snowflake/.venv'),
    ):
        result = subprocess.run(['make', '-Bn', target, _run_render('NS=__BEFORE_NAMESPACE__')],
                                cwd=ROOT.parents[1], env=env, capture_output=True, text=True, check=True)
        assert f'-m venv {own}' in result.stdout
        assert f'{own}/bin/python -m pytest' in result.stdout
        assert other not in result.stdout


def test_role_apply_refuses_without_privilege(monkeypatch, capsys):
    cur = Cursor([
        (["CURRENT_ROLE()"], [(_run_render("__RUN_DATABASE___ROLE"),)]),
        (["privilege", "granted_on", "name"], []),
    ])

    class Context:
        def __init__(self, value):
            self.value = value

        def __enter__(self):
            return self.value

        def __exit__(self, *args):
            pass

        def cursor(self):
            return Context(cur)

    monkeypatch.setattr(roles, "connect", lambda *args: Context(Context(None)))
    monkeypatch.setattr(sys, "argv", ["dry_run.py", "--apply"])
    with pytest.raises(SystemExit) as result:
        roles.main()
    assert result.value.code == 1
    assert "apply skipped: role lacks CREATE ROLE" in capsys.readouterr().out
    assert all(not sql.startswith(("CREATE", "GRANT")) for sql, _ in cur.calls)


class InventoryCursor:
    def __init__(self, denied=False):
        self.calls = []
        self.denied = denied
        self.deleted = set()

    def execute(self, sql):
        self.calls.append(sql)
        if sql.startswith("DROP "):
            self.deleted.add(tuple(re.findall(r'"([^"]+)"', sql)))
        if sql.startswith(("DROP ", "ALTER ")):
            self.description = []
            self.rows = []
            return
        if sql == "SHOW USERS" and self.denied:
            raise ProgrammingError(msg="insufficient privileges", errno=3001)
        data = []
        if sql.startswith("SHOW DATABASES"):
            data = [(_run_render("__RUN_DATABASE__"), ""), (_run_render("__RUN_DATABASE___TEMP"), _run_render("__RUN_TOKEN__")),
                    ("OTHER", "unrelated")]
        elif sql.startswith("SHOW SCHEMAS"):
            data = [("INFORMATION_SCHEMA", ""), ("RAW_BILLING", _run_render("__RUN_TOKEN__ raw")),
                    ("KEEP", "unrelated")]
        elif sql.startswith("SHOW TASKS"):
            data = [("LOAD_TASK", _run_render("__RUN_TOKEN__ task"))]
        elif sql.startswith("SHOW STAGES"):
            data = [("LANDING_STAGE", _run_render("__RUN_TOKEN__ stage"))]
        elif sql == "SHOW WAREHOUSES":
            data = [(_run_render("__RUN_DATABASE___LOAD_WH"), ""), ("OTHER_WH", "")]
        elif sql == "SHOW ROLES":
            data = [(_run_render("__RUN_DATABASE___ROLE"), ""), (_run_render("__RUN_DATABASE___ANALYST"), _run_render("__RUN_TOKEN__ role"))]
        elif sql == "SHOW USERS":
            data = [(_run_render("__RUN_DATABASE___SVC"), "")]
        elif sql == "SHOW RESOURCE MONITORS":
            data = [(_run_render("__RUN_DATABASE___RM"), "")]
        self.description = [("name",), ("comment",)]
        scope = tuple(re.findall(r'"([^"]+)"', sql))
        if any(scope[:len(key)] == key for key in self.deleted):
            data = []
        self.rows = [row for row in data if (*scope, row[0]) not in self.deleted]

    def fetchall(self):
        return self.rows


def test_teardown_dry_run_and_scope(capsys):
    cur = InventoryCursor()
    assert teardown.cleanup(cur, _run_render("__RUN_TOKEN__"), dry_run=True) == 1
    assert all(sql.startswith("SHOW ") for sql in cur.calls)
    assert "Dry-run summary:" in capsys.readouterr().out
    objects, _ = teardown.discover(cur, _run_render("__RUN_TOKEN__"))
    commands = teardown.plan(objects)
    assert not any(_run_render('DROP DATABASE IF EXISTS "__RUN_DATABASE__"') in sql for sql in commands)
    assert not any('"OTHER' in sql for sql in commands)
    assert not any(sql.startswith("DROP SCHEMA") and '"KEEP"' in sql for sql in commands)
    first_drop = next(i for i, sql in enumerate(commands) if sql.startswith("DROP"))
    assert all(sql.startswith("ALTER") for sql in commands[:first_drop])
    assert any(_run_render('DROP DATABASE IF EXISTS "__RUN_DATABASE___TEMP"') in sql for sql in commands)
    assert any(_run_render('DROP ROLE IF EXISTS "__RUN_DATABASE___ANALYST"') in sql for sql in commands)


def test_teardown_real_and_include_provisioned():
    cur = InventoryCursor()
    assert teardown.cleanup(cur, _run_render("__RUN_TOKEN__")) == 0
    assert not any(sql.startswith(_run_render('DROP ROLE IF EXISTS "__RUN_DATABASE___ROLE"')) for sql in cur.calls)
    cur = InventoryCursor()
    assert teardown.cleanup(cur, _run_render("__RUN_TOKEN__"), include_provisioned=True) == 0
    for kind, name in teardown.PROVISIONED:
        if name in (_run_render("__RUN_DATABASE___ROLE"), _run_render("__RUN_DATABASE___SVC"), _run_render("__RUN_DATABASE__"),
                    _run_render("__RUN_DATABASE___LOAD_WH"), _run_render("__RUN_DATABASE___RM")):
            assert any(sql.startswith(f'DROP {kind} IF EXISTS "{name}"') for sql in cur.calls)


def test_teardown_privilege_and_suspend_only(capsys):
    cur = InventoryCursor(denied=True)
    assert teardown.cleanup(cur, _run_render("__RUN_TOKEN__"), dry_run=True) == 1
    assert "insufficient privilege" in capsys.readouterr().out
    cur = InventoryCursor()
    assert teardown.cleanup(cur, _run_render("__RUN_TOKEN__"), suspend_only=True) == 0
    assert not any(sql.startswith("DROP") for sql in cur.calls)
    assert teardown.tagged(_run_render("__RUN_DATABASE___EXTRA"), "", _run_render("__RUN_TOKEN__"))
    assert not teardown.tagged("OTHER", "", _run_render("__RUN_TOKEN__"))


def test_before_namespace_lifecycle():
    repo = ROOT.parents[1]
    for target in ("up", "run", "down"):
        result = subprocess.run(
            ["make", "sfx-snowflake-" + target, _run_render("NS=__BEFORE_NAMESPACE__")],
            cwd=repo, capture_output=True, text=True, check=True,
        )
        assert "not part of namespace" in result.stdout
        assert "python" not in result.stdout
