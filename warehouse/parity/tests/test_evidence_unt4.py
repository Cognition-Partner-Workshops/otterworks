"""Offline UNT-4 checks: fixture construction, guards and gate negative controls; not live parity."""
from copy import deepcopy
from datetime import date, datetime, timedelta

import pytest

from parity.evidence import cell, full_compare, replay_gate

NO_REJECTS = ([], [], [])
from parity import evidence_unt4 as unt4

KEYS = ['ACTOR_USER_ID', 'DOCUMENT_ID', 'EVENT_TS', 'EVENT_TYPE', 'DETAILS']


def archive():
    types = {'ARCHIVE_ID': ['bigint', None, 64, 0, None], 'ACTOR_USER_ID': ['bigint', None, 64, 0, None],
             'DOCUMENT_ID': ['bigint', None, 64, 0, None],
             'EVENT_TS': ['timestamp without time zone', None, None, None, 0],
             'EVENT_TYPE': ['character', 12, None, None, None], 'DETAILS': ['character varying', 160, None, None, None]}
    rows = [[cell(1), cell(5), cell(7), cell(datetime(2019, 11, 11, 23, 59, 59)), cell('DOC_EXPORT  '), cell(' a ')],
            [cell(2), cell(None), cell(None), cell(datetime(2001, 1, 1)), cell(None), cell(None)]]
    return {'columns': list(types), 'types': types, 'rows': rows}


def test_fixture_boundaries():
    today = date(2026, 11, 10)
    cutoff, rows, history = unt4.fixture_rows(today)
    assert cutoff == datetime(2019, 11, 12)
    archived = [r[0] for r in rows if r[4] is not None and r[4] < cutoff]
    assert archived == [91000001, 91000002, 91000006, 91000007, 91000008, 91000011, 91000012, 91000013]
    assert [r[0] for r in rows] == sorted(r[0] for r in rows)
    assert any(r[4] == cutoff for r in rows) and any(r[4] == cutoff + timedelta(seconds=1) for r in rows)
    assert len({tuple(r[1:2] + r[2:3] + r[4:]) for r in rows}) == len(rows), 'archive tuple collisions fail the gate'
    assert {h[0] for h in history} == {7, 8, 9} and unt4.HISTORY_NEXT == 10


@pytest.mark.parametrize('sql', [
    'CREATE SCHEMA IF NOT EXISTS SFX_D1110_AFTER.PC_AUDIT_UNT4_FIXTURE COMMENT = 1',
    'CREATE TABLE SFX_D1110_AFTER.PC_AUDIT_UNT4_FIXTURE.AUDIT_EVENT (A INT)',
    'INSERT INTO SFX_D1110_AFTER.PC_AUDIT_UNT4_FIXTURE.AUDIT_EVENT VALUES (1)'])
def test_fixture_writes_allowed(sql):
    assert unt4.WRITE.match(sql)


@pytest.mark.parametrize('sql', [
    'INSERT INTO SFX_D1110_AFTER.PC_AUDIT.AUDIT_EVENT_ARCHIVE VALUES (1)',
    'CREATE OR REPLACE TABLE SFX_D1110_AFTER.PC_AUDIT_UNT4_FIXTURE.AUDIT_EVENT (A INT)',
    'DELETE FROM SFX_D1110_AFTER.PC_AUDIT_UNT4_FIXTURE.AUDIT_EVENT',
    'UPDATE SFX_D1110_AFTER.MIGRATION_CONTROL.MAPPINGS SET STATUS=1',
    'INSERT INTO SFX_D1110_AFTER.PC_AUDIT_UNT4_FIXTURE_X.T VALUES (1)'])
def test_other_writes_refused(sql):
    assert not unt4.WRITE.match(sql)


def test_owned_scope():
    assert unt4.owned('m_SFX_AUDIT_EVENT_ARCHIVE')['parameters']['$$ARCHIVE_DAYS'] == '2555'
    assert not unt4.owned('m_SFX_AUDIT_EVENT_ARCHIVE')['enabled_in_workflow']
    assert unt4.owned('m_SFX_AUDIT_DAILY_SUMMARY')['sequence_columns'] == ['SUMMARY_ID']
    with pytest.raises(ValueError):
        unt4.owned('m_SFX_SECURITY_ALERT')


@pytest.mark.parametrize('case', ['id', 'timestamp', 'padding', 'whitespace', 'null_vs_empty', 'legacy_append', 'missing'])
def test_archive_negative_controls(case):
    before = archive()
    after = deepcopy(before)
    if case == 'id':
        after['rows'][0][0] = cell(3)
    elif case == 'timestamp':
        after['rows'][0][3] = cell(datetime(2019, 11, 12))
    elif case == 'padding':
        after['rows'][0][4] = cell('DOC_EXPORT')
    elif case == 'whitespace':
        after['rows'][0][5] = cell('a')
    elif case == 'null_vs_empty':
        after['rows'][1][5] = cell('')
    elif case == 'legacy_append':
        after['rows'] += [[cell(3)] + r[1:] for r in before['rows'][:1]]
    elif case == 'missing':
        after['rows'] = after['rows'][:1]
    assert not full_compare(before, after, KEYS)['equal']
    assert not replay_gate(before, before, after, KEYS, ['ARCHIVE_ID'], NO_REJECTS)['passed']


def test_archive_positive():
    snap = archive()
    assert replay_gate(snap, snap, deepcopy(snap), KEYS, ['ARCHIVE_ID'], NO_REJECTS)['passed']


def test_python_value_roundtrip():
    row = archive()['rows'][0]
    assert [cell(unt4.python_value(c)) for c in row] == row
