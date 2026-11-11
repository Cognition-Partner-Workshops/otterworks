from collections import Counter
from datetime import date
import importlib.util
from pathlib import Path
import re
import subprocess
import unicodedata

from jinja2 import Environment
import pytest

from parity import evidence_unt8 as u
from parity.evidence import cell, full_compare
from parity.harness import source_plan


def row(key='1', team='2', user='3', role='admin', day='2026-11-09'):
    return [key, team, user, role, day]


@pytest.mark.parametrize('text,value', [('12abc', 12), ('12.9', 12), ('-12.9', -12),
    ('-7', -7), (' 42 ', 42), ('\x1c42\u00a0', 42), ('１２abc', 12), ('١٢', 12), ('1e9', 1), (None, None)])
def test_python_integer_contract(text, value):
    record = u.route(row(team=text))
    assert record['classification'] == 'accepted'
    assert record['values'][1] == value


@pytest.mark.parametrize('text', ['bad', '', ' ', '*', '.5', '+bad'])
def test_transformation_drops(text):
    assert u.route(row(key=text))['classification'] == 'transformation_drop'


@pytest.mark.parametrize('day', ['2026-02-30', '2026/11/09', '11/09/2026', '0000-01-01', '*'])
def test_date_errors(day):
    assert u.route(row(day=day))['classification'] == 'transformation_drop'


@pytest.mark.parametrize('role,want', [('é', 'É'), ('ß', 'SS'), ('中文', '中文'),
    (' admin ', 'ADMIN'), ('\trole\t', '\tROLE\t'), (' abcdefghijklmnop ', 'ABCDEFGHIJK'),
    (None, None), ('            ', ''), ('\u00a0a\u00a0', '\u00a0A\u00a0')])
def test_role_ascii_trim_and_unicode_upper(role, want):
    assert u.route(row(role=role))['values'][3] == want


def test_precision_date_null_and_empty_batch():
    record = u.route(row(team='00000000000000000000123', day='2026-11-09suffix'))
    assert record['values'][1] == 0 and record['values'][4] == date(2026, 11, 9)
    assert u.route(row(day=None))['values'][4] is None
    seed = [[999, 2, 3, 'OLD         ', None]]
    assert u.expected(seed, []) == seed
    assert u.expected([], []) == []


@pytest.mark.parametrize('changes', [dict(key=None), dict(key='9223372036854775808'),
    dict(team='9223372036854775808'), dict(user='-9223372036854775809'), dict(role='a\x00b')])
def test_writer_rejects(changes):
    assert u.route(row(**changes))['classification'] == 'writer_reject'


def test_last_successful_update_wins_and_unmentioned_rows_survive():
    initial = [[1, 90, 91, 'OLD         ', None], [999, 90, 91, 'SURVIVES    ', None]]
    rows = [row(team='4'), row(team='5'), row(team='9223372036854775808')]
    actual = u.expected(initial, rows)
    assert actual[0][1] == 5 and actual[1] == initial[1]
    assert u.expected(actual, rows) == actual
    assert u.writer_rejects(initial, rows) == ['1,D,1,D,9223372036854775808,D,3,D,ADMIN,D,2026-11-09']
    assert u.writer_rejects([], [row(key=None)])[0].startswith('0,D,')
    assert u.writer_rejects([], [row(team='9223372036854775808')])[0].startswith('1,D,')
    assert u.seed('seeded')[1][3] == 'SURVIVES    '


def test_fixture_valid_keys_unique_and_update_survival():
    rows = u.read_psv(u.landing('seeded'))
    accepted = [r['values'][0] for r in map(u.route, rows) if r['classification'] == 'accepted']
    assert len(accepted) == len(set(accepted))
    result = {r[0]: r for r in u.expected(u.seed('seeded'), rows)}
    assert result[101][1] == 2 and result[999][3].strip() == 'SURVIVES'
    assert u.expected(list(result.values()), rows) == list(result.values())
    assert u.expected(u.seed('dup_key'), u.read_psv(u.landing('dup_key')))[0][3].strip() == 'SECOND'


