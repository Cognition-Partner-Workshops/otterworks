from types import SimpleNamespace

import pytest
from prometheus_client import generate_latest

from odl_sync import metrics, sync
from odl_sync.extract import Extract, ExtractError


def test_failure_skips_all_writes_and_still_extracts_others(monkeypatch):
    seen = []
    def fail(settings):
        raise ExtractError('connect')
    def succeed(settings):
        seen.append(True)
        return Extract('postgres')
    monkeypatch.setattr(sync.db2, 'extract', fail)
    monkeypatch.setattr(sync.oracle, 'extract', succeed)
    monkeypatch.setattr(sync.postgres, 'extract', succeed)
    def no_load(*args):
        pytest.fail('must not write an incomplete projection')
    monkeypatch.setattr(sync, 'load', no_load)
    assert sync.run(None) == {'status': 'skipped', 'failures': {'db2': 'connect'}}
    assert len(seen) == 2


def test_write_failure_does_not_advance_checkpoint(monkeypatch):
    before = dict(metrics.checkpoints)
    for source in metrics.SOURCES:
        monkeypatch.setattr(getattr(sync, source), 'extract', lambda settings, s=source: Extract(s, checkpoint=100))
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def __getitem__(self, name):
            return None
    monkeypatch.setattr(sync, 'MongoClient', Client)
    def fail(*args):
        raise RuntimeError('write failed')
    monkeypatch.setattr(sync, 'load', fail)
    assert sync.run(SimpleNamespace(mongo={}, mongo_database='odl'))['status'] == 'failed'
    assert metrics.checkpoints == before


def test_metrics_contract():
    output = generate_latest().decode()
    for source in metrics.SOURCES:
        for reason in metrics.REASONS:
            assert f'odl_sync_errors_total{{reason="{reason}",source="{source}"}}' in output
    assert 'odl_sync_lag_seconds{' not in output
    metrics.success('db2', 100, 2)
    assert 'odl_sync_lag_seconds{source="db2"}' in generate_latest().decode()
    assert metrics.read_duration._upper_bounds == [.005, .01, .025, .05, .1, .25, .5, 1., 2.5, 5., 10., float('inf')]
