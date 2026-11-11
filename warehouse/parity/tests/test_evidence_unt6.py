from collections import Counter
from datetime import datetime
import subprocess

from jinja2 import Environment
import pytest

from parity import evidence_unt6 as u
from parity.evidence import cell, full_compare
from parity.harness import source_plan
from parity.inventory import inventory


def row(key='1', user='2', stamp='2026-11-09 01:02:03', code='SUCCESS', client='WEB'):
    return [key, user, stamp, code, client]


@pytest.mark.parametrize('value,expected', [
    ('123', 123), (' 123 ', 123), ('+123', 123), ('-123', -123),
    ('12.9', 12), ('-12.9', -12), ('12suffix', 12), ('1e3', 1),
    ('9223372036854775808', 9223372036854775808), (None, None),
])
def test_integer_semantics_against_runner(value, expected):
    from runner.expr import _to_integer
    assert _to_integer(value) == expected
    assert u.route_rows([row(key=value)])[0]['values'][0] == expected


@pytest.mark.parametrize('value', ['bad', '', '   ', '*', '.5'])
def test_bad_integer_drops_without_writer_reject(value):
    from runner.expr import _to_integer, TransformationError
    with pytest.raises(TransformationError):
        _to_integer(value)
    result = u.route_rows([row(key=value)])[0]
    assert result['route'] == 'expression_error'
    assert result['row_type'] is None and not result['accepted']


@pytest.mark.parametrize('code,route', [
    ('SUCCESS', 'success'), (' success ', 'success'), ('FAILED', 'failure'),
    ('LOCKED', 'failure'), ('mfa_failed', 'failure'), ('TIMEOUT', 'default'),
    (None, 'default'), ('', 'default'), ('*', 'default'), ('\tSUCCESS\t', 'default'),
    ('SUCCESS_MORE', 'default'),
])
def test_router_cases(code, route):
    result = u.route_rows([row(code=code)])[0]
    assert result['route'] == route
    assert result['accepted'] == (route != 'default')
    assert result['row_type'] is None


@pytest.mark.parametrize('stamp', ['bad-date', '*', '2026-02-30 00:00:00', '2026-11-09 25:00:00'])
def test_bad_date_drops(stamp):
    from runner.expr import _to_date, TransformationError
    with pytest.raises(TransformationError):
        _to_date(stamp, 'YYYY-MM-DD HH24:MI:SS')
    assert u.route_rows([row(stamp=stamp)])[0]['route'] == 'expression_error'


def test_null_timestamp_user_and_string_padding():
    result = u.expected_target([], [row(user=None, stamp=None, client=None)])
    assert result == [[1, None, None, 'SUCCESS     ', None]]
    assert u.route_rows([row(client=' abcdefghijklmnop ')])[0]['values'][4] == 'ABCDEFGHIJK'
    assert u.route_rows([row(client='\tweb\t')])[0]['values'][4] == '\tWEB\t'


@pytest.mark.parametrize('key,user,rt', [(None, '2', 0), ('9223372036854775808', '2', 0),
                                      ('1', '9223372036854775808', 1)])
def test_writer_reject_rowtypes(key, user, rt):
    result = u.route_rows([row(key=key, user=user)])[0]
    assert not result['accepted'] and result['row_type'] == rt


def test_fixture_routes_and_frozen_input():
    frozen = u.read_psv(u.landing('frozen'))
    assert len(frozen) == 420 and u.sha(u.landing('frozen')) == u.FROZEN_SHA
    assert Counter(r['route'] for r in u.route_rows(frozen)) == {'success': 364, 'failure': 48, 'default': 8}
    routed = u.route_rows(u.read_psv(u.landing('seeded')))
    assert len(routed) == 28
    assert Counter(r['route'] for r in routed) == {'success': 11, 'failure': 6, 'default': 5, 'expression_error': 6}
    assert Counter(r['row_type'] for r in routed) == {None: 24, 0: 3, 1: 1}


