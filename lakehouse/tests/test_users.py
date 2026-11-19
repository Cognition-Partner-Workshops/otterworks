import gzip
import json
from datetime import date

import pytest
import yaml

from lakehouse.coverage.checker import entries, parity_result
from lakehouse.coverage.inventory import discover
from lakehouse.orchestration.graph import load, ordered
from lakehouse.orchestration.runner import command
from lakehouse.parity.spec import discover as discover_specs
from lakehouse.runtime.layout import ROOT
from lakehouse.runtime.users_activity_report import publish, top_user_records
from lakehouse.runtime.users_exports import atomic_output, write_team_counts
from lakehouse.runtime.users_informatica import events, store
from lakehouse.runtime.users_spark import components, preferences, read_inputs
from lakehouse.tests.test_lakehouse import spark  # noqa: F401


def test_users_graph_and_ownership(tmp_path, monkeypatch):
    monkeypatch.setenv('NS', 'users-test')
    inventory = discover()
    owned = yaml.safe_load((ROOT / 'coverage/domains/users.yaml').read_text())['legacy_objects']
    specs = discover_specs()
    coverage = entries(ROOT / 'coverage/coverage.yaml', 'objects')
    graph = load()
    daily = graph['lakehouse_daily']
    warehouse = {n['id']: n for n in daily['nodes']}
    assert warehouse['export_users_team_counts']['depends_on'] == ['dbt_users']
    assert warehouse['infa_users_role_grant']['depends_on'] == ['infa_users_app']
    assert warehouse['infa_users_login_team']['depends_on'] == ['infa_users_app']
    assert set(warehouse['parity_users_informatica']['depends_on']) == {'infa_users_role_grant', 'infa_users_login_team'}
    assert len(set(owned)) == len(owned)
    assert set(owned) <= inventory.keys()
    assert {key for key in inventory if ':SFX_USERS.' in key or
            '/scripts/users/' in key or '/fastload/users_' in key} <= set(owned)
    assert not any('/daily_chain#' in key or key.startswith('batch_runner:') for key in owned)
    scheduled = set()
    for key in ('lakehouse_users_spark', 'lakehouse_users_activity'):
        dag = graph[key]
        assert dag['paused'] and dag['schedule'] == '@daily'
        first, parity = ordered(dag['nodes'])
        assert parity['depends_on'] == [first['id']]
        assert parity['retries'] == first['retries'] == 1
        assert all(v in command(parity, tmp_path, '20261109') for v in parity['specs'])
        scheduled.update(item for item in first['legacy_objects'] if item.startswith(('cron_entry:', 'spark_submit:')))
    assert scheduled == {item for item in owned if item.startswith(('cron_entry:', 'spark_submit:'))}
    for key in owned:
        entry = coverage[key]
        assert entry['status'] in ('converted', 'replaced_by_platform')
        for spec in entry['parity']:
            assert parity_result(spec, specs, ROOT / 'evidence') == 'PASS'


def test_report_publication_is_idempotent(tmp_path):
    day = '2026-11-09'
    report = {'report_date': day, 'user_summaries': [{'user_id': 'demo'}]}
    latest = tmp_path / 'latest/activity_report.json'
    publish(tmp_path, report)
    data = latest.read_bytes()
    publish(tmp_path, report)
    assert latest.read_bytes() == data
    publish(tmp_path, {'report_date': '2026-11-08', 'user_summaries': []})
    assert latest.read_bytes() == data
    output = tmp_path / day / 'user_summaries.jsonl'
    assert json.loads(output.read_text()) == {'user_id': 'demo'}
    publish(tmp_path, {'report_date': day, 'user_summaries': []})
    assert not output.exists()
    counts = tmp_path / 'counts.psv'
    write_team_counts(counts, [(1, 'Name|Second', 2)])
    assert counts.read_text() == '1|"Name|Second"|2\n'
    with pytest.raises(RuntimeError), atomic_output(counts) as handle:
        handle.write('incomplete')
        raise RuntimeError('interrupted')
    assert counts.read_text() == '1|"Name|Second"|2\n'


def test_report_corrupt_optional_input_is_not_empty(tmp_path):
    source = tmp_path / 'top_users.jsonl.gz'
    with gzip.open(source, 'wt', encoding='utf-8') as handle:
        handle.write('{"user_id":"demo","total":2}\nnot json\n')
    rows = top_user_records((0, source))
    assert next(rows) == ('demo', 2, {}, 0, 0)
    with pytest.raises(json.JSONDecodeError):
        next(rows)


def test_users_spark_edges(spark, tmp_path):
    assert preferences('{"notifications":{"email":false},"theme":"dark"}') == (
        'dark', "{'email': False}", '')
    assert preferences('{broken') is None
    assert preferences(None) == ('', '', '')
    with pytest.raises(FileNotFoundError, match='Missing Spark landing'):
        read_inputs(spark, tmp_path)
    teams = spark.createDataFrame([(1,), (2,), (4,)], 'team_id LONG')
    members = spark.createDataFrame([(1, 7), (2, 7), (2, 8), (3, 8), (3, 8)],
                                    'team_id LONG, user_id LONG')
    assert sorted(tuple(row) for row in components(teams, members).collect()) == [
        (1, 1), (2, 1), (3, 1), (4, 4)]
    empty = spark.createDataFrame([], teams.schema)
    assert components(empty, spark.createDataFrame([], members.schema)).count() == 0
    with pytest.raises(ValueError, match='null team/user'):
        components(teams, spark.createDataFrame([(1, None)], members.schema))


def test_informatica_delta_contract(spark, monkeypatch):
    from lakehouse.runtime import users_informatica

    schema = 'id LONG, label STRING'
    store(spark, spark.createDataFrame([(1, 'old'), (2, 'retained')], schema), 'merge_test', 'id')
    store(spark, spark.createDataFrame([(1, 'new'), (3, 'inserted')], schema), 'merge_test', 'id', merge=True)
    expected = [(1, 'new'), (2, 'retained'), (3, 'inserted')]
    assert [tuple(row) for row in spark.table('silver_users.merge_test').orderBy('id').collect()] == expected
    for rows in ([(4, 'first'), (4, 'duplicate')], [(None, 'missing')]):
        with pytest.raises(ValueError, match='missing or duplicate'):
            store(spark, spark.createDataFrame(rows, schema), 'merge_test', 'id', merge=True)
    assert [tuple(row) for row in spark.table('silver_users.merge_test').orderBy('id').collect()] == expected
    logins = spark.createDataFrame([
        (i, 101, '2026-11-09 12:00:00', code, 'WEB')
        for i, code in enumerate(('success', 'failed', 'locked', 'mfa_failed', 'unknown', None), 1)],
        'login_id LONG, user_id LONG, login_ts STRING, result_cd STRING, client_type STRING')
    members = spark.createDataFrame([], 'team_member_id LONG, team_id LONG, user_id LONG, role_cd STRING, joined_dt STRING')
    monkeypatch.setattr(users_informatica, 'source',
                        lambda _spark, name, day: logins if name == 'login_event' else members)
    events(spark, date(2026, 11, 9))
    assert {row.result_cd for row in spark.table('silver_users.infa_login_event').collect()} == {
        'SUCCESS', 'FAILED', 'LOCKED', 'MFA_FAILED'}
    assert spark.table('silver_users.infa_team_member').count() == 0
