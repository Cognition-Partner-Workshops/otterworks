import datetime as dt


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
