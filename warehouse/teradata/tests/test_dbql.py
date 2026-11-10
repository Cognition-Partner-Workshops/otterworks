import csv
import datetime as dt
from pathlib import Path

import pytest

from dbql.generate import AS_OF, CLIENTS, DENSE_START, QUIET_OBJECTS, ROOT, START, generate, inventory
from dbql.load import FEEDS, load_history
from test_estate import estate


def query(runner, statement):
    runner.execute(statement)
    assert runner.errorcode == 0, runner.output.getvalue()
    return runner.rows


def test_history_reproducibility(tmp_path):
    counts = generate(tmp_path)
    assert set(counts) == {'qrylog.csv', 'objectusage.csv', 'tablesv.csv'}
    assert sum((ROOT / 'dbql' / name).stat().st_size for name in counts) < 5_000_000
    for name in counts:
        assert (tmp_path / name).read_bytes() == (ROOT / 'dbql' / name).read_bytes()
    with (tmp_path / 'qrylog.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    timestamps = [dt.datetime.fromisoformat(r['StartTime']) for r in rows]
    assert timestamps == sorted(timestamps)
    assert min(timestamps).date() == START and max(timestamps).date() == AS_OF-dt.timedelta(days=1)
    assert len({r['QueryID'] for r in rows}) == len(rows)
    assert {r['UserName'] for r in rows} == CLIENTS.keys()
    assert sum(t.date() >= DENSE_START for t in timestamps) / 30 > sum(t.date() < DENSE_START for t in timestamps) / 60
    assert {'0', '3807', '2616'} == {r['ErrorCode'] for r in rows}
    assert all(int(r['NumResultRows']) == 0 for r in rows if r['ErrorCode'] != '0')
    generate(tmp_path / 'different', seed=1111)
    assert (tmp_path / 'different/qrylog.csv').read_bytes() != (tmp_path / 'qrylog.csv').read_bytes()


def test_catalog_access_window(estate):
    unused = query(estate, '''SELECT t.DatabaseName, t.TableName, t.TableKind
FROM DBC.TablesV t LEFT JOIN (
SELECT DISTINCT o.ObjectDatabaseName, o.ObjectTableName
FROM DBC.QryLogObjectsV o JOIN DBC.QryLogV q ON o.QueryID=q.QueryID
WHERE q.StartTime>=TIMESTAMP '2026-08-12 00:00:00'
AND q.StartTime<TIMESTAMP '2026-11-10 00:00:00'
) r ON t.DatabaseName=r.ObjectDatabaseName AND t.TableName=r.ObjectTableName
WHERE r.ObjectTableName IS NULL ORDER BY t.DatabaseName,t.TableName''')
    assert {database+'.'+name for database, name, _ in unused} == QUIET_OBJECTS
    assert sorted(kind for _, _, kind in unused) == ['M', 'T', 'T', 'T', 'V', 'V']
    old = query(estate, "SELECT DatabaseName,TableName FROM DBC.TablesV WHERE LastAccessTimeStamp<TIMESTAMP '2026-08-12 00:00:00' AND AccessCount=0")
    assert {database+'.'+name for database, name in old} == QUIET_OBJECTS
    catalog = query(estate, 'SELECT DatabaseName,TableName,TableKind FROM DBC.TablesV')
    assert {d+'.'+n: k for d, n, k in catalog} == {name: kind for name, (kind, _) in inventory().items()}
    physical = estate.conn.execute("SELECT upper(n.nspname||'.'||c.relname) FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname IN ('sfx_billing','sfx_documents','sfx_users','sfx_audit','dbc') AND c.relkind IN ('r','v') UNION ALL SELECT upper(name) FROM sfx_td.routines").fetchall()
    assert {row[0] for row in physical} == inventory().keys()
    assert query(estate, '''SELECT COUNT(*) FROM DBC.TablesV t JOIN (
SELECT o.ObjectDatabaseName,o.ObjectTableName,COUNT(*) AS AccessCount,MAX(q.StartTime) AS LastAccessTimeStamp
FROM DBC.QryLogObjectsV o JOIN DBC.QryLogV q ON o.QueryID=q.QueryID
GROUP BY o.ObjectDatabaseName,o.ObjectTableName
) r ON t.DatabaseName=r.ObjectDatabaseName AND t.TableName=r.ObjectTableName
WHERE t.AccessCount<>r.AccessCount OR t.LastAccessTimeStamp<>r.LastAccessTimeStamp''') == [(0,)]


def test_consumer_clients_and_daily_reads(estate):
    clients = query(estate, "SELECT DISTINCT UserName,AppID,ClientID FROM DBC.QryLogV WHERE UserName IN ('FIN_ANALYST_JMORALES','svc_partner_sftp') ORDER BY UserName")
    assert clients == [('FIN_ANALYST_JMORALES', 'ODBC', 'Microsoft Excel; workstation=FIN-WS-014'),
                       ('svc_partner_sftp', 'SFTP Export', 'sftp.partner-feed.example')]
    daily = query(estate, "SELECT UserName,CAST(StartTime AS DATE) AS ReadDate,COUNT(*) AS Reads FROM DBC.QryLogV WHERE StatementType='SELECT' AND ErrorCode=0 GROUP BY UserName,CAST(StartTime AS DATE)")
    assert daily and all(isinstance(row[1], dt.date) and row[2] > 0 for row in daily)
    excel = query(estate, "SELECT StartTime FROM DBC.QryLogV WHERE UserName='FIN_ANALYST_JMORALES'")
    assert all(timestamp.weekday()<5 and 9<=timestamp.hour<=16 for timestamp, in excel)
    script = (ROOT / 'dbql/consumer_reads.bteq').read_text()
    assert estate.run(script) == 0, estate.output.getvalue()
    assert estate.rows[0][0] == 'svc_analytics_dash'
    assert {'FIN_ANALYST_JMORALES', 'svc_partner_sftp'} <= {r[0] for r in estate.rows}
    for directory in ('scripts', 'macros', 'procedures', 'jobs', 'load', 'ddl'):
        for path in (ROOT / directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                source = path.read_text()
                assert 'FIN_ANALYST_JMORALES' not in source and 'svc_partner_sftp' not in source


def test_layered_views(estate):
    assert query(estate, 'SELECT * FROM SFX_BILLING.V_INVOICE_REVENUE') == []
    query(estate, "INSERT INTO SFX_BILLING.CUSTOMER_ACCOUNT (CUSTOMER_ID,ACCOUNT_NAME) VALUES (1,'Meadowford Freight AS')")
    query(estate, "INSERT INTO SFX_BILLING.INVOICE_HDR (INVOICE_ID,CUSTOMER_ID,INVOICE_DT,CURRENCY_CD,TOTAL_AMOUNT) VALUES (1,1,DATE '2026-11-09','usd',12.34),(2,1,DATE '2026-11-08','USD',5.66)")
    rows = query(estate, 'SELECT INVOICE_PERIOD,INVOICE_COUNT,TOTAL_AMOUNT FROM SFX_BILLING.V_INVOICE_REVENUE')
    assert rows == [('2026-11', 2, 18)]
    query(estate, 'INSERT INTO SFX_DOCUMENTS.DOCUMENT (DOCUMENT_ID,OWNER_USER_ID) VALUES (1,1)')
    query(estate, 'INSERT INTO SFX_DOCUMENTS.DOC_VERSION (VERSION_ID,DOCUMENT_ID,FILE_SIZE) VALUES (1,1,4096)')
    assert query(estate, 'SELECT * FROM SFX_DOCUMENTS.V_WORKSPACE_STORAGE') == [(1, 1, 4096)]


def test_history_empty_and_failed_reload(estate, tmp_path):
    before = query(estate, 'SELECT COUNT(*) FROM DBC.QryLogV')
    for name, _, columns in FEEDS:
        with (tmp_path/name).open('w', newline='') as handle:
            csv.writer(handle).writerow(columns)
    (tmp_path/'tablesv.csv').write_text('wrong,header\n')
    with pytest.raises(ValueError, match='header'):
        load_history(estate, tmp_path)
    assert query(estate, 'SELECT COUNT(*) FROM DBC.QryLogV') == before
    (tmp_path/'tablesv.csv').unlink()
    with pytest.raises(FileNotFoundError):
        load_history(estate, tmp_path)
    assert query(estate, 'SELECT COUNT(*) FROM DBC.QryLogV') == before
    with (tmp_path/'tablesv.csv').open('w', newline='') as handle:
        csv.writer(handle).writerow(FEEDS[2][2])
    assert all(count == 0 for count in load_history(estate, tmp_path).values())
    assert query(estate, 'SELECT COUNT(*) FROM DBC.QryLogV') == [(0,)]
    assert all(count > 0 for count in load_history(estate).values())
