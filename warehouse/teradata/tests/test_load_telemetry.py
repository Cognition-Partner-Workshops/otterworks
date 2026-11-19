import json
from unittest.mock import Mock

import pytest

from bteq import load


@pytest.mark.parametrize('count', [0, 3])
def test_loader_events(tmp_path, monkeypatch, count):
    log = tmp_path / 'events.jsonl'
    monkeypatch.setenv('SFX_LOG_PATH', str(log))
    controls = tmp_path / 'controls'
    controls.mkdir()
    area = controls / 'billing'
    area.mkdir()
    (area / 'table.fl').touch()
    monkeypatch.setattr(load, 'parse_control', Mock(return_value=Mock(target='table')))
    monkeypatch.setattr(load, 'load_control', Mock(return_value=count))
    assert load.load_all(None, tmp_path, root=controls) == {'table': count}
    assert [json.loads(line)['event'] for line in log.read_text().splitlines()] == ['load_started', 'load_success']


def test_loader_error_event(tmp_path, monkeypatch):
    log = tmp_path / 'events.jsonl'
    monkeypatch.setenv('SFX_LOG_PATH', str(log))
    area = tmp_path / 'billing'
    area.mkdir()
    (area / 'bad.fl').touch()
    with pytest.raises(ValueError):
        load.load_all(None, tmp_path, root=tmp_path)
    assert json.loads(log.read_text().splitlines()[-1])['event'] == 'load_failure'
