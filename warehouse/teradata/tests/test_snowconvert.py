from types import SimpleNamespace

import pytest

from jobs import snowconvert


def test_missing_cli(capsys, monkeypatch):
    monkeypatch.setattr(snowconvert.shutil, 'which', lambda _: None)
    monkeypatch.setattr(snowconvert.subprocess, 'run', lambda *args, **kwargs: pytest.fail('configuration ran without scai'))
    assert snowconvert.convert('/missing/scai', 'test') == 2
    message = capsys.readouterr().err
    assert 'not found' in message and 'https://docs.snowflake.com/' in message and 'SCAI=/path/to/scai' in message


def test_conversion_staging(tmp_path):
    count = snowconvert.prepare_input(tmp_path)
    files = list(tmp_path.rglob('*.*'))
    assert len(files) == count
    assert len(list(tmp_path.rglob('*.bteq'))) == 26
    assert len(list((tmp_path/'procedures').glob('*.sql'))) == 4
    for path in tmp_path.rglob('*.sql'):
        assert path.read_bytes() == (snowconvert.ROOT/path.relative_to(tmp_path)).read_bytes()
        assert '<sc-' in path.read_text()
    assert '${BUSINESS_DATE}' in (tmp_path/'scripts/billing/13_period_close.bteq').read_text()


def test_conversion_command_log(tmp_path, monkeypatch):
    monkeypatch.setenv('SNOWFLAKE_PRIVATE_KEY', 'test-only key material')
    monkeypatch.setattr(snowconvert, 'ROOT', tmp_path)
    monkeypatch.setattr(snowconvert.shutil, 'which', lambda _: '/opt/scai')
    monkeypatch.setattr(snowconvert, 'prepare_input', lambda _: 1)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == '/opt/scai':
            assert kwargs['env']['SNOWFLAKE_CONNECTION'] == 'sfx_d1110'
            assert 'SNOWFLAKE_PRIVATE_KEY' not in kwargs['env']
        if command[1] == 'init':
            (kwargs['cwd']/command[2]).mkdir()
        if command[1:3] == ['code', 'convert']:
            (kwargs['cwd']/'snowflake').mkdir()
            (kwargs['cwd']/'snowflake/output.sql').write_text('SELECT 1;')
            reports = kwargs['cwd']/'.scai/reports/SnowConvert'
            reports.mkdir(parents=True)
            (reports/'Issues.csv').write_text('Code\n')
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(snowconvert.subprocess, 'run', run)
    assert snowconvert.convert('/opt/scai', 'test') == 0
    assert calls[-1] == ['/opt/scai', 'code', 'convert', '--show-ewis']
    assert calls[1][1:] == ['init', 'project', '-n', 'sfx-d1110-teradata-test', '-l', 'Teradata', '-c', 'sfx_d1110']
    assert calls[0][1].endswith('/bin/snowflake_connection.py')
    assert calls[1][-2:] == ['-c', 'sfx_d1110']
    assert calls[2][1:4] == ['code', 'add', '-i']
    logs = list((tmp_path/'.snowconvert').glob('*/command.log'))
    assert len(logs) == 1 and logs[0].read_text().count('EXIT 0') == 3
    assert (logs[0].parent/'raw-output/Reports/SnowConvert/Issues.csv').is_file()
    assert (logs[0].parent/'raw-output/output.sql').is_file()


def test_conversion_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(snowconvert, 'ROOT', tmp_path)
    monkeypatch.setattr(snowconvert.shutil, 'which', lambda _: '/opt/scai')
    monkeypatch.setattr(snowconvert, 'prepare_input', lambda _: 1)
    monkeypatch.setattr(snowconvert.subprocess, 'run', lambda command, **kwargs: SimpleNamespace(returncode=7 if command[0]=='/opt/scai' else 0))
    assert snowconvert.convert('/opt/scai', 'test') == 7
    assert next((tmp_path/'.snowconvert').glob('*/command.log')).read_text().endswith('EXIT 7\n')


def test_configuration_failure_stops_conversion(tmp_path, monkeypatch):
    monkeypatch.setattr(snowconvert, 'ROOT', tmp_path)
    monkeypatch.setattr(snowconvert.shutil, 'which', lambda _: '/opt/scai')
    monkeypatch.setattr(snowconvert.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=2))
    assert snowconvert.convert('/opt/scai', 'test') == 2
    assert not (tmp_path/'.snowconvert').exists()
