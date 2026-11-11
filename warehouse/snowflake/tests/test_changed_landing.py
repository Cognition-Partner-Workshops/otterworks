from contextlib import nullcontext
from copy import deepcopy
import json
import re
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.parse import urlparse, unquote

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import load


class FileCursor:
    description = [('status',), ('rows_loaded',), ('errors_seen',)]

    def __init__(self, fail=False):
        self.staged, self.data, self.history = {}, {'unrelated.psv': ['keep']}, set()
        self.commands, self.fail = [], fail

    def execute(self, sql, params=None):
        self.commands.append(sql)
        if sql.startswith('PUT'):
            uri, stage = re.search(r"PUT '([^']+)' (@\S+)", sql).groups()
            path = Path(unquote(urlparse(uri).path))
            key = stage.split('/', 1)[1] + path.name
            if key not in self.staged or 'OVERWRITE=TRUE' in sql:
                self.staged[key] = path.read_text().splitlines()[1:]
        elif sql == 'BEGIN':
            self.original = deepcopy(self.data)
        elif sql == 'ROLLBACK':
            self.data = self.original
        elif sql.startswith('DELETE'):
            # The staged file name is a bind value, never part of the SQL text.
            assert sql == 'DELETE FROM IDENTIFIER(%s) WHERE _SRC_FILE=%s', sql
            key = params[1]
            self.data.pop(key, None)
        elif sql.startswith('COPY'):
            stage, name = re.search(r"FROM (@\S+) FILES=\('([^']+)'\)", sql).groups()
            self.copy(stage.split('/', 1)[1] + name, 'FORCE=TRUE' in sql)
        elif sql.startswith('CALL'):
            loaded = sum(self.copy(k, False) for k in self.staged)
            self.call_result = json.dumps([dict(table='INVOICE_HDR', rows_loaded=loaded)])

    def copy(self, key, force):
        if self.fail:
            raise RuntimeError('injected COPY failure')
        loaded = len(self.staged[key]) if force or key not in self.history else 0
        if force or key not in self.history:
            self.data.setdefault(key, []).extend(self.staged[key])
            self.history.add(key)
        self.result = [('LOADED' if loaded or force else 'LOAD_SKIPPED', loaded, 0)]
        return loaded

    def fetchall(self):
        return self.result

    def fetchone(self):
        if self.commands[-1].startswith('CALL'):
            return (self.call_result,)
        return (sum(map(len, self.data.values())),)


@pytest.mark.parametrize('source', ['fixtures', 'seed'])
def test_changed_landing_replaces_only_its_file(tmp_path, monkeypatch, source):
    directory = tmp_path / 'billing/INVOICE_HDR'
    directory.mkdir(parents=True)
    path = directory / '20261109.psv'
    cursor = FileCursor()
    monkeypatch.setattr(load, 'SPEC', {'billing': {'INVOICE_HDR': {'ID': 'BIGINT'}}})
    monkeypatch.setattr(load, 'FIXTURE_SPEC', load.SPEC)
    conn = SimpleNamespace(cursor=lambda: nullcontext(cursor))
    monkeypatch.setattr(load, 'connect', lambda *args: nullcontext(conn))
    monkeypatch.setattr('sys.argv', ['load.py', '--area', 'billing', '--landing-dir', str(tmp_path)])
    for values in (['1', '2'], ['1', '2'], ['3'], ['3'], []):
        path.write_text('ID\n' + ''.join(v + '\n' for v in values))
        if source == 'fixtures':
            load.main()
        else:
            load.load_seed(cursor, [('billing', 'INVOICE_HDR', path, len(values))])
        assert sorted(v for rows in cursor.data.values() for v in rows) == sorted(['keep', *values])
    assert all('OVERWRITE=TRUE' in sql for sql in cursor.commands if sql.startswith('PUT'))


def test_file_reload_failure_rolls_back_deleted_rows(tmp_path):
    path = tmp_path / '20261109.psv'
    path.write_text('ID\n3\n')
    cursor = FileCursor(fail=True)
    cursor.data['seed/billing/INVOICE_HDR/20261109/20261109.psv'] = ['original']
    before = deepcopy(cursor.data)
    with pytest.raises(RuntimeError, match='injected COPY failure'):
        load.load_seed(cursor, [('billing', 'INVOICE_HDR', path, 1)])
    assert cursor.data == before
    assert cursor.commands[-1] == 'ROLLBACK'
