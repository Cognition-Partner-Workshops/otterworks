import csv
from decimal import Decimal
import gzip
import importlib.util
import re
from pathlib import Path

import pytest
import yaml

from load import load_seed
from seed_contract import ROOT, column_type, prepare_seed, seed_spec
from warehouse.seed.generate import generate


def test_additive_seed_contract():
    spec = importlib.util.spec_from_file_location('seed_renderer', ROOT / 'tools/render_seed.py')
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    merged, sql = renderer.render()
    assert yaml.safe_load((ROOT / 'landing_columns.yml').read_text()) == merged
    assert renderer.TARGET.read_text() == sql
    for area, tables in seed_spec().items():
        for table, columns in tables.items():
            assert columns.keys() <= merged[area][table].keys()
    assert merged['users']['APP_USER']['DISPLAY_NAME'] == 'VARCHAR(256)'
    assert 'DROP ' not in sql and 'TRUNCATE ' not in sql
    assert 'ALTER TABLE RAW_BILLING.CUSTOMER_ACCOUNT ALTER COLUMN ACCOUNT_NUMBER SET DATA TYPE VARCHAR(24)' in sql
    assert 'COMPAT.GL_ACCOUNT' in sql and 'COMPAT.INVOICE_HDR' in sql
    assert column_type('Q') == 'NUMBER(12,4)'
    with pytest.raises(ValueError, match='Unsupported seed type'):
        column_type('unknown')


def test_prepare_seed_balanced_and_lossless(tmp_path):
    source, output = tmp_path / 'source', tmp_path / 'output'
    counts = generate(20, 1110, source)
    # The shared seed holds prior-period Teradata history only (8 invoice + 3 credit lines at 20 rows).
    assert counts['GL_ACCOUNT'] == 10 and counts['GL_JOURNAL_LINE'] == 11
    prepared = prepare_seed(source, output, '20261109')
    assert len(prepared) == 42
    journals = {}
    contract = yaml.safe_load((ROOT / 'landing_columns.yml').read_text())
    for area, table, path, count in prepared:
        with gzip.open(path, 'rt', newline='') as stream:
            reader = csv.DictReader(stream, delimiter='|')
            assert set(reader.fieldnames) <= contract[area][table].keys()
            rows = list(reader)
        assert len(rows) == count
        if table == 'GL_JOURNAL_LINE':
            assert count == counts['INVOICE_HDR'] * 3 + counts['PAYMENT'] * 2 + counts['CREDIT_NOTE'] * 2
            for row in rows:
                journals.setdefault(row['JOURNAL_ID'], Decimal(0))
                journals[row['JOURNAL_ID']] += Decimal(row['DEBIT_AMOUNT']) - Decimal(row['CREDIT_AMOUNT'])
                assert row['CURRENCY_CD']
        else:
            assert count == counts[table]
        if table == 'STORAGE_USAGE_DAILY':
            assert len({row['STORAGE_USAGE_ID'] for row in rows}) < count
        if table == 'APP_USER':
            assert max(len(row['DISPLAY_NAME']) for row in rows) > 60
        for row in rows:
            for column, value in row.items():
                kind = contract[area][table][column]
                if kind.startswith(('CHAR(', 'VARCHAR(')):
                    assert len(value) <= int(kind.split('(')[1][:-1])
    assert journals and all(amount == 0 for amount in journals.values())


def test_prepare_seed_empty_and_error(tmp_path):
    with pytest.raises(FileNotFoundError, match='Missing seed landing file'):
        prepare_seed(tmp_path, tmp_path / 'out', '20261109')
    generate(1, 1110, tmp_path)
    path = tmp_path / 'billing/CUSTOMER_ACCOUNT/20261109.psv'
    path.write_text('bad|row\n')
    with pytest.raises(ValueError, match='expected 9 columns, got 2'):
        prepare_seed(tmp_path, tmp_path / 'out', '20261109')
    path.write_text('')
    (tmp_path / 'billing/GL_ACCOUNT/20261109.psv').write_text('')
    with pytest.raises(ValueError, match='missing posting account'):
        prepare_seed(tmp_path, tmp_path / 'out', '20261109')


class Cursor:
    description = [('status',), ('rows_loaded',), ('errors_seen',)]

    def __init__(self, rows=3, fail=False):
        self.rows, self.fail, self.commands = rows, fail, []

    def execute(self, command, params=None):
        self.commands.append(command)
        if self.fail and command.startswith('PUT'):
            raise RuntimeError('upload failed')

    def fetchall(self):
        return [('LOADED', self.rows, 0)]

    def fetchone(self):
        return (self.rows,)


