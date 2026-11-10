from collections import Counter
from contextlib import contextmanager
from datetime import date
import subprocess

from jinja2 import Environment
import pytest
import sqlglot

from parity import evidence_unt7 as u
from parity.evidence import cell, full_compare
from parity.harness import source_plan
from parity.inventory import inventory


def row(key='1', user='2', role='admin', day='2026-11-09'):
    return [key, user, role, day]


@pytest.mark.parametrize('text,value', [
    ('123', 123), (' 123 ', 123), ('+123', 123), ('-123', -123),
    ('12.9', 12), ('-12.9', -12), ('12suffix', 12), ('1e3', 1),
    ('9223372036854775808', 9223372036854775808), (None, None)])
def test_integer_contract(text, value):
    from runner.expr import _to_integer
    assert _to_integer(text) == value
    assert u.route_rows([row(key=text)])[0]['values'][0] == value


@pytest.mark.parametrize('text', ['bad', '', '   ', '*', '.5'])
def test_expression_errors_are_not_writer_rejects(text):
    from runner.expr import _to_integer, TransformationError
    with pytest.raises(TransformationError):
        _to_integer(text)
    r = u.route_rows([row(key=text)])[0]
    assert r['route'] == 'expression_error' and r['row_type'] is None


@pytest.mark.parametrize('day', ['bad-date', '*', '2026-02-30', '11/09/2026', '2026/11/09'])
def test_calendar_and_format_errors(day):
    from runner.expr import _to_date, TransformationError
    with pytest.raises(TransformationError):
        _to_date(day[:10], 'YYYY-MM-DD')
    assert u.route_rows([row(day=day)])[0]['route'] == 'expression_error'


@pytest.mark.parametrize('role,expected', [
    (' admin ', 'ADMIN'), ('MiXeD', 'MIXED'), ('\trole\t', '\tROLE\t'),
    (' abcdefghijklmnop ', 'ABCDEFGHIJK'), (None, None), ('*', '*'), ('            ', '')])
def test_role_slice_before_ascii_trim(role, expected):
    assert u.route_rows([row(role=role)])[0]['values'][2] == expected


@pytest.mark.parametrize('key,user', [(None, '2'), ('9223372036854775808', '2'),
                                     ('1', '9223372036854775808')])
def test_insert_reject_rowtype_is_zero(key, user):
    from runner.expr import DD_INSERT
    r = u.route_rows([row(key=key, user=user)])[0]
    assert r['row_type'] == DD_INSERT == 0 and not r['accepted']


def test_nulls_dates_and_truncate_replay():
    seed = [[999, 9, 'OLD         ', date(2000, 1, 1)], [1, 90, 'OLD         ', None]]
    rows = [row(user=None, role=None, day=None), row(key='2', day='2026-11-09suffix')]
    expected = [[1, None, None, None], [2, 2, 'ADMIN       ', date(2026, 11, 9)]]
    assert u.expected_target(seed, rows) == expected
    assert u.expected_target(expected, rows) == expected
    assert u.expected_target(seed, []) == []


def test_first_insert_wins_only_among_insertable_rows():
    rows = [row(user='9223372036854775808'), row(user='3'), row(user='4')]
    assert [r['row_type'] for r in u.route_rows(rows)] == [0, None, 0]
    assert u.expected_target([], rows)[0][1] == 3
    assert u.expected_stats([], rows)['ROLE_GRANT'] == {
        'inserted': 1, 'updated': 0, 'deleted': 0, 'rejected': 2}


def test_fixture_counts_and_frozen_source_ddl():
    frozen = u.read_psv(u.landing('frozen'))
    assert len(frozen) == 149 and u.sha(u.landing('frozen')) == u.FROZEN_SHA
    assert all(r['accepted'] for r in u.route_rows(frozen))
    assert len({r['values'][0] for r in u.route_rows(frozen)}) == 149
    rows = u.read_psv(u.landing('seeded'))
    assert len(rows) == 25
    assert Counter(r['route'] for r in u.route_rows(rows)) == {'insert': 17, 'expression_error': 8}
    assert Counter(r['row_type'] for r in u.route_rows(rows)) == {None: 21, 0: 4}
    seed = u.read_target(u.FIXTURES / 'seeded_target.psv')
    out = u.expected_target(seed, rows)
    assert len(out) == 13 and 999 not in {r[0] for r in out}
    assert next(r for r in out if r[0] == 101)[1] == 1
    entry = next(p for p in source_plan(u.ESTATE / 'tests/fixture/landing') if p[0] == 'ROLE_GRANT')
    assert 'GRANT_ID BIGINT' in entry[1] and 'ROLE_CD VARCHAR(200)' in entry[1]
    assert 'GRANTED_DT DATE' in entry[1]
    assert entry[2] == u.landing('frozen')


def snap(rows):
    return {'columns': ['GRANT_ID', 'ROLE_CD'],
            'types': {'GRANT_ID': ['bigint', None, 64, 0, None],
                      'ROLE_CD': ['character', 12, None, None, None]},
            'rows': [[cell(v) for v in row] for row in rows]}


