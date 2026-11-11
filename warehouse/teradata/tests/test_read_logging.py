import datetime as dt
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from bteq.runner import Runner


@pytest.mark.parametrize('modifier,statement,kind,objects', [
    ('LOCKING ROW FOR ACCESS', 'SEL * FROM billing.invoices', 'SELECT', {('billing', 'invoices')}),
    ('locking table billing.lock_target for read nowait',
     'WITH paid AS (SEL * FROM billing.payments) SEL * FROM paid',
     'SELECT', {('billing', 'payments'), ('public', 'paid')}),
    ('LOCKING DATABASE billing IN EXCLUSIVE LOCKING ROW FOR READ',
     'SELECT * FROM billing.invoices UNION ALL SELECT * FROM billing.payments',
     'SELECT', {('billing', 'invoices'), ('billing', 'payments')}),
    ('LOCKING ROW FOR WRITE', 'UPD billing.invoices SET amount=0', 'UPDATE', {('billing', 'invoices')}),
    ('LOCKING TABLE billing.invoices FOR EXCLUSIVE',
     'INS INTO billing.invoices SELECT * FROM billing.payments',
     'INSERT', {('billing', 'invoices'), ('billing', 'payments')}),
    ('LOCKING ROW FOR CHECKSUM', 'DEL FROM billing.invoices', 'DELETE', {('billing', 'invoices')}),
    ('LOCKING ROW FOR ACCESS', 'SELECT * FROM', 'SELECT', set()),
    ('', 'SELECT 1', 'SELECT', set()),
])
def test_locking_request_logging_offline(monkeypatch, modifier, statement, kind, objects):
    log = MagicMock()
    log.execute.return_value.fetchone.return_value = (123,)
    connect = MagicMock()
    connect.return_value.__enter__.return_value = log
    monkeypatch.setattr('bteq.runner.psycopg.connect', connect)
    runner = object.__new__(Runner)
    runner.conn = SimpleNamespace(info=SimpleNamespace(dsn='unused'))
    runner.logon_user = 'svc_locking_test'
    runner.variables = {}
    runner.activitycount = 7
    runner.errorcode = 3706 if statement == 'SELECT * FROM' else 0
    source = (modifier + '\n' + statement).strip()
    started = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    runner.log_statement(source, started)

    calls = log.execute.call_args_list
    row = calls[1].args[1]
    assert row == (123, 'svc_locking_test', 'BTEQ', '', started,
                   row[5], kind, source, 7, runner.errorcode)
    usage = 'READ' if kind == 'SELECT' else 'WRITE'
    assert {call.args[1] for call in calls[2:]} == {
        (123, database, table, 'T', usage) for database, table in objects
    }


def test_logon_success_error_and_objects(td):
    td.variables.update(TD_APP_ID='verification', TD_CLIENT_ID='test-client')
    td.run('.LOGON localhost/svc_test_reader,unused;\nSELECT 1;\nSELECT * FROM missing_table;')
    rows = td.conn.execute('''SELECT username,appid,clientid,starttime,statementtype,errorcode,queryid
                              FROM dbc.qrylogv WHERE username='svc_test_reader' ORDER BY queryid''').fetchall()
    assert len(rows) == 2
    assert all(r[:3] == ('svc_test_reader', 'verification', 'test-client') for r in rows)
    assert all(r[3].date() == dt.datetime.now(dt.timezone.utc).date() and r[4] == 'SELECT' for r in rows)
    assert [r[5] for r in rows] == [0, 3807]
    assert td.conn.execute('SELECT objecttablename FROM dbc.qrylogobjectsv WHERE queryid=%s', (rows[-1][-1],)).fetchall() == [('missing_table',)]


def test_logging_survives_rollback(td):
    td.logon_user = 'svc_rollback_reader'
    td.execute('BT')
    td.execute('SELECT 1')
    td.conn.execute('ROLLBACK')
    assert td.conn.execute("SELECT count(*) FROM dbc.qrylogv WHERE username='svc_rollback_reader'").fetchone()[0] == 2


@pytest.mark.parametrize('source', ['', ' ', '\n'])
def test_empty_request_logging_offline(monkeypatch, source):
    connect = MagicMock()
    monkeypatch.setattr('bteq.runner.psycopg.connect', connect)
    runner = object.__new__(Runner)
    runner.log_statement(source, dt.datetime.now(dt.timezone.utc))
    connect.assert_not_called()


def test_adjacent_semicolons_continue(td):
    td.logon_user = 'svc_empty_request_test'
    td.run('SELECT 1;;SELECT 2;')
    rows = td.conn.execute("SELECT querytext FROM dbc.qrylogv WHERE username='svc_empty_request_test' ORDER BY queryid").fetchall()
    assert [row[0].strip() for row in rows] == ['SELECT 1', 'SELECT 2']
