import json
from pathlib import Path
import sys
import subprocess
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import reads
import board
import decommission


def td(account='service', **kw):
    return dict(username=account, appid='', clientid='', starttime='2026-11-09T12:00:00Z',
                statementtype='SELECT', errorcode=0, **kw)


CONSUMERS = [dict(name='reader', team='team', teradata_service_account='service', workflow='.github/workflows/consumer-reader.yml')]


def summary(rows=(), sf=()):
    return reads.summarize(rows, sf, CONSUMERS, '2026-11-09', '2026-11-10')


def test_counts_aliases_bounds_errors_and_empty():
    rows = [td(), td('unregistered'), td('svc_etl_load'), td('svc_fastload')]
    alias = td('alias'); alias['appid'] = 'JupyterLab/python'
    assert reads.classify(alias, CONSUMERS) == 'finance-notebook'
    failed = td(); failed['errorcode'] = 3807
    boundary = td(); boundary['starttime'] = '2026-11-10'
    result = summary(rows + [failed, boundary])
    assert result['reader']['teradata'] == 1
    assert result['reader']['baseline'] == 1
    assert result['unmanaged']['teradata'] == 1
    assert result['etl (out of scope)']['teradata'] == 2
    assert decommission.remaining(result) == 2
    assert decommission.remaining(summary()) == 0
    assert summary()['reader']['days'] == {}
    with pytest.raises(ValueError):
        reads.timestamp('invalid')


def test_snowflake_dedup_tags_and_failures():
    row = dict(query_id='1', start_time='2026-11-09', query_tag=json.dumps(dict(run='sfx-d1110', act='consumers', consumer='reader')),
               query_type='SELECT', execution_status='SUCCESS')
    bad = [{**row, 'query_id': str(i+2), 'query_tag': tag} for i, tag in enumerate(['invalid', '[]', '{}', '{"run":"sfx-d1110","act":"exit"}'])]
    assert summary([], [row, row] + bad)['reader']['snowflake'] == 1
    assert summary([], [{**row, 'execution_status': 'FAIL'}])['reader']['snowflake'] == 0


def test_parity_tooling_is_visible_but_does_not_block():
    data = summary([td('svc_exit_parity'), td('svc_etl_load')])
    parity = data['parity tooling (out of scope)']
    assert parity['baseline'] == parity['teradata'] == 1
    assert parity['accounts'] == {'svc_exit_parity': 1}
    assert parity['days']['2026-11-09']['teradata'] == 1
    assert decommission.remaining(data) == 0
    assert 'parity tooling (out of scope) | 1 | 1 | 0' in reads.render(data)
    records = board.rows(data, CONSUMERS, [])
    assert records[-1] == ['parity tooling (out of scope)', '—', 'svc_exit_parity', 1, 1, 0, '—', '—', 'out of scope']
    assert 'parity tooling (out of scope)' in board.document(records)
    failed = td('svc_exit_parity')
    failed['errorcode'] = 3807
    assert summary([failed])['parity tooling (out of scope)']['teradata'] == 0
    assert summary()['parity tooling (out of scope)']['teradata'] == 0


def test_unknown_and_other_unmanaged_accounts_block():
    data = summary([td('unknown'), td('unregistered'), td('svc_exit_parity')])
    assert data['unmanaged']['accounts'] == {'unknown': 1, 'unregistered': 1}
    assert data['unmanaged']['teradata'] == 2
    assert decommission.remaining(data) == 2


def pr(**kw):
    return dict(number=1, state='open', merged_at=None, base={'ref': 'demo-snowflake-dw-exit'},
                head={'ref': 'devin/sfx-d1110-consumer-reader', 'sha': 'abc'}, html_url='https://example.invalid/pr', **kw)


def test_board_workflow_sha_and_status():
    run = dict(head_sha='abc', path=CONSUMERS[0]['workflow'], event='pull_request', status='completed', conclusion='success')
    data = summary()
    assert board.rows(data, CONSUMERS, [])[0][-1] == 'Teradata'
    p = pr(workflow_runs=[run])
    assert board.rows(data, CONSUMERS, [p])[0][-1] == 'Teradata → Snowflake'
    p['workflow_runs'] = [{**run, 'head_sha': 'old'}]
    assert board.rows(data, CONSUMERS, [p])[0][-1] == 'Teradata'
    p['merged_at'] = '2026-11-09'
    assert board.rows(data, CONSUMERS, [p])[0][-1] == 'Snowflake'
    records = board.rows(data, CONSUMERS, [])
    assert 'unmanaged — needs owner' in board.markdown(records)
    assert '<script>' not in board.document([['<script>']])
    assert '&lt;script&gt;' in board.document([['<script>']])