def test_strict_multisets_and_not_parity():
    a = snap([[1, 'ADMIN       ']])
    assert u.comparisons(a, a, a, a)['passed']
    empty = snap([])
    assert u.comparisons(empty, empty, empty, empty)['passed']
    assert not full_compare(a, snap([[1, 'ADMIN']]), ['GRANT_ID'])['equal']
    assert not u.comparisons(a, a, snap([[1, 'ADMIN       ']] * 2), a)['passed']
    old = snap([[1, 'OLD']])
    result = u.comparisons(a, a, old, old, duplicate=True)
    assert result['passed'] and not result['oracle1_dbt1']['equal']


def test_input_empty_malformed_star(tmp_path):
    p = tmp_path / 'input.psv'
    p.write_text('')
    assert u.read_psv(p) == []
    p.write_text('1|2\n')
    with pytest.raises(ValueError, match='four columns'):
        u.read_psv(p)
    p.write_text('1||*|\n')
    assert u.read_psv(p) == [['1', None, '*', None]]


def test_write_scope_and_fresh_guard(tmp_path):
    for value in ('other', '', 'production; DROP TABLE X'):
        with pytest.raises(ValueError):
            u.target(value)
        with pytest.raises(ValueError):
            u.landing(value)
    for sql in ['GRANT SELECT TO ROLE X', 'TRUNCATE TABLE ' + u.TARGET,
                'INSERT INTO SFX_D1110_AFTER.PC_SRC.ROLE_GRANT VALUES (1)']:
        with pytest.raises(ValueError):
            u.fixture_write(None, [], sql)
    with pytest.raises(ValueError, match='Never overwrite'):
        u.fresh(tmp_path)


def test_preflight_refuses_even_empty_existing_target(monkeypatch, tmp_path):
    monkeypatch.setattr(u, 'DEST', tmp_path)
    @contextmanager
    def queries(*args, **kwargs):
        yield object()
    monkeypatch.setattr(u, 'queries', queries)
    monkeypatch.setattr(u, 'hashes', lambda: {})
    monkeypatch.setattr(u, 'control_snapshot', lambda *a: {})
    monkeypatch.setattr(u, 'frozen_input', lambda *a: {})
    monkeypatch.setattr(u, 'target_state', lambda *a: {'exists': True, 'row_count': 0})
    monkeypatch.setattr(u, 'load', lambda *a: snap([]))
    with pytest.raises(ValueError, match='Production target exists'):
        u.preflight()


def test_existing_fixture_schema_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(u, 'DEST', tmp_path)
    class Q:
        def run(self, sql):
            assert sql.startswith('SELECT')
            return [], [('PC_FX_UNT7_ROLE_GRANT',)]
    @contextmanager
    def queries(*args, **kwargs):
        yield Q()
    monkeypatch.setattr(u, 'queries', queries)
    with pytest.raises(ValueError, match='Fixture schema exists'):
        u.fixture_load()


def test_control_requires_twenty_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(u, 'capture_control', lambda *a: {'row_count': 19})
    with pytest.raises(ValueError, match='20 control rows'):
        u.control_snapshot(None, tmp_path)


def test_compiled_sql_and_model_enablement():
    macro = (u.ROOT / 'warehouse/dbt/macros/pc_content_role_grant.sql').read_text()
    module = Environment().from_string(macro).module
    for raw in (False, True):
        for rejects in (False, True):
            sql = module.pc_content_role_grant('SRC', rejects=rejects, raw_input=raw)
            assert sqlglot.parse_one(sql, read='snowflake')
            assert ('try_to_date' in sql) == raw
            assert ('rpad(' in sql) != rejects
    sql = module.pc_content_role_grant('SRC')
    assert 'count(*) over (partition by GRANT_ID)' in sql
    assert 'max(KEY_COUNT) over ()' in sql and '1 / iff(MAX_KEY_COUNT>1,0,1) = 1' in sql
    assert 'from converted_rows where not WRITER_REJECT' in sql
    rejects = module.pc_content_role_grant('SRC', rejects=True)
    assert 'select 0::number(38,0) as ROW_TYPE' in rejects
    for subject in u.SCENARIOS[1:]:
        text = (u.ROOT / ('warehouse/dbt/models/pc/content/unt7_fixture/' + u.model(subject) + '.sql')).read_text()
        assert "enabled=env_var('SFX_UNT7_ROLE_FIXTURE','0') == '1'" in text
        assert "schema='PC_FX_UNT7_ROLE_GRANT'" in text
        assert "materialized='table'" in text and "full_refresh=false" in text
    schema_macro = (u.ROOT / 'warehouse/dbt/macros/generate_schema_name.sql').read_text()
    assert 'custom_schema_name | trim if custom_schema_name else target.schema' in schema_macro


