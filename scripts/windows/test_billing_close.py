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


def pc_mapping(**changes):
    return dict(dict(mapping='test', target_table='TEST', after_table='PC_BILLING.TEST',
                     key_columns=['ID'], exclude_columns={}), **changes)


@pytest.mark.parametrize('rows', [[], [(1, 'x   ', LOCAL.Decimal('12.00'))],
                                  [(1, 'x   ', LOCAL.Decimal('12.00'))] * 2])
def test_pc_uses_harness_named_columns_types_and_keys(rows):
    with LOCAL.duckdb.connect() as before, LOCAL.duckdb.connect() as after:
        before.execute('CREATE SCHEMA SFX_BILLING')
        after.execute('CREATE SCHEMA PC_BILLING')
        before.execute('CREATE TABLE SFX_BILLING.TEST (ID BIGINT, VALUE VARCHAR, AMOUNT DECIMAL(14,2))')
        after.execute('CREATE TABLE PC_BILLING.TEST (amount DECIMAL(18,4), value VARCHAR, id BIGINT, SRC_ROW_NO BIGINT)')
        if rows:
            LOCAL.copy_rows(before, 'SFX_BILLING.TEST', rows)
            LOCAL.copy_rows(after, 'PC_BILLING.TEST', [(v, s.rstrip(), i, n) for n, (i, s, v) in enumerate(rows)])
        result = LOCAL.pc_result(before, after, pc_mapping(), {'VALUE': 'character'})
        assert result['passed'] and result['hash_match']
        assert result['extra_columns'] == ['SRC_ROW_NO']
        assert result['before_count'] == result['after_count'] == len(rows)
        if rows:
            after.execute('UPDATE PC_BILLING.TEST SET value=\'X\'')
            assert not LOCAL.pc_result(before, after, pc_mapping(), {'VALUE': 'character'})['passed']


def test_pc_missing_columns_are_not_aliased_or_projected_away():
    with LOCAL.duckdb.connect() as before, LOCAL.duckdb.connect() as after:
        before.execute('CREATE SCHEMA SFX_BILLING')
        after.execute('CREATE SCHEMA PC_BILLING')
        before.execute('CREATE TABLE SFX_BILLING.TEST (ID BIGINT, ACCOUNT_NUMBER VARCHAR)')
        after.execute('CREATE TABLE PC_BILLING.TEST (ID BIGINT, ACCOUNT_NO VARCHAR)')
        result = LOCAL.pc_result(before, after, pc_mapping(), {})
        assert not result['passed'] and result['hash_match'] is None
        assert result['missing_columns'] == ['ACCOUNT_NUMBER']
        assert result['extra_columns'] == ['ACCOUNT_NO']
        excluded = pc_mapping(exclude_columns={'ACCOUNT_NUMBER': 'Explicit test exclusion'})
        assert LOCAL.pc_result(before, after, excluded, {})['passed']


def test_pc_rejects_invalid_exclusions_and_duplicate_multiplicity():
    with LOCAL.duckdb.connect() as before, LOCAL.duckdb.connect() as after:
        before.execute('CREATE SCHEMA SFX_BILLING')
        after.execute('CREATE SCHEMA PC_BILLING')
        for con, name in ((before, 'SFX_BILLING.TEST'), (after, 'PC_BILLING.TEST')):
            LOCAL.rows_table(con, name, ['ID'], [(1,), (1,)])
        excluded = pc_mapping(exclude_columns={'NOT_HERE': 'Invalid test exclusion'})
        assert LOCAL.pc_result(before, after, excluded, {})['error'] == 'Excluded columns absent from BEFORE'
        after.execute('DELETE FROM PC_BILLING.TEST')
        LOCAL.copy_rows(after, 'PC_BILLING.TEST', [(1,)])
        result = LOCAL.pc_result(before, after, pc_mapping(), {})
        assert not result['passed'] and not result['hash_match']
        assert result['measured']['changed_keys'] == 1


@pytest.mark.parametrize('workflow_fails', [False, True])
def test_pc_fixture_is_fresh_uses_same_landing_and_cleans_up(monkeypatch, tmp_path, workflow_fails):
    queries, calls = [], []

    class PG:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            queries.append(query if isinstance(query, str) else query.as_string())
            return self

        def fetchone(self):
            return (0,)

    def run(*args, **kwargs):
        calls.append((args, kwargs))
        if workflow_fails:
            raise LOCAL.subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(LOCAL.psycopg, 'connect', lambda *a, **kw: PG())
    monkeypatch.setattr(LOCAL.subprocess, 'run', run)
    monkeypatch.setattr(LOCAL, 'inventory', lambda: [dict(pc_mapping(), folder='SFX_BILLING')])
    monkeypatch.setenv('SNOWFLAKE_ACCOUNT', 'must-not-reach-child')
    landing = tmp_path / 'landing'

    def exercise():
        with LOCAL.pc_fixture('host=127.0.0.1 port=5432 user=postgres dbname=teradata',
                              LOCAL.dt.date(2026, 11, 9), landing, tmp_path) as (dsn, evidence):
            assert 'sfx_windows_pc_' in dsn
            assert evidence['initial_target_counts'] == {'TEST': 0}

    if workflow_fails:
        with pytest.raises(LOCAL.subprocess.CalledProcessError):
            exercise()
    else:
        exercise()
    assert queries[0].startswith('CREATE DATABASE "sfx_windows_pc_')
    assert queries[-1].startswith('DROP DATABASE "sfx_windows_pc_')
    env = calls[0][1]['env']
    assert env['LANDING_DIR'] == str(landing)
    assert env['TD_DB'].startswith('sfx_windows_pc_')
    assert not any(k.startswith('SNOWFLAKE_') for k in env)


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
