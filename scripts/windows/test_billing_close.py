import importlib.util
from pathlib import Path
from types import SimpleNamespace

import json

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLOSE = load('billing-close')
LOCAL = load('duckdb-close')


def test_migrated_needs_no_snowflake_credentials_and_filters_inherited_ones(monkeypatch):
    monkeypatch.setenv('SNOWFLAKE_ACCOUNT', 'must-not-reach-child')
    monkeypatch.setenv('SNOWFLAKE_PRIVATE_KEY', 'must-not-reach-child')
    calls = []
    monkeypatch.setattr(CLOSE, 'run', lambda *a, **kw: calls.append((a, kw)))
    CLOSE.migrated(SimpleNamespace(rows=20000, business_date='20261109'))
    args, kwargs = calls[0]
    assert args[1].name == 'duckdb-close.py'
    assert args[2:6] == ('--business-date', '20261109', '--rows', 20000)
    assert not any(k.startswith('SNOWFLAKE_') for k in kwargs['env'])


def test_local_scope_does_not_inherit_snowflake_token(monkeypatch, tmp_path):
    monkeypatch.delenv('RUN_TOKEN', raising=False)
    monkeypatch.setenv('SNOWFLAKE_RUN_TOKEN', 'sfx-unrelated')
    monkeypatch.setattr(CLOSE, 'RUNS', tmp_path)
    assert CLOSE.configure().token == 'sfx1119'


@pytest.mark.parametrize('rows', [[], [(1, 'a')], [(1, 'a'), (1, 'a')]])
def test_local_comparison_preserves_empty_and_duplicate_rows(rows):
    with LOCAL.duckdb.connect() as before, LOCAL.duckdb.connect() as after:
        for con in (before, after):
            con.execute('CREATE SCHEMA billing')
            LOCAL.rows_table(con, 'billing.test', ['id', 'value'], rows)
        result = LOCAL.result(before, after, 'test', 'billing.test', 'billing.test')
        assert result['passed'] and result['hash_match']
        assert result['before_count'] == result['after_count'] == len(rows)
        if rows:
            after.execute('DELETE FROM billing.test')
            assert not LOCAL.result(before, after, 'test', 'billing.test', 'billing.test')['passed']


def test_local_comparison_reports_schema_error_without_inventing_hash():
    with LOCAL.duckdb.connect() as before, LOCAL.duckdb.connect() as after:
        for con, column in ((before, 'id'), (after, 'different')):
            con.execute('CREATE SCHEMA billing')
            LOCAL.rows_table(con, 'billing.test', [column], [(1,)])
        result = LOCAL.result(before, after, 'test', 'billing.test', 'billing.test')
        assert result['before_count'] == result['after_count'] == 1
        assert not result['passed'] and result['hash_match'] is None
        assert 'column names/order differ' in result['error']


def test_failed_statement_does_not_prevent_later_statements():
    with LOCAL.duckdb.connect() as con:
        errors = []
        LOCAL.execute(con, 'SELECT * FROM missing; CREATE TABLE good AS SELECT 1 AS id;',
                      LOCAL.dt.date(2026, 11, 9), errors, 'test')
        assert len(errors) == 1
        assert con.execute('SELECT * FROM good').fetchall() == [(1,)]


def test_arrow_copy_preserves_types_nulls_padding_and_duplicates():
    decimal = LOCAL.Decimal('12345.6700')
    day = LOCAL.dt.date(2026, 11, 9)
    rows = [(9, decimal, 'café  ', day, None), (9, decimal, 'café  ', day, None)]
    with LOCAL.duckdb.connect() as con:
        con.execute('CREATE SCHEMA billing')
        con.execute('CREATE TABLE billing.test (id BIGINT, amount DECIMAL(18,4), padded VARCHAR, day DATE, empty VARCHAR)')
        LOCAL.copy_rows(con, 'billing.test', rows)
        LOCAL.copy_rows(con, 'billing.test', [])
        assert con.execute('SELECT * FROM billing.test').fetchall() == rows
        with pytest.raises(LOCAL.duckdb.Error):
            LOCAL.copy_rows(con, 'billing.test', [('bad id', decimal, 'x', day, None)])
        LOCAL.copy_rows(con, 'billing.test', rows[:1])
        assert con.execute('SELECT COUNT(*) FROM billing.test').fetchone()[0] == 3