def test_csv_baseline():
    data = reads.summarize(reads.teradata(reads.ROOT / 'warehouse/teradata/dbql/qrylog.csv'), [], reads.registry(), '2026-10-11', '2026-11-10')
    assert len(data) == 11
    assert data['parity tooling (out of scope)']['baseline'] == 0
    assert all(r['baseline'] == r['teradata'] and r['baseline'] > 0
               for name, r in data.items() if name != 'parity tooling (out of scope)')


def test_offline_cli(tmp_path):
    sf = tmp_path / 'sf.json'
    sf.write_text('[]')
    prs = tmp_path / 'prs.json'
    prs.write_text('[]')
    common = ['--since', '2026-11-10', '--until', '2026-11-11', '--csv',
              str(reads.ROOT / 'warehouse/teradata/dbql/qrylog.csv'), '--snowflake-json', str(sf)]
    def run(script, extra=()):
        return subprocess.run([sys.executable, str(Path(__file__).parent / script), *common, *extra], capture_output=True, text=True)
    result = run('reads.py', ['--json'])
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['report-service']['baseline'] > 0
    result = run('decommission.py')
    assert result.returncode == 0 and 'CLEAR' in result.stdout and 'unmanaged:' in result.stdout
    result = run('board.py', ['--prs-json', str(prs), '--html', str(tmp_path / 'board.html')])
    assert result.returncode == 0, result.stderr
    assert result.stdout.count('| Teradata |') == 8
    assert '<table>' in (tmp_path / 'board.html').read_text()
    sf.write_text('not json')
    assert run('reads.py').returncode != 0
    assert run('board.py', ['--prs-json', str(prs), '--html', str(tmp_path / 'error.html')]).returncode != 0
    assert run('decommission.py').returncode != 0


def test_nonzero_gate_cli(tmp_path):
    sf = tmp_path / 'sf.json'
    sf.write_text('[]')
    result = subprocess.run([sys.executable, str(Path(__file__).parent / 'decommission.py'),
                             '--since', '2026-10-11', '--until', '2026-11-10',
                             '--csv', str(reads.ROOT / 'warehouse/teradata/dbql/qrylog.csv'),
                             '--snowflake-json', str(sf)], capture_output=True, text=True)
    assert result.returncode == 1 and 'BLOCKED' in result.stdout


def test_current_registry_accounts_are_authoritative():
    consumers = reads.registry()
    for consumer in consumers:
        row = td(consumer['teradata_service_account'])
        data = reads.summarize([row], [], consumers, '2026-11-09', '2026-11-10')
        assert data[consumer['name']]['teradata'] == 1
        assert data['unmanaged']['teradata'] == 0


@pytest.mark.parametrize('size', [0, 1, 10000])
def test_recent_history_checks_unfiltered_capacity(monkeypatch, size):
    import datetime as dt
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    now = dt.datetime.now(dt.timezone.utc)
    since, until = now - dt.timedelta(hours=1), now
    outside = now - dt.timedelta(hours=2)
    batch = [(str(i), outside, '{}', 'SELECT', 'SUCCESS') for i in range(size)]
    cursor = MagicMock()
    cursor.fetchall.side_effect = [[], batch]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connect = MagicMock()
    connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(snowflake.connector, 'connect', connect)
    monkeypatch.setattr(serialization, 'load_pem_private_key', MagicMock())
    for name in ['ACCOUNT', 'USER', 'ROLE', 'PRIVATE_KEY']:
        monkeypatch.setenv('SNOWFLAKE_' + name, 'offline')

    if size == 10000:
        with pytest.raises(RuntimeError, match='10000'):
            reads.snowflake(since, until)
    else:
        rows = reads.snowflake(since, until)
        assert len(rows) == size
        assert summary([], rows)['reader']['snowflake'] == 0
    query, params = cursor.execute.call_args_list[1].args
    assert 'INFORMATION_SCHEMA.QUERY_HISTORY' in query
    assert ' WHERE ' not in query
    assert len(params) == 2