def test_seed_copy_truncate_and_error(tmp_path, capsys):
    prepared = [('billing', 'INVOICE_HDR', tmp_path / '20261109.psv.gz', 3)]
    cur = Cursor()
    load_seed(cur, prepared, truncate=True)
    assert 'billing | INVOICE_HDR | 3 | 3' in capsys.readouterr().out
    assert cur.commands[1:3] == ['BEGIN', 'DELETE FROM RAW_BILLING.INVOICE_HDR']
    assert 'MATCH_BY_COLUMN_NAME=CASE_INSENSITIVE' in cur.commands[3]
    assert 'ON_ERROR=ABORT_STATEMENT' in cur.commands[3]
    assert 'FORCE=TRUE' in cur.commands[3]
    assert cur.commands[-1] == 'COMMIT'
    assert '/seed/' in cur.commands[0]
    cur = Cursor(fail=True)
    with pytest.raises(RuntimeError, match='upload failed'):
        load_seed(cur, prepared, truncate=True)
    assert not any(command in ('BEGIN', 'COMMIT') for command in cur.commands)
    with pytest.raises(RuntimeError, match='expected 3 rows'):
        load_seed(Cursor(rows=0), prepared, truncate=True)
    cur = Cursor()
    load_seed(cur, [], truncate=True)
    load_seed(cur, prepared, area='audit', truncate=True)
    assert cur.commands == []


def test_seed_copy_repeat_and_date_isolation(tmp_path, monkeypatch, capsys):
    class HistoryCursor(Cursor):
        def __init__(self):
            super().__init__()
            self.loaded = set()
            self.count = 0

        def execute(self, command, params=None):
            super().execute(command)
            if command.startswith('COPY'):
                stage, filename = re.search(r"FROM (\S+) FILES=\('([^']+)'\)", command).groups()
                assert stage.endswith('/' + filename[:8] + '/')
                key = stage + filename
                self.description = [('status',), ('rows_loaded',)]
                if key in self.loaded and 'FORCE=TRUE' not in command:
                    self.result = [('LOAD_SKIPPED', 0)]
                else:
                    self.loaded.add(key)
                    self.count += 3
                    self.result = [('LOADED', 3)]
            elif command.startswith('DELETE'):
                assert command == 'DELETE FROM IDENTIFIER(%s) WHERE _SRC_FILE=%s'
                self.count -= 3 if params[1] in {k.split('/', 1)[1] for k in self.loaded} else 0

        def fetchall(self):
            return self.result

        def fetchone(self):
            return (self.count,)

    cur = HistoryCursor()
    prepared = [('billing', 'INVOICE_HDR', tmp_path / '20261109.psv.gz', 3)]
    monkeypatch.setenv('SFX_RUN_ID', 'first')
    load_seed(cur, prepared)
    monkeypatch.setenv('SFX_RUN_ID', 'different-process')
    load_seed(cur, prepared)
    assert cur.count == 3
    assert 'billing | INVOICE_HDR | 3 | 3' in capsys.readouterr().out
    load_seed(cur, [('billing', 'INVOICE_HDR', tmp_path / '20261110.psv.gz', 3)])
    assert cur.count == 6
    copies = [sql for sql in cur.commands if sql.startswith('COPY')]
    assert copies[0] == copies[1]
    assert '/seed/billing/INVOICE_HDR/20261109/' in copies[0]
    assert "FILES=('20261109.psv.gz')" in copies[0]
    assert '20261109' not in copies[2]
    assert all('OVERWRITE=TRUE' in sql for sql in cur.commands if sql.startswith('PUT'))


@pytest.mark.parametrize('result', [[], [('Copy executed with 0 files processed.',)]])
def test_seed_copy_rejects_history_noop(tmp_path, result):
    cur = Cursor()
    cur.description = [('status',)]
    cur.fetchall = lambda: result
    with pytest.raises(RuntimeError):
        load_seed(cur, [('billing', 'INVOICE_HDR', tmp_path / '20261109.psv.gz', 3)])


def test_seed_copy_rejects_bad_filename_and_unexplained_zero(tmp_path):
    with pytest.raises(ValueError, match='Invalid prepared seed filename'):
        load_seed(Cursor(), [('billing', 'INVOICE_HDR', tmp_path / 'other.psv.gz', 3)])
    with pytest.raises(RuntimeError, match='expected 3 rows'):
        load_seed(Cursor(rows=0), [('billing', 'INVOICE_HDR', tmp_path / '20261109.psv.gz', 3)])
