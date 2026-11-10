from pathlib import Path
from types import SimpleNamespace

from bteq.parser import commands
from jobs import snowconvert


def test_missing_cli(capsys, monkeypatch):
    monkeypatch.setattr(snowconvert.shutil, 'which', lambda _: None)
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
        statements = list(commands(path.read_text()))
        assert len(statements) == 1
        assert statements[0].upper().startswith(('CREATE ', 'REPLACE '))
    assert '${BUSINESS_DATE}' in (tmp_path/'scripts/billing/13_period_close.bteq').read_text()


def test_conversion_command_log(tmp_path, monkeypatch):
    monkeypatch.setattr(snowconvert, 'ROOT', tmp_path)
    monkeypatch.setattr(snowconvert.shutil, 'which', lambda _: '/opt/scai')
    monkeypatch.setattr(snowconvert, 'prepare_input', lambda _: 1)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1] == 'init':
            Path(command[2]).mkdir()
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(snowconvert.subprocess, 'run', run)
    assert snowconvert.convert('/opt/scai', 'test') == 0
    assert calls[-1] == ['/opt/scai', 'code', 'convert', '--scripttargetlanguage', 'SnowScript']
    assert calls[1][1:4] == ['code', 'add', '-i']
    logs = list((tmp_path/'.snowconvert').glob('*/command.log'))
    assert len(logs) == 1 and logs[0].read_text().count('EXIT 0') == 4


def test_conversion_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(snowconvert, 'ROOT', tmp_path)
    monkeypatch.setattr(snowconvert.shutil, 'which', lambda _: '/opt/scai')
    monkeypatch.setattr(snowconvert, 'prepare_input', lambda _: 1)
    monkeypatch.setattr(snowconvert.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=7))
    assert snowconvert.convert('/opt/scai', 'test') == 7
    assert next((tmp_path/'.snowconvert').glob('*/command.log')).read_text().endswith('EXIT 7\n')
