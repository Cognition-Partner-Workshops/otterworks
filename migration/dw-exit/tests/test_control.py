import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import control


class Cursor:
    def __init__(self, values=()):
        self.calls = []
        self.values = iter(values)

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return (next(self.values),)


def test_tags():
    assert control.query_tag('load_dbql') == '{"run":"sfx-d1110","act":"assess","step":"load_dbql"}'
    cursor = Cursor()
    control.tag(cursor, 'verify')
    assert json.loads(cursor.calls[0][1][0])['step'] == 'verify'


def test_scope_guard():
    with pytest.raises(ValueError, match='scope mismatch'):
        control.connection_options({'SNOWFLAKE_DATABASE': 'OTHER'})


def test_missing_schema(capsys):
    assert not control.verify(Cursor([0]))
    assert 'MIGRATION_CONTROL missing' in capsys.readouterr().out


def test_insert_empty_and_parameterized():
    cursor = Cursor()
    control.insert_rows(cursor, 'MANIFEST', ['id'], [])
    assert cursor.calls == []
    control.insert_rows(cursor, 'MANIFEST', ['id'], [{'id': "a'quoted"}])
    assert "a'quoted" not in cursor.calls[0][0]
    assert cursor.calls[0][1] == ("a'quoted",)
    with pytest.raises(ValueError):
        control.insert_rows(cursor, 'OTHER', ['id'], [])


def test_schema_and_view_contracts():
    cursor = Cursor()
    control.create_table(cursor, 'MANIFEST', control.MANIFEST_FIELDS)
    ddl = cursor.calls[0][0]
    assert "STATUS\" VARCHAR DEFAULT 'not_started'" in ddl
    assert 'UPDATED_AT TIMESTAMP_LTZ' in ddl
    assert 'UPDATED_BY_ACT' in ddl
    assert control.COMMENT in ddl
    views = control.view_sql()
    assert set(views) == control.VIEWS
    assert 'NOT EXISTS' in views['V_DEAD_OBJECTS']
    assert '2026-11-10' in views['V_DEAD_OBJECTS']
    assert "STATUS NOT IN ('done','retired')" in views['V_LICENCE_COUNTER']
    assert 'CODE_PRINCIPALS' in views['V_HIDDEN_CONSUMERS']


def test_dead_feeders(estate=None):
    from assess import build
    data = build()
    expected = {'m_SFX_AUDIT_EVENT_ARCHIVE', 's_m_SFX_AUDIT_EVENT_ARCHIVE',
                'SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE', 'SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG',
                'audit_audit_event_archive', 'documents_search_index_log'}
    assert expected <= set(data['dead_dependents'])
    assert len(data['dead']) == 6
    for row in data['objects']:
        if row['name'] in data['dead_dependents']:
            assert row['target_type'] == 'retire'
            assert 'feeds only dead objects' in row['risk_reasons']


def test_load_uses_pinned_dbql(monkeypatch):
    import assess
    loaded = {}
    monkeypatch.setattr(control, 'tag', lambda *a: None)
    monkeypatch.setattr(control, 'create_table', lambda *a: None)
    monkeypatch.setattr(control, 'build', lambda: {'scans': {}})
    monkeypatch.setattr(control, 'insert_rows', lambda cursor, table, fields, records: loaded.__setitem__(table, len(records)))

    class Cursor:
        def execute(self, *args):
            pass

    control.load(Cursor())
    pinned = assess.before_state_root() / 'warehouse/teradata/dbql/qrylog.csv'
    with pinned.open() as stream:
        expected = sum(1 for _ in stream) - 1
    assert loaded['DBQL_QRYLOG'] == expected == 7990


def test_history_preserves_assessment_scope():
    class HistoryCursor(Cursor):
        description = [('STEP',), ('EXECUTION_STATUS',), ('QUERY_COUNT',)]

        def fetchall(self):
            return []

    cursor = HistoryCursor()
    control.history(cursor)
    sql = cursor.calls[-1][0]
    assert sql == (control.OUT / 'query_history_assess.sql').read_text()
    assert 'assess' in sql
    assert 'prove' not in sql