@pytest.mark.parametrize('text,expected', [
    ('', []),
    ('7|| raw |ignored\n\n8|USD\n', [('7', None, ' raw ', 1), ('8', 'USD', None, 3)]),
])
def test_stage_preserves_raw_fields_and_file_row_numbers(tmp_path, text, expected):
    path = tmp_path / 'source.psv'
    path.write_text(text)
    with LOCAL.duckdb.connect() as con:
        con.execute('CREATE SCHEMA PC_STAGE')
        LOCAL.stage(con, 'TEST', path, 3)
        assert con.execute('SELECT * FROM PC_STAGE.TEST ORDER BY "METADATA$FILE_ROW_NUMBER"').fetchall() == expected


def test_stage_reports_missing_input(tmp_path):
    with LOCAL.duckdb.connect() as con:
        con.execute('CREATE SCHEMA PC_STAGE')
        with pytest.raises(FileNotFoundError):
            LOCAL.stage(con, 'TEST', tmp_path / 'missing.psv', 3)


@pytest.mark.parametrize('value,pattern', [('20261109', 'YYYYMMDD'), ('09/11/2026', 'DD/MM/YYYY')])
def test_formatted_date_translation(value, pattern):
    with LOCAL.duckdb.connect() as con:
        query = f"SELECT TO_DATE('{value}', '{pattern}')"
        statement = next(LOCAL.translated(query, LOCAL.dt.date(2026, 11, 9)))
        assert con.execute(statement).fetchone()[0] == LOCAL.dt.date(2026, 11, 9)


def test_translation_changes_dialect_not_period_key_semantics():
    sql = "UPDATE __RUN_DATABASE__.BILLING.INVOICE_HDR SET PERIOD_KEY=DATEDIFF(day, DATE '1900-01-01', PERIOD_START_DT)+19000000"
    translated = next(LOCAL.translated(sql, LOCAL.dt.date(2026, 11, 9)))
    assert '__RUN_DATABASE__' not in translated
    with LOCAL.duckdb.connect() as con:
        con.execute('CREATE SCHEMA billing')
        con.execute("CREATE TABLE billing.invoice_hdr AS SELECT DATE '2026-11-01' AS period_start_dt, 0 AS period_key")
        con.execute(translated)
        assert con.execute('SELECT period_key FROM billing.invoice_hdr').fetchone()[0] == 19046325


def test_main_runs_pc_even_when_bteq_is_red(monkeypatch, tmp_path, capsys):
    (tmp_path / 'legacy-snapshot.json').write_text(json.dumps({'rows': 20, 'business_date': '20261109'}))
    row = dict(name='test', before_count=1, after_count=0, hash_match=False, passed=False)
    monkeypatch.setattr(LOCAL, 'bteq', lambda *a: dict(results=[row], execution_errors=[], close_summary={}))
    monkeypatch.setattr(LOCAL, 'pc', lambda *a: dict(results=[dict(row, name='pc-test')], execution_errors=[]))
    monkeypatch.setenv('TD_PG_PORT', '5432')
    monkeypatch.setattr(LOCAL.sys, 'argv', ['duckdb-close.py', '--rows', '20', '--output', str(tmp_path)])
    LOCAL.main()
    output = capsys.readouterr().out
    assert 'BTEQ test | 1 | 0 | hash_match=False | RED' in output
    assert 'PC pc-test | 1 | 0 | hash_match=False | RED' in output