def test_source_has_no_ordinal():
    entry = next(r for r in source_plan(u.ESTATE / 'tests/fixture/landing') if r[0] == 'TEAM_MEMBER')
    columns = re.findall(r'^\s*(\w+)\s+\w+', entry[1], re.M)
    assert columns == u.COLUMNS


def test_mapping_change_is_pure_append():
    path = 'warehouse/parity/mappings/sfx_content.yml'
    original = subprocess.check_output(['git', 'show', '47bea1ddf5f834f15285aa3593ec22bfdb714212:' + path], cwd=u.ROOT)
    current = (u.ROOT / path).read_bytes()
    assert current.startswith(original)
    assert current[len(original):].count(b'm_SFX_TEAM_MEMBER:') == 1


def test_generated_unicode_is_reproducible():
    spec = importlib.util.spec_from_file_location('unt8_unicode', u.FIXTURES / 'generate_unicode.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    actual = (u.ROOT / 'warehouse/dbt/macros/unt8_python_unicode.sql').read_text()
    recorded_version = re.search(r'; Unicode ([0-9.]+)\. #}', actual.splitlines()[0]).group(1)
    if unicodedata.unidata_version != recorded_version:
        pytest.skip(f'Committed macro uses Unicode {recorded_version}; runtime uses Unicode {unicodedata.unidata_version}')
    assert actual == module.macro()
    assert 'chr(28)' in actual and 'chr(133)' in actual and 'chr(12288)' in actual
    assert '"\\u00df":"SS"' in actual


def test_models_are_incremental_single_key_no_refresh():
    for subject in u.SUBJECTS:
        path = u.ROOT / 'warehouse/dbt/models/pc/content'
        path /= ('pc_content__team_member.sql' if subject == 'production'
                 else 'unt8_fixture/' + u.model(subject) + '.sql')
        text = path.read_text()
        for fragment in ["materialized='incremental'", "incremental_strategy='merge'", "unique_key='TEAM_MEMBER_ID'", 'full_refresh=false']:
            assert fragment in text
        if subject != 'production':
            assert "schema='PC_FX_UNT8_TEAM_MEMBER'" in text and 'SFX_UNT8_TEAM_FIXTURE' in text


def test_macro_has_atomic_duplicate_guard_and_no_delete():
    text = (u.ROOT / 'warehouse/dbt/macros/pc_content_team_member.sql').read_text()
    env = Environment()
    env.globals.update(unt8_integer_prefix=lambda value: value,
                       unt8_python_upper=lambda value: value, unt8_decimal_digits=lambda value: value)
    macro = env.from_string(text).module.pc_content_team_member
    for raw in (False, True):
        sql = macro('SOURCE_TABLE', raw_input=raw)
        assert 'partition by TEAM_MEMBER_ID' in sql and 'MAX_KEY_COUNT>1' in sql
        assert 'DELETE' not in sql.upper() and 'TRUNCATE' not in sql.upper()
        analysis = macro('SOURCE_TABLE', rejects=True, raw_input=raw)
        assert 'transformation_drop' in analysis and 'writer_reject' in analysis
        assert 'CLASSIFICATION_COUNT' in analysis
        import sqlglot
        assert sqlglot.parse_one(sql, read='snowflake')
        assert sqlglot.parse_one(analysis, read='snowflake')


def test_write_scope_fails_closed():
    def record(sql, status='SUCCESS'):
        return ['qid', sql, 'MERGE', '{"mapping":"m_SFX_TEAM_MEMBER"}', None, None, status, None, None]
    good = record('MERGE INTO "SFX_D1110_AFTER"."PC_CONTENT"."TEAM_MEMBER" USING t ON true')
    bad = record('UPDATE SFX_D1110_AFTER.PC_CONTENT.ROLE_GRANT SET ROLE_CD=1')
    failed = record('UNKNOWN SQL', 'FAILED_WITH_ERROR')
    assert u.write_scope([good, failed])['passed']
    assert not u.write_scope([good, bad])['passed']
    assert not u.write_scope([record('EXECUTE TASK other_task')])['passed']


def test_dirty_tree_refused_before_evidence_creation(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, 'check_output', lambda *a, **kw: ' M file\n')
    with pytest.raises(ValueError, match='dirty tree'):
        u.fresh(tmp_path / 'capture')
    assert not (tmp_path / 'capture').exists()


def test_success_only_intervening_history():
    def history(kind, status, sql):
        return ['qid', sql, kind, '{}', None, None, status, 'error', 'message']
    failed = history('UNKNOWN', 'FAILED_WITH_ERROR', 'SELECT TEAM_MEMBER')
    write = history('MERGE', 'SUCCESS', 'MERGE INTO PC_CONTENT.TEAM_MEMBER')
    read = history('SELECT', 'SUCCESS', 'SELECT * FROM PC_CONTENT.TEAM_MEMBER')
    assert u.intervening([failed, write, read], u.TARGET) == ([write], [failed])


def test_multiset_differences_do_not_hide_duplicates():
    snap = {'columns': u.COLUMNS, 'types': {}, 'rows': [[cell(v) for v in [1, 2, 3, 'A', None]]]}
    assert not full_compare(snap, {**snap, 'rows': snap['rows'] * 2}, u.KEYS)['equal']


def test_bounded_history_filters_and_paginates():
    class Queries:
        calls = []

        def run(self, sql):
            self.calls.append(sql)
            row = ['qid', 'SELECT 1', 'SELECT', '{}', 'time', 'time', 'SUCCESS', None, None]
            if len(self.calls) == 1:
                return [], [row + [10000, True]]
            return [], [row + [2, True], ['running'] * 9 + [2, False]]

    q = Queries()
    assert len(u.history(q, '2026-11-10T00:00:00+00:00', '2026-11-10T01:00:00+00:00')) == 1
    assert len(q.calls) == 3
    assert all('END_TIME >= START_TIME' in sql and "EXECUTION_STATUS <> 'RUNNING'" in sql
               and 'START_TIME >=' in sql and 'END_TIME <=' in sql for sql in q.calls)


def test_bounded_history_empty_and_invalid():
    class Queries:
        def run(self, sql):
            return [], []
    assert u.history(Queries(), '2026-11-10T00:00:00+00:00', '2026-11-10T00:00:01+00:00') == []
    with pytest.raises(ValueError, match='timezone-aware'):
        u.history(Queries(), '2026-11-10', '2026-11-09')


def test_bounded_history_fails_on_unsplittable_truncation():
    class Queries:
        def run(self, sql):
            return [], [[None] * 9 + [10000, True]]
    with pytest.raises(ValueError, match='Bounded history truncated'):
        u.history(Queries(), '2026-11-10T00:00:00+00:00', '2026-11-10T00:00:00+00:00')


def test_continuation_hash_gate(monkeypatch, tmp_path):
    original = {'head': '2108f983f65993a9cee828b2a2bbb21ee1f9c87a', 'sha256': {'model': 'a'}}
    monkeypatch.setattr(u, 'load', lambda path: {'implementation': original})
    monkeypatch.setattr(u, 'binding', lambda: {**original, 'head': 'new'})
    u.continuation(tmp_path)
    assert (tmp_path / 'continuation_binding.json').exists()
    monkeypatch.setattr(u, 'binding', lambda: {**original, 'sha256': {'model': 'changed'}})
    with pytest.raises(ValueError, match='outside collector/test'):
        u.continuation(tmp_path)


def test_content_inventory_guard():
    def row(name, count=1):
        return {'TABLE_NAME': ['str', name], 'ROW_COUNT': ['int', str(count)]}
    before = [row('ROLE_GRANT'), row('TEAM_MEMBER')]
    u.inventory_guard(before, [row('ROLE_GRANT'), row('TEAM_MEMBER', 2)])
    with pytest.raises(ValueError, match='outside TEAM_MEMBER'):
        u.inventory_guard(before, [row('ROLE_GRANT', 2)])
    with pytest.raises(ValueError, match='scratch relation remains'):
        u.inventory_guard(before, before + [row('TEAM_MEMBER__DBT_TMP')])


@pytest.mark.parametrize('relation', [u.TARGET, u.TARGET + '__dbt_tmp',
                                    u.SCHEMA + '.UNT8_FIXTURE_SEEDED',
                                    u.SCHEMA + '.UNT8_FIXTURE_DUP_KEY__dbt_tmp'])
@pytest.mark.parametrize('sql', [
    'create or replace  temporary view {relation}\n  as (select 1)',
    'merge into {relation} as DBT_INTERNAL_DEST using tmp on true when matched then update set a=1',
    'drop view if exists {relation} cascade',
    'alter table {relation} set tag "SFX_D1110_AFTER".GOVERNANCE.SFX_RUN = \'sfx-d1110\'',
    'comment on table {relation}\n is \'run_token=sfx-d1110 expires=2026-11-24\'',
    'comment on view {relation} is \'run_token=sfx-d1110\'',
])
def test_actual_dbt_statement_shapes_whitespace(sql, relation):
    text = sql.format(relation=relation)
    for variant in (text, re.sub(' +', '\t\n ', text).swapcase(), ' /* dbt */ ' + text):
        row = ['qid', variant, 'ALTER', '{"mapping":"m_SFX_TEAM_MEMBER"}', None, None, 'SUCCESS', None, None]
        result = u.write_scope([row])
        assert result['passed']
        assert result['writes'][0]['relation'] == relation.upper()


def test_actual_captured_run2_queries():
    path = u.DEST / 'production/run2/history.json'
    if not path.exists():
        pytest.skip('Local captured Snowflake history not present')
    records = [[None if c[0] == 'null' else c[1] for c in row] for row in u.load(path)]
    assert any('create or replace  temporary view' in r[1] for r in records)
    for subject in ('production', 'seeded', 'dup_key'):
        projected = [list(row) for row in records]
        if subject != 'production':
            for row in projected:
                row[1] = row[1].replace(u.TARGET, u.table(subject)).replace(
                    '"SFX_D1110_AFTER"."PC_CONTENT"."TEAM_MEMBER"', u.table(subject))
        result = u.write_scope(projected)
        assert result['passed']
        assert not result['failed_statements']


@pytest.mark.parametrize('kind,sql', [('DESCRIBE', 'describe table t'), ('SHOW', 'show terse objects'),
                                      ('SELECT', 'select 1'), ('BEGIN', 'begin;'),
                                      ('COMMIT', 'COMMIT'), ('ALTER_SESSION', 'alter session set query_tag=\'x\'')])
def test_dbt_read_and_session_shapes(kind, sql):
    row = ['qid', sql, kind, '{"mapping":"m_SFX_TEAM_MEMBER"}', None, None, 'SUCCESS', None, None]
    assert u.write_scope([row])['passed']


@pytest.mark.parametrize('relation', [u.TARGET + '__DBT_OTHER', u.TARGET + '_OTHER',
                                    'SFX_D1110_AFTER.PC_CONTENT.ROLE_GRANT',
                                    'SFX_D1110_AFTER.MIGRATION_CONTROL.MAPPINGS',
                                    'SFX_D1110_AFTER.PC_FX_UNT7_ROLE_GRANT.X'])
def test_classifier_does_not_expand_allowed_objects(relation):
    row = ['qid', 'create or replace  temporary view ' + relation + ' as (select 1)', 'CREATE_VIEW',
           '{"mapping":"m_SFX_TEAM_MEMBER"}', None, None, 'SUCCESS', None, None]
    assert not u.write_scope([row])['passed']