def test_last_writer_and_seed_preservation():
    rows = u.read_psv(u.landing('seeded'))
    seed = u.read_target(u.FIXTURES / 'seeded_target.psv')
    target = {r[0]: r for r in u.expected_target(seed, rows)}
    assert len(target) == 14
    assert target[101][1] == 1
    assert target[103] == seed[1] and target[104] == seed[2]
    assert target[112][1:] == [13, datetime(2026, 11, 9, 12, 13, 14), 'LOCKED      ', 'IOS         ']
    assert target[116][1] == 17 and target[116][4] == '*           '
    assert u.expected_stats(seed, rows) == {
        'LOGIN_EVENT': {'inserted': 8, 'updated': 1, 'deleted': 0, 'rejected': 2},
        'LOGIN_EVENT1': {'inserted': 3, 'updated': 1, 'deleted': 0, 'rejected': 2}}
    duplicate = u.expected_target(u.read_target(u.FIXTURES / 'dup_within_route_target.psv'),
                                  u.read_psv(u.landing('dup_within_route')))
    assert len(duplicate) == 1 and duplicate[0][1] == 2


def snap(rows):
    return {'columns': ['LOGIN_ID', 'CLIENT_TYPE'],
            'types': {'LOGIN_ID': ['bigint', None, 64, 0, None],
                      'CLIENT_TYPE': ['character', 12, None, None, None]},
            'rows': [[cell(v) for v in r] for r in rows]}


def test_strict_multisets_empty_and_duplicate_not_parity():
    a = snap([[1, 'WEB         ']])
    assert u.comparisons(a, a, a, a)['passed']
    assert u.comparisons(snap([]), snap([]), snap([]), snap([]))['passed']
    assert not u.comparisons(a, a, snap([[1, 'WEB']]), a)['passed']
    assert not full_compare(snap([[1, None]]), snap([[1, '']]), ['LOGIN_ID'])['equal']
    dup = snap([[1, 'WEB'], [1, 'WEB']])
    assert not u.comparisons(dup, dup, dup, dup)['passed']
    keep = snap([[1, 'OLD']])
    result = u.comparisons(a, a, keep, keep, duplicate=True)
    assert result['passed'] and not result['oracle1_dbt1']['equal']


def test_empty_malformed_psv_and_null_character(tmp_path):
    p = tmp_path / 'input.psv'
    p.write_text('')
    assert u.read_psv(p) == []
    p.write_text('1|2\n')
    with pytest.raises(ValueError, match='five columns'):
        u.read_psv(p)
    p.write_text('1||2026-11-09 01:02:03|*|\n')
    assert u.read_psv(p) == [['1', None, '2026-11-09 01:02:03', '*', None]]


def test_scope_and_write_guards(tmp_path):
    with pytest.raises(ValueError):
        u.target('other')
    with pytest.raises(ValueError):
        u.landing('other')
    for sql in ['GRANT SELECT TO ROLE X', 'TRUNCATE TABLE ' + u.TARGET,
                'INSERT INTO SFX_D1110_AFTER.PC_SRC.LOGIN_EVENT VALUES (1)']:
        with pytest.raises(ValueError):
            u.fixture_write(None, [], sql)
    tmp_path.mkdir(exist_ok=True)
    with pytest.raises(ValueError, match='Never overwrite'):
        u.fresh(tmp_path)


def test_preflight_refuses_populated_initial_target(monkeypatch, tmp_path):
    from contextlib import contextmanager
    monkeypatch.setattr(u, 'DEST', tmp_path)
    @contextmanager
    def queries(*args, **kwargs):
        yield object()
    monkeypatch.setattr(u, 'queries', queries)
    monkeypatch.setattr(u, 'hashes', lambda: {})
    monkeypatch.setattr(u, 'control_snapshot', lambda *a: {})
    monkeypatch.setattr(u, 'frozen_input', lambda *a: {})
    monkeypatch.setattr(u, 'target_state', lambda *a: {'exists': True})
    monkeypatch.setattr(u, 'load', lambda *a: snap([]))
    monkeypatch.setattr(u, 'fetched', lambda *a: snap([[1, 'EXISTING']]))
    with pytest.raises(ValueError, match='Typed multiset mismatch'):
        u.preflight()


def test_fixture_load_refuses_existing_schema(monkeypatch, tmp_path):
    from contextlib import contextmanager
    monkeypatch.setattr(u, 'DEST', tmp_path)
    class Q:
        def run(self, sql):
            assert sql.startswith('SELECT')
            return [], [('PC_CONTENT_UNT6_FIXTURE',)]
    @contextmanager
    def queries(*args, **kwargs):
        yield Q()
    monkeypatch.setattr(u, 'queries', queries)
    with pytest.raises(ValueError, match='Fixture schema exists'):
        u.fixture_load()


