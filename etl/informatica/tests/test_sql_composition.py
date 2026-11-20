import sqlite3

import pytest

from runner.db import bind_sql, compose, identifier, qi
from runner.params import expand


@pytest.mark.parametrize('name', ['', 'a.b', 'a;DROP TABLE x', 'a"b', 'a--x', 'a b', '1table'])
def test_invalid_identifiers(name):
    with pytest.raises(ValueError):
        qi(name)


def test_quoted_physical_identifiers():
    assert compose('SELECT * FROM {}', identifier('schema', 'Mixed_Case')) == 'SELECT * FROM "schema"."Mixed_Case"'
    with pytest.raises(TypeError):
        compose('SELECT * FROM {}', 'unvalidated')


@pytest.mark.parametrize('value', ['', 'ordinary', "x'); DROP TABLE records; --"])
def test_expanded_values_are_bound(value):
    query, values = bind_sql("INSERT INTO records VALUES ('prefix%$$Value')", lambda text: expand(text, {'$$Value': value}, {}))
    assert values == ('prefix%' + value,)
    assert query == 'INSERT INTO records VALUES (%s)'
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE records (value TEXT)')
        db.execute(query.replace('%s', '?'), values)
        assert db.execute('SELECT value FROM records').fetchall() == [('prefix%' + value,)]


def test_numeric_and_recursive_parameters_and_literal_percents():
    query, values = bind_sql("SELECT $$Days, '$$Label' WHERE 'abc' LIKE 'a%'", lambda text: expand(text, {'$$Days': '90', '$$Label': '$PMValue'}, {'$PMValue': "x' OR 1=1 --"}))
    assert query == "SELECT %s, %s WHERE 'abc' LIKE 'a%%'"
    assert values == (90, "x' OR 1=1 --")
    assert bind_sql("SELECT 'a%'", lambda text: text) == ("SELECT 'a%'", ())
    with pytest.raises(ValueError):
        bind_sql('SELECT \x00', lambda text: text)
