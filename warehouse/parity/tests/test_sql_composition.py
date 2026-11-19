import sqlite3
from unittest.mock import Mock

import pytest

from warehouse.sql import compose, identifier, stage
from parity.commands import fetch


@pytest.mark.parametrize('dialect,expected', [
    ('snowflake', '"SCHEMA"."TABLE"'),
    ('postgres', '"schema"."table"'),
    ('sqlite', '"schema"."table"'),
])
def test_identifier_quoting_preserves_unquoted_dialect_case(dialect, expected):
    assert identifier('Schema.Table', dialect=dialect).as_string() == expected
    assert identifier('Mixed', dialect=dialect, preserve_case=True).as_string() == '"Mixed"'


@pytest.mark.parametrize('value', ['', None, 'a..b', '.table', 'table.', 'a b',
                                  'a; DROP TABLE x', 'a"b', 'a--comment', 'a/*b*/',
                                  'a\x00b', '１table', 'table\n'])
def test_invalid_identifiers_raise(value):
    with pytest.raises(ValueError, match='Invalid identifier'):
        identifier(value)


def test_unknown_dialect_and_qualified_column_raise():
    with pytest.raises(ValueError, match='Unsupported SQL dialect'):
        identifier('table', dialect='unknown')
    with pytest.raises(ValueError, match='Invalid identifier'):
        identifier('schema.column', qualified=False)


def test_composition_rejects_raw_interpolation():
    with pytest.raises(TypeError):
        compose('SELECT * FROM {}', 'table; DROP TABLE other')


@pytest.mark.parametrize('rows', [[], [("x'); DROP TABLE records; --",), ('normal',)]])
def test_values_remain_bound_and_empty_results_are_unchanged(rows):
    table = identifier('records', dialect='sqlite')
    with sqlite3.connect(':memory:') as db:
        db.execute(compose('CREATE TABLE {} (value TEXT)', table))
        db.executemany(compose('INSERT INTO {} VALUES (?)', table), rows)
        assert db.execute(compose('SELECT value FROM {} ORDER BY value', table)).fetchall() == sorted(rows)
        assert db.execute(compose('SELECT count(*) FROM {}', table)).fetchone() == (len(rows),)


def test_fetch_rejects_identifier_before_dispatch():
    cursor = Mock()
    with pytest.raises(ValueError, match='Invalid identifier'):
        fetch(cursor, 'PC_BEFORE.TABLE; DROP DATABASE x')
    cursor.execute.assert_not_called()


def test_stage_quotes_object_and_preserves_validated_path():
    assert stage('@landing.stage/seed/billing/20261109/').as_string() == '@"LANDING"."STAGE"/seed/billing/20261109/'
    for value in ['@landing.stage/a\'b/', '@landing.stage/../', '@bad;drop/path/']:
        with pytest.raises(ValueError):
            stage(value)