def test_inventory_append_only_and_hash_coverage():
    mapping = next(r for r in inventory() if r['mapping'] == u.MAPPING)
    assert mapping['after_table'] == 'PC_CONTENT.ROLE_GRANT'
    assert mapping['key_columns'] == ['GRANT_ID']
    original = subprocess.check_output(['git', 'show',
        'ed22934c:warehouse/parity/mappings/sfx_content.yml'], cwd=u.ROOT)
    assert (u.ROOT / 'warehouse/parity/mappings/sfx_content.yml').read_bytes().startswith(original)
    hashed = u.hashes()
    assert 'warehouse/parity/evidence_unt7.py' in hashed
    assert 'warehouse/parity/tests/test_evidence_unt7.py' in hashed
    assert set(u.PROTECTED) == {'STG_APP_USER', 'APP_USER', 'STG_DOCUMENT', 'DOCUMENT', 'DOC_SHARE', 'LOGIN_EVENT'}


def test_oracle_captures():
    for name in u.SCENARIOS:
        path = u.DEST / 'oracle' / name
        if not path.exists():
            pytest.skip('Local artifacts are not committed')
        initial = u.load(path / 'initial_target.json')
        rows = u.read_psv(u.landing(name))
        expected = u.typed(u.expected_target([], rows), initial)
        for n in (1, 2):
            actual = u.load(path / f'run{n}/target.json')
            assert full_compare(expected, actual, ['GRANT_ID'])['equal']
            sessions = u.load(path / f'run{n}/session_results.json')
            assert sessions[0]['RUN_STATUS'] == 'SUCCEEDED'
            assert int(sessions[0]['FAILED_SOURCE_ROWS']) == sum(
                r['route'] == 'expression_error' for r in u.route_rows(rows))
            stats = u.load(path / f'run{n}/writer_stats.json')
            assert all(stats[i][k] == v for i, counts in u.expected_stats([], rows).items() for k, v in counts.items())
            bad = [line for f in u.load(path / f'run{n}/rejects.json') for line in f['rows']]
            assert u.bad_multiset(bad) == u.bad_multiset([
                u.bad_line(r['row_type'], r['values']) for r in u.route_rows(rows) if r['row_type'] is not None])


def test_intervening_statements_success_only():
    failed = ('failed-qid', 'SELECT COUNT(*) AS ROWS FROM PC_CONTENT.ROLE_GRANT',
              'UNKNOWN', '', '', '', 'FAILED_WITH_ERROR', '001003', 'unexpected ROWS')
    write = ('write-qid', 'CREATE TABLE PC_CONTENT.ROLE_GRANT AS SELECT 1',
             'CREATE_TABLE_AS_SELECT', '', '', '', 'SUCCESS', None, None)
    read = ('read-qid', 'SELECT * FROM PC_CONTENT.ROLE_GRANT',
            'SELECT', '', '', '', 'SUCCESS', None, None)
    writes, failures = u.intervening_statements([failed, write, read], u.TARGET)
    assert writes == [write] and failures == [failed]
    assert u.intervening_statements([], u.TARGET) == ([], [])


def test_comparison_attempt_preserves_original(tmp_path):
    (tmp_path / 'comparison.json').write_text('failed original')
    (tmp_path / 'between_runs').mkdir()
    (tmp_path / 'between_runs/queries.json').write_text('original queries')
    output, before = u.comparison_attempt(tmp_path)
    assert output != tmp_path and output.is_dir()
    u.dump(output / 'comparison.json', {'passed': True})
    proof = u.preserved_comparison(tmp_path, before)
    assert proof['byte_identical'] and proof['before'] == proof['after']
    again, _ = u.comparison_attempt(tmp_path)
    assert again != output
    (tmp_path / 'comparison.json').write_text('modified')
    with pytest.raises(ValueError, match='capture changed'):
        u.preserved_comparison(tmp_path, before)


def test_first_comparison_uses_original_path(tmp_path):
    output, before = u.comparison_attempt(tmp_path)
    assert output == tmp_path and before == {}


def test_continuation_only_allows_collector_and_test_changes(monkeypatch):
    old = {'warehouse/dbt/macros/pc_content_role_grant.sql': 'dbt',
           'oracle/runner.py': 'oracle', **{p: 'old' for p in u.CONTINUATION_ALLOWLIST}}
    new = {**old, **{p: 'new' for p in u.CONTINUATION_ALLOWLIST}}
    monkeypatch.setattr(u, 'hashes', lambda: new)
    monkeypatch.setattr(u, 'head', lambda: 'new-head')
    result = u.continuation({'commit': 'old-head', 'hashes': old})
    assert result['preflight_head'] == 'old-head' and result['executed_head'] == 'new-head'
    assert set(result['changed_files']) == set(u.CONTINUATION_ALLOWLIST)
    for p in ('warehouse/dbt/macros/pc_content_role_grant.sql', 'oracle/runner.py', 'unexpected'):
        new[p] = 'modified'
        with pytest.raises(ValueError, match='Implementation changed'):
            u.continuation({'commit': 'old-head', 'hashes': old})
        if p in old:
            new[p] = old[p]
        else:
            del new[p]
