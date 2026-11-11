from datetime import date, datetime, timezone
from decimal import Decimal
import pytest

from parity.compare import compare, normal, status
from parity.commands import identifier, relation, mark_sql
from parity.harness import control_table
from parity.inventory import target_relation


def test_normalisation():
    assert normal(Decimal('1.00')) == normal(1)
    assert normal(Decimal('123456789012345678901234567890.10'))[1] == '123456789012345678901234567890.1'
    assert normal(' a ') != normal('a')
    assert normal('\ta') != normal('a')
    assert normal(None) != normal('null')
    assert normal(date(2026, 11, 9)) == ['date', '2026-11-09']
    assert normal(datetime(2026, 11, 9, tzinfo=timezone.utc))[1].startswith('2026-11-09T')


def test_keyed_diff_and_multiset():
    b = [dict(ID=1, V='a'), dict(ID=2, V='b')]
    a = [dict(ID=1, V='a'), dict(ID=3, V='c')]
    r = compare(b, a, ['ID', 'V'], ['ID'], 1)
    assert (r['matched_keys'], r['missing_keys'], r['extra_keys']) == (1, 1, 1)
    assert len(r['sampled_diffs']) == 1
    changed = compare(b, [dict(ID=1, V='z'), b[1]], ['ID', 'V'], ['ID'])
    assert changed['changed_keys'] == 1
    assert 'V' in changed['sampled_diffs'][0]['columns']
    assert not compare(b, b + [b[0]], ['ID', 'V'], [])['keyed_hash_match']
    assert compare([], [], ['ID'], [])['keyed_hash_match']
    assert compare(b, list(reversed(b)), ['ID', 'V'], [])['keyed_hash_match']


def test_decisions():
    assert status({}) == 'PENDING'
    assert status({}, 'Needs review.') == 'AMBER'
    r = dict(rowcount_match=True, keyed_hash_match=True, rerun_duplicates=0,
             run1_rows=2, run2_rows=2, after_rows=2)
    assert status(r) == 'VERIFIED'
    assert status(dict(r, rerun_duplicates=1)) == 'PENDING'
    with pytest.raises(ValueError):
        status({}, 'two\nlines')


@pytest.mark.parametrize('value', [' review', 'review ', 're view'])
def test_varchar_whitespace_is_significant(value):
    result = compare([dict(ID=1, V=value)], [dict(ID=1, V='review')], ['ID', 'V'], ['ID'])
    assert not result['keyed_hash_match']
    assert result['sampled_diffs'][0]['columns']['V']['before'] == [['string', value]]


def test_char_padding_uses_source_types_for_values_and_keys():
    types = {'ID': 'character', 'V': 'character varying'}
    before = [dict(ID='key  ', V='review')]
    after = [dict(ID='key', V='review')]
    assert compare(before, after, ['ID', 'V'], ['ID'], types=types)['keyed_hash_match']
    assert compare(before, after, ['ID', 'V'], [], types=types)['keyed_hash_match']
    after[0]['V'] = 'review '
    assert not compare(before, after, ['ID', 'V'], ['ID'], types=types)['keyed_hash_match']
    after[0] = dict(ID=' key', V='review')
    assert not compare(before, after, ['ID', 'V'], ['ID'], types=types)['keyed_hash_match']


def test_parity_uses_captured_source_column_types(tmp_path, monkeypatch):
    import json
    from contextlib import nullcontext
    from types import SimpleNamespace
    from parity import commands

    row = dict(mapping='probe', before_table='PC_BEFORE.PROBE', after_table='PC_AUDIT.PROBE',
               key_columns=['ID'], exclude_columns=[])
    (tmp_path / 'probe.json').write_text(json.dumps({'source_types': {'ID': 'character'}}))
    monkeypatch.setattr(commands, 'OUT', tmp_path)
    cur = SimpleNamespace(execute=lambda *args: None, fetchone=lambda: (1,))
    conn = SimpleNamespace(cursor=lambda: nullcontext(cur))
    monkeypatch.setattr(commands, 'connection', lambda *args: nullcontext(conn))
    monkeypatch.setattr(commands, 'fetch', lambda cur, table:
                        (['ID'], [dict(ID='key  ' if 'BEFORE' in table else 'key')]))
    commands.parity(row, 10)
    assert json.loads((tmp_path / 'probe.json').read_text())['keyed_hash_match']


