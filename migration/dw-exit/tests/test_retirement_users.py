import copy

import pytest
import yaml

import assess
from parity import object_board, provenance, retirement_users

ROOT = retirement_users.ROOT


@pytest.fixture(scope='module')
def current():
    return assess.build(root=ROOT), assess.dbql(ROOT)


def test_current_dbql_and_propagation(current):
    evidence = retirement_users.verify()
    assert evidence['passed']
    assert evidence['reads'] == {'SFX_USERS.USER_PREF': 0, 'SFX_USERS.V_USER_SETTINGS': 0}
    assert evidence['observed_window'] == ['2026-08-12', '2026-11-09']
    assert evidence['query_count'] > 0
    assert len(evidence['sha256']) == 3
    assert set(evidence['dead_dependents']) == retirement_users.DEPENDENTS


@pytest.mark.parametrize('failure', ['reads', 'empty', 'window', 'dead', 'dependents', 'target'])
def test_changed_or_empty_evidence_fails_closed(current, monkeypatch, failure):
    estate, (queries, usage, catalog, dead) = copy.deepcopy(current)
    if failure == 'reads':
        usage.append(dict(QueryID=next(iter(queries)), ObjectDatabaseName='SFX_USERS',
                          ObjectTableName='USER_PREF', UsageType='READ'))
    elif failure == 'empty':
        queries, usage = {}, []
    elif failure == 'window':
        queries = {k: v for k, v in queries.items() if v['StartTime'][:10] != '2026-11-09'}
    elif failure == 'dead':
        dead.remove('SFX_USERS.USER_PREF')
    elif failure == 'dependents':
        estate['dead_dependents'].remove('users_user_pref')
    else:
        next(o for o in estate['objects'] if o['name'] == 'users_user_pref')['target_type'] = 'dbt_model'
    monkeypatch.setattr(assess, 'build', lambda *, root: estate)
    monkeypatch.setattr(assess, 'dbql', lambda root: (queries, usage, catalog, dead))
    assert retirement_users.verify()['passed'] is False


def test_unavailable_evidence_fails_closed(monkeypatch):
    def unavailable(**kwargs):
        raise OSError('DBQL unavailable')
    monkeypatch.setattr(assess, 'build', unavailable)
    evidence = retirement_users.verify()
    assert evidence['passed'] is False
    assert 'DBQL unavailable' in evidence['reason']


@pytest.mark.parametrize('passed', [False, True])
def test_retirement_board_is_not_migrated_or_live_green(monkeypatch, passed):
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    manifest['objects'] = [o for o in manifest['objects'] if o['subject_area'] == 'users' and o['target_type'] == 'retire']
    monkeypatch.setattr(retirement_users, 'verify', lambda: dict(passed=passed, reason='current check'))
    board = object_board.build_board(manifest)
    assert board['summary']['users']['local_green'] == 0
    assert board['summary']['users']['local_retired'] == (4 if passed else 0)
    assert board['summary']['users']['local_red'] == (0 if passed else 4)
    assert board['summary']['migrated'] == 0
    for row in board['rows']:
        assert row['local_duckdb'] == ('retired' if passed else 'red')
        if passed:
            assert row['retirement_evidence']['decision_id'] == 'sfg1120-user-pref-retirement'
            assert row['retirement_evidence']['owner_approved'] is True
        assert row['snowflake'] == 'red'
        assert row['row_count'] is None and row['keyed_row_hash'] is None
        assert row['migration_status'] == 'not_started'
        assert row['licence_dependency_count'] == 1
        assert 'Spark USER_PREF' in row['reason']
        metrics = row['provenance']['metrics']
        assert 'retirement_absence' in metrics and 'retirement_propagation' in metrics
        assert 'retirement_objectusage.csv' in metrics
    markdown = provenance.markdown(board['rows'], 'users')
    assert 'retired' in markdown and 'USER_PREF/PREF_JSON' in markdown
    if passed:
        manifest['dead'] = []
        assert all(r['status'] == 'red' for r in object_board.build_board(manifest)['rows']
                   if r['name'] in retirement_users.DEAD)


def test_compact_markdown_links_numbers_and_preserves_unmeasured():
    metric = dict(url='https://example.com/code#L1-L2')
    rows = [dict(name='one', subject_area='users', local_duckdb='red',
                 row_count=dict(before=2, after=3), keyed_row_hash={'A': dict(difference=1)},
                 provenance=dict(metrics=dict(counts=metric, hashes=metric))),
            dict(name='retired', subject_area='users', local_duckdb='retire_verified',
                 row_count=None, keyed_row_hash=None, provenance=dict(metrics={}))]
    text = provenance.compact_markdown(rows)
    assert '| one | red | [2](https://example.com/code#L1-L2) | [3]' in text
    assert '| [1](https://example.com/code#L1-L2) |' in text
    assert '| retired | retire_verified | — | — | — |' in text
    assert '| one |' not in provenance.compact_markdown([])