def test_macro_and_fixture_enablement():
    macro = (u.ROOT / 'warehouse/dbt/macros/pc_content_login_event.sql').read_text()
    module = Environment().from_string(macro).module
    sql = module.pc_content_login_event('SRC')
    assert 'count(*) over (partition by ROUTE,LOGIN_ID)' in sql
    assert 'max(ROUTE_COUNT) over ()' in sql and '1 / iff(MAX_ROUTE_COUNT>1,0,1) = 1' in sql
    assert 'order by ROUTE desc' in sql and "rpad(CLIENT_TYPE,12,' ')" in sql
    rejects = module.pc_content_login_event('SRC', rejects=True, raw_input=True)
    assert 'from routed where ROUTE<>3 and WRITER_REJECT' in rejects
    assert 'rpad(' not in rejects and 'try_to_timestamp_ntz' in rejects
    for subject in u.SCENARIOS[1:]:
        model = u.ROOT / ('warehouse/dbt/models/pc/content/unt6_fixture/' + u.model(subject) + '.sql')
        text = model.read_text()
        assert "enabled=env_var('SFX_UNT6_LOGIN_FIXTURE','0') == '1'" in text
        assert "schema='PC_CONTENT_UNT6_FIXTURE'" in text


def test_inventory_loader_and_act3_bytes():
    rows = inventory()
    mapping = next(r for r in rows if r['mapping'] == u.MAPPING)
    assert mapping['after_table'] == 'PC_CONTENT.LOGIN_EVENT' and mapping['key_columns'] == ['LOGIN_ID']
    config = u.ROOT / 'warehouse/parity/mappings/sfx_content.yml'
    ref = 'origin/devin/sfx-d1110-act3-content'
    if subprocess.run(['git', 'rev-parse', '--verify', ref], cwd=u.ROOT,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        pytest.skip('Sibling ref origin/devin/sfx-d1110-act3-content is unavailable in this checkout')
    original = subprocess.check_output(['git', 'show',
        'origin/devin/sfx-d1110-act3-content:warehouse/parity/mappings/sfx_content.yml'], cwd=u.ROOT)
    assert config.read_bytes().startswith(original)
    entry = next(p for p in source_plan(u.ESTATE / 'tests/fixture/landing') if p[0] == 'LOGIN_EVENT')
    assert 'LOGIN_ID BIGINT' in entry[1] and 'RESULT_CD VARCHAR(200)' in entry[1]
    assert entry[2] == u.landing('frozen')


def test_raw_captures_match_independent_expectations():
    for scenario in u.SCENARIOS:
        path = u.DEST / 'oracle' / scenario
        if not path.exists():
            pytest.skip('Local oracle artifacts are not committed')
        initial = u.load(path / 'initial_target.json')
        rows = u.read_psv(u.landing(scenario))
        expected = u.typed(u.expected_target([[u.native(c) for c in r] for r in initial['rows']], rows), initial)
        for n in (1, 2):
            actual = u.load(path / f'run{n}/target.json')
            assert full_compare(expected, actual, ['LOGIN_ID'])['equal']
            session = u.load(path / f'run{n}/session_results.json')[0]
            assert session['RUN_STATUS'] == 'SUCCEEDED'
            assert int(session['FAILED_SOURCE_ROWS']) == sum(r['route'] == 'expression_error' for r in u.route_rows(rows))
            prior = initial if n == 1 else u.load(path / 'run1/target.json')
            stats = u.expected_stats([[u.native(c) for c in r] for r in prior['rows']], rows)
            actual_stats = u.load(path / f'run{n}/writer_stats.json')
            assert all(actual_stats[i][k] == v for i, counts in stats.items() for k, v in counts.items())
            bad = [line for f in u.load(path / f'run{n}/rejects.json') for line in f['rows']]
            assert u.bad_multiset(bad) == u.bad_multiset([u.bad_line(r['row_type'], r['values'])
                for r in u.route_rows(rows) if r['row_type'] is not None])