def test_historical_capture_uses_committed_char_types(tmp_path, monkeypatch):
    import json
    from contextlib import nullcontext
    from types import SimpleNamespace
    from parity import commands

    row = dict(mapping='probe', target_table='AUDIT_EVENT', before_table='PC_BEFORE.AUDIT_EVENT',
               after_table='PC_AUDIT.AUDIT_EVENT', key_columns=['EVENT_ID'], exclude_columns=[])
    monkeypatch.setattr(commands, 'OUT', tmp_path)
    cur = SimpleNamespace(execute=lambda *args: None, fetchone=lambda: (1,))
    conn = SimpleNamespace(cursor=lambda: nullcontext(cur))
    monkeypatch.setattr(commands, 'connection', lambda *args: nullcontext(conn))
    monkeypatch.setattr(commands, 'fetch', lambda cur, table:
                        (['EVENT_ID', 'EVENT_TYPE'], [dict(EVENT_ID=1, EVENT_TYPE=
                         'DOC_VIEW    ' if 'BEFORE' in table else 'DOC_VIEW')]))
    commands.parity(row, 10)
    assert json.loads((tmp_path / 'probe.json').read_text())['keyed_hash_match']


def test_sql_scope_and_owner(monkeypatch):
    assert target_relation('PAYMENT') == 'SFX_BILLING.PAYMENT'
    assert target_relation('DOCUMENT') == 'SFX_DOCUMENTS.DOCUMENT'
    monkeypatch.setenv('PC_CONTROL_SCHEMA', 'PC_CONTROL')
    monkeypatch.setenv('PC_CONTROL_TABLE', 'CUSTOM_MAPPINGS')
    assert control_table() == 'SFX_D1110_AFTER.PC_CONTROL.CUSTOM_MAPPINGS'
    assert 't.OWNER_EFFORT=s.OWNER_EFFORT' in mark_sql()
    assert 'WHEN NOT MATCHED' not in mark_sql()
    assert 'ON t.FOLDER=s.FOLDER AND t.MAPPING=s.MAPPING' in mark_sql()
    assert mark_sql().count('%s') == 16
    assert "IFF(t.STATUS='VERIFIED',COALESCE(t.VERIFIED_AT" in mark_sql()
    assert relation('PC_BILLING.PAYMENT') == 'SFX_D1110_AFTER.PC_BILLING.PAYMENT'
    with pytest.raises(ValueError):
        relation('OTHER.PC_BILLING.PAYMENT')
    with pytest.raises(ValueError):
        identifier('bad; DROP TABLE x')


def test_mark_rejects_other_owner_before_reading_evidence(monkeypatch):
    from types import SimpleNamespace
    from parity import commands
    statements = []

    class Cursor:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def cursor(self):
            return self
        def execute(self, sql, params):
            statements.append(sql)
        def fetchall(self):
            return [('SFX_CONTENT', 'migrations-page')]

    monkeypatch.setattr(commands, 'connection', lambda *args: Cursor())
    with pytest.raises(ValueError, match='ownership mismatch'):
        commands.mark({'folder': 'SFX_CONTENT', 'mapping': 'm_SFX_LOGIN_EVENT'}, SimpleNamespace(owner='act3-workflow'))
    with pytest.raises(ValueError, match='folder mismatch'):
        commands.mark({'folder': 'SFX_AUDIT', 'mapping': 'm_SFX_LOGIN_EVENT'}, SimpleNamespace(owner='migrations-page'))
    assert len(statements) == 2
    assert all(s.startswith('SELECT FOLDER, OWNER_EFFORT') for s in statements)
