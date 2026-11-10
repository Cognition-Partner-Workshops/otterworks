import json
from pathlib import Path
import sys
import subprocess

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
    assert len(data) == 10
    assert all(r['baseline'] == r['teradata'] and r['baseline'] > 0 for r in data.values())


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
