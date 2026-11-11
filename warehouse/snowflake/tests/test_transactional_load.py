from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

import load


class TransactionCursor:
    description = [('status',), ('rows_loaded',), ('errors_seen',)]

    def __init__(self, fail_at=None, result=None, rows=3):
        self.commands, self.copies = [], 0
        self.fail_at, self.result, self.rows = fail_at, result, rows
        self.data = {f'RAW_BILLING.{table}': ['original'] for table in load.SPEC['billing']}
        self.pending = None

    def execute(self, sql):
        self.commands.append(sql)
        if sql == 'BEGIN':
            self.pending = deepcopy(self.data)
        elif sql == 'ROLLBACK':
            self.pending = None
        elif sql == 'COMMIT':
            self.data, self.pending = self.pending, None
        elif sql.startswith('DELETE FROM'):
            self.pending[sql.split()[-1]] = []
        elif sql.startswith('COPY'):
            self.copies += 1
            if self.copies == self.fail_at:
                raise RuntimeError('injected COPY failure')
            self.pending[sql.split()[2]].extend(['replacement'] * self.rows)
        elif sql.startswith('SELECT COUNT'):
            self.count = len(self.pending[sql.split()[-1]])

    def fetchall(self):
        if self.result is not None and self.copies == 2:
            return self.result
        return [('LOADED', self.rows, 0)]

    def fetchone(self):
        return (self.count,)


def prepared(tmp_path):
    return [('billing', table, tmp_path / '20261109.psv.gz', 3)
            for table in ('INVOICE_HDR', 'INVOICE_LINE', 'GL_JOURNAL_LINE')]


@pytest.mark.parametrize('fail_at', [2, 3])
@pytest.mark.parametrize('prefix', ['seed', 'teradata-before'])
def test_replace_rolls_back_all_tables_on_later_copy(tmp_path, fail_at, prefix):
    cursor = TransactionCursor(fail_at=fail_at)
    before = deepcopy(cursor.data)
    with pytest.raises(RuntimeError, match='injected COPY failure'):
        load.load_seed(cursor, prepared(tmp_path), truncate=True, stage_prefix=prefix)
    assert cursor.data == before
    assert cursor.commands[-1] == 'ROLLBACK'
    assert 'COMMIT' not in cursor.commands
    assert not any('TRUNCATE' in sql for sql in cursor.commands)
    begin = cursor.commands.index('BEGIN')
    assert all(sql.startswith('PUT') for sql in cursor.commands[:begin])
    assert not any(sql.startswith(('PUT', 'CREATE', 'ALTER', 'TRUNCATE')) for sql in cursor.commands[begin:])


@pytest.mark.parametrize('result', [
    [('PARTIALLY_LOADED', 3, 0)], [('LOAD_FAILED', 3, 0)],
    [('LOAD_SKIPPED', 0, 0)], [('LOADED', 3, 1)], [],
])
def test_replace_rolls_back_unsuccessful_copy_results(tmp_path, result):
    cursor = TransactionCursor(result=result)
    before = deepcopy(cursor.data)
    with pytest.raises(RuntimeError):
        load.load_seed(cursor, prepared(tmp_path), truncate=True)
    assert cursor.data == before
    assert cursor.commands[-1] == 'ROLLBACK'
    assert 'COMMIT' not in cursor.commands


def test_replace_validates_complete_manifest_before_upload(tmp_path):
    cursor = TransactionCursor()
    invalid = prepared(tmp_path)
    invalid[-1] = ('billing', 'GL_JOURNAL_LINE', tmp_path / 'bad.psv.gz', 3)
    with pytest.raises(ValueError, match='filename'):
        load.load_seed(cursor, invalid, truncate=True)
    assert cursor.commands == []
    with pytest.raises(ValueError, match='Invalid COPY plan'):
        load.copy_tables(cursor, [('MART.A', '@LANDING.LANDING_STAGE/test/', 'bad.psv', 1)], replace=True)
    assert cursor.commands == []
    assert load.copy_tables(cursor, [], replace=True) == []
    assert cursor.commands == []


def test_replace_success_forces_every_copy_and_commits_once(tmp_path):
    cursor = TransactionCursor()
    load.load_seed(cursor, prepared(tmp_path), truncate=True)
    assert cursor.commands.count('BEGIN') == cursor.commands.count('COMMIT') == 1
    assert 'ROLLBACK' not in cursor.commands
    copies = [sql for sql in cursor.commands if sql.startswith('COPY')]
    assert len(copies) == 3
    assert all('FORCE=TRUE' in sql and "FILES=('20261109.psv.gz')" in sql for sql in copies)
    assert all(cursor.data['RAW_BILLING.' + t] == ['replacement'] * 3
               for t in ('INVOICE_HDR', 'INVOICE_LINE', 'GL_JOURNAL_LINE'))


@pytest.mark.parametrize('fail_at', [None, 2])
def test_fixture_replace_uses_same_transaction_helper(monkeypatch, fail_at):
    cursor = TransactionCursor(fail_at=fail_at, rows=20)
    before = deepcopy(cursor.data)
    conn = SimpleNamespace(cursor=lambda: nullcontext(cursor))
    monkeypatch.setattr(load, 'connect', lambda *a, **kw: nullcontext(conn))
    monkeypatch.setattr('sys.argv', ['load.py', '--area', 'billing', '--truncate'])
    if fail_at:
        with pytest.raises(RuntimeError, match='injected COPY failure'):
            load.main()
        assert cursor.data == before
        assert cursor.commands[-1] == 'ROLLBACK'
        assert 'COMMIT' not in cursor.commands
    else:
        load.main()
        assert cursor.copies == len(load.FIXTURE_SPEC['billing'])
        assert cursor.commands.count('COMMIT') == 1
    assert not any(sql.startswith(('TRUNCATE', 'CALL')) for sql in cursor.commands)


def test_fixture_multiple_dates_delete_once_and_copy_explicit_files(tmp_path, monkeypatch):
    monkeypatch.setattr(load, 'FIXTURE_SPEC', {'billing': {'INVOICE_HDR': {'INVOICE_ID': 'BIGINT'}}})
    directory = tmp_path / 'billing/INVOICE_HDR'
    directory.mkdir(parents=True)
    for date in ('20261109', '20261110'):
        (directory / (date + '.psv')).write_text('INVOICE_ID\n1\n2\n3\n')
    entries = load.prepare_fixtures(tmp_path, ['billing'])
    cursor = TransactionCursor()
    load.load_seed(cursor, entries, truncate=True, stage_prefix='fixtures')
    assert cursor.commands.count('DELETE FROM RAW_BILLING.INVOICE_HDR') == 1
    assert cursor.data['RAW_BILLING.INVOICE_HDR'] == ['replacement'] * 6
    assert len([sql for sql in cursor.commands if sql.startswith('COPY') and "FILES=('20261109.psv')" in sql]) == 1
    assert len([sql for sql in cursor.commands if sql.startswith('COPY') and "FILES=('20261110.psv')" in sql]) == 1
    assert len(load.prepare_fixtures(tmp_path, ['billing'], '20261109')) == 1
    with pytest.raises(FileNotFoundError, match='No landing files'):
        load.prepare_fixtures(tmp_path, ['billing'], '20261111')
    (directory / '20261110.psv').write_text('wrong\n1\n')
    with pytest.raises(ValueError, match='header'):
        load.prepare_fixtures(tmp_path, ['billing'])
