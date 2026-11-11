"""PostgreSQL seed and validation identifiers must be composed, never interpolated."""

import importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock

import psycopg2.extensions
from psycopg2 import sql
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


helpers = load("c2_helpers", "testdata/generated/seed/helpers.py")
validate = load("c2_validate", "testdata/harness/validate.py")


@pytest.fixture
def cursor(monkeypatch):
    monkeypatch.setattr(psycopg2.extensions, "quote_ident",
                        lambda value, context: '"' + value.replace('"', '""') + '"')
    cur = Mock()
    cur.fetchone.return_value = (0,)
    cur.fetchall.return_value = []
    return cur


@pytest.mark.parametrize("identifier", ["users", 'users"; DROP TABLE users; --', ""])
def test_validation_identifiers_are_quoted(cursor, identifier):
    validate.check_row_count(cursor, identifier, identifier, 0)
    query = cursor.execute.call_args.args[0]
    assert isinstance(query, sql.Composable)
    quoted = '"' + identifier.replace('"', '""') + '"'
    assert query.as_string(None) == f"SELECT count(*) FROM {quoted}.{quoted}"


def test_all_validation_queries_compose_identifiers(cursor):
    validate.check_not_null(cursor, "s", "t", ["c"])
    validate.check_unique(cursor, "s", "t", ["c"])
    validate.check_fk_integrity(cursor, "s", "t", "c", "p", "id")
    validate.check_temporal_consistency(cursor, "s", "t", "ts", "p", "ts", "id")
    validate.check_enum_values(cursor, "s", "t", "c", [])
    validate.check_quota_not_exceeded(cursor, "s")
    assert all(isinstance(call.args[0], sql.Composable) for call in cursor.execute.call_args_list)


def test_seed_search_path_and_insert(cursor, monkeypatch):
    helpers.set_search_path(cursor, 'x"; SELECT 1; --')
    assert '""' in cursor.execute.call_args.args[0].as_string(None)
    execute = Mock()
    monkeypatch.setattr(helpers, "execute_values", execute)
    assert helpers.bulk_insert(cursor, 't"', ['c"'], [("'quoted",)]) == 1
    query = execute.call_args.args[1].as_string(None)
    assert query == 'INSERT INTO "t""" ("c""") VALUES %s ON CONFLICT DO NOTHING'
    assert execute.call_args.args[2] == [("'quoted",)]
    assert helpers.bulk_insert(cursor, "t", ["c"], []) == 0
    with pytest.raises(ValueError, match="Unsupported conflict clause"):
        helpers.bulk_insert(cursor, "t", ["c"], [(1,)], on_conflict="DO NOTHING; DROP TABLE t")
