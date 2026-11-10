import datetime

import pytest


def ok(td, sql):
    td.execute(sql)
    assert td.errorcode == 0, td.output.getvalue()
    return td.rows


def test_realistic_ddl_and_set(td):
    ok(td, """CREATE SET TABLE ledger, NO FALLBACK,
       NO BEFORE JOURNAL, NO AFTER JOURNAL (
       id BIGINT NOT NULL, code CHAR(10) CHARACTER SET LATIN NOT CASESPECIFIC COMPRESS ('PRO','TEAM'),
       note VARCHAR(20) CHARACTER SET UNICODE CASESPECIFIC TITLE 'Note',
       dt DATE FORMAT 'YYYY-MM-DD', amount DECIMAL(12,2) COMPRESS 0)
       UNIQUE PRIMARY INDEX ledger_idx (id)""")
    ok(td, "INSERT INTO ledger VALUES (1,'pro',NULL,DATE '2026-11-09',1),(1,'pro',NULL,DATE '2026-11-09',1)")
    assert td.activitycount == 1
    ok(td, 'INSERT INTO ledger SELECT * FROM ledger')
    assert td.activitycount == 0
    td.execute("INSERT INTO ledger VALUES (1,'other',NULL,DATE '2026-11-09',1)")
    assert td.errorcode == 2801
    ok(td, 'CREATE MULTISET TABLE feed (id INT, val VARCHAR(20)) NO PRIMARY INDEX')
    ok(td, "INSERT INTO feed VALUES (1,'x'),(1,'x')")
    assert td.activitycount == 2


def test_set_null_and_empty(td):
    ok(td, 'CREATE SET TABLE t (a INT,b INT) PRIMARY INDEX(a)')
    ok(td, 'INSERT INTO t VALUES(NULL,NULL),(NULL,NULL)')
    assert td.activitycount == 1
    ok(td, 'INSERT INTO t SELECT * FROM t WHERE 1=0')
    assert td.activitycount == 0


def test_catalog_schema_resolution(td):
    schema = td.conn.execute('SELECT current_schema()').fetchone()[0]
    ok(td, f'CREATE SET TABLE {schema}.t (id INT) PRIMARY INDEX(id)')
    ok(td, 'INSERT INTO t VALUES(1),(1)')
    assert td.activitycount == 1
    ok(td, f'INSERT INTO {schema}.t VALUES(1)')
    assert td.activitycount == 0
    ok(td, 'DATABASE public')
    ok(td, f'INSERT INTO {schema}.t VALUES(1)')
    assert td.activitycount == 0


def test_multiset_upi(td):
    ok(td, 'CREATE MULTISET TABLE t (id INT) UNIQUE PRIMARY INDEX(id)')
    ok(td, 'INSERT INTO t VALUES(1)')
    td.execute('INSERT INTO t VALUES(1)')
    assert td.errorcode == 2801


def test_case_and_padding(td):
    ok(td, 'CREATE MULTISET TABLE plans (code CHAR(10) NOT CASESPECIFIC, label VARCHAR(20) CASESPECIFIC) PRIMARY INDEX(code)')
    ok(td, "INSERT INTO plans VALUES ('pro','X'),('PRO','x')")
    assert ok(td, "SELECT COUNT(*) FROM plans WHERE code='Pro  '") == [(2,)]
    assert ok(td, "SELECT COUNT(*) FROM plans WHERE label='x'") == [(1,)]
    assert ok(td, "SELECT COUNT(*) FROM plans WHERE label LIKE 'x%'") == [(1,)]
    assert ok(td, "SELECT COUNT(*) FROM plans WHERE code LIKE 'p%'") == [(2,)]
    assert len(ok(td, 'SELECT code,COUNT(*) FROM plans GROUP BY code')) == 1
    assert len(ok(td, 'SELECT DISTINCT code FROM plans')) == 1
    ok(td, 'CREATE MULTISET TABLE subscriptions (code VARCHAR(10)) PRIMARY INDEX(code)')
    ok(td, "INSERT INTO subscriptions VALUES('PrO  ')")
    assert ok(td, 'SELECT COUNT(*) FROM subscriptions s JOIN plans p ON s.code=p.code') == [(2,)]
    ok(td, "INSERT INTO subscriptions VALUES('PRO'),('pro ')")
    assert len(ok(td, 'SELECT code,COUNT(*) FROM subscriptions GROUP BY code')) == 1
    assert len(ok(td, 'SELECT DISTINCT code FROM subscriptions')) == 1


def test_truncation(td):
    ok(td, 'CREATE MULTISET TABLE src (v VARCHAR(200)) NO PRIMARY INDEX')
    ok(td, "INSERT INTO src VALUES('abcdefgh')")
    ok(td, 'CREATE MULTISET TABLE dst (v VARCHAR(3), c CHAR(2)) NO PRIMARY INDEX')
    ok(td, "INSERT INTO dst VALUES('longer','abcd')")
    ok(td, 'INSERT INTO dst SELECT v,v FROM src')
    assert ok(td, 'SELECT v FROM dst ORDER BY v') == [('abc',), ('lon',)]
    ok(td, "UPDATE dst SET v='xyz123'")
    assert ok(td, 'SELECT DISTINCT v FROM dst') == [('xyz',)]
    ok(td, 'CREATE MULTISET TABLE other (a VARCHAR(2)) NO PRIMARY INDEX')
    ok(td, 'INSERT INTO other SELECT * FROM src')
    assert ok(td, 'SELECT a FROM other') == [('ab',)]


def test_dates(td):
    ok(td, 'CREATE MULTISET TABLE dates (d DATE) NO PRIMARY INDEX')
    ok(td, "INSERT INTO dates VALUES(DATE '2026-11-09'),(DATE '1999-12-31'),(DATE '2024-02-29')")
    assert ok(td, 'SELECT CAST(d AS INTEGER) FROM dates ORDER BY d') == [(991231,), (1240229,), (1261109,)]
    assert ok(td, 'SELECT CAST(1261109 AS DATE)') == [(datetime.date(2026, 11, 9),)]
    assert ok(td, 'SELECT (d / 100) MOD 100 FROM dates WHERE d BETWEEN 1261101 AND 1261130') == [(11,)]
    assert ok(td, 'SELECT d+1 FROM dates WHERE 1261109=d') == [(datetime.date(2026, 11, 10),)]
    ok(td, 'CREATE MULTISET TABLE datekeys (k INT) NO PRIMARY INDEX')
    ok(td, 'INSERT INTO datekeys VALUES(991231)')
    assert ok(td, 'SELECT CAST(k AS DATE) FROM datekeys') == [(datetime.date(1999, 12, 31),)]
    assert ok(td, "SELECT d-1,ADD_MONTHS(d,1),EXTRACT(YEAR FROM d) FROM dates WHERE d=1240229")[0][:2] == (datetime.date(2024, 2, 28), datetime.date(2024, 3, 29))
    td.execute('SELECT CAST(1261399 AS DATE)')
    assert td.errorcode == 2620


def test_formats(td, tmp_path):
    ok(td, "CREATE MULTISET TABLE dates (d DATE FORMAT 'YYYYMMDD') NO PRIMARY INDEX")
    ok(td, "INSERT INTO dates VALUES(DATE '2026-11-09')")
    assert ok(td, "SELECT CAST('202611' AS DATE FORMAT 'YYYYMM')") == [(datetime.date(2026, 11, 1),)]
    assert ok(td, "SELECT CAST(202611 AS DATE FORMAT 'YYYYMM')") == [(datetime.date(2026, 11, 1),)]
    assert ok(td, "SELECT CAST(CAST(d AS FORMAT 'YYYY-MM') AS CHAR(7)), CAST(d AS VARCHAR(10) FORMAT 'YYYY-MM-DD'),(d (FORMAT 'YYYYMMDD')) FROM dates") == [('2026-11', '2026-11-09', '20261109')]
    out = tmp_path / 'report'
    td.run(f'.EXPORT REPORT FILE={out}\nSELECT d FROM dates;\n.EXPORT RESET')
    assert out.read_text() == '20261109\n'
    assert ok(td, "SELECT CAST(d AS VARCHAR(10) FORMAT 'YYYYBMMBDD') FROM dates") == [('2026 11 09',)]


def test_merge(td):
    ok(td, 'CREATE MULTISET TABLE target (id INT,v INT) UNIQUE PRIMARY INDEX(id)')
    ok(td, 'CREATE MULTISET TABLE source (id INT,v INT) NO PRIMARY INDEX')
    ok(td, 'INSERT INTO target VALUES(1,0)')
    ok(td, 'INSERT INTO source VALUES(1,2),(2,3)')
    ok(td, 'MERGE INTO target t USING source s ON t.id=s.id WHEN MATCHED THEN UPDATE SET v=s.v WHEN NOT MATCHED THEN INSERT(id,v) VALUES(s.id,s.v)')
    assert ok(td, 'SELECT * FROM target ORDER BY id') == [(1, 2), (2, 3)]


def test_qualify(td):
    ok(td, 'CREATE MULTISET TABLE t (id INT,v INT) NO PRIMARY INDEX')
    ok(td, 'INSERT INTO t VALUES(1,1),(1,2),(2,1)')
    assert ok(td, 'SELECT id,v FROM t QUALIFY ROW_NUMBER() OVER (PARTITION BY id ORDER BY v DESC)=1 ORDER BY id') == [(1, 2), (2, 1)]


def test_misc(td):
    ok(td, 'CREATE VOLATILE TABLE t (id INT) ON COMMIT PRESERVE ROWS')
    ok(td, 'INS INTO t VALUES(1),(2)')
    ok(td, 'BT')
    ok(td, 'UPD t SET id=id+1')
    ok(td, 'ET')
    assert ok(td, 'SEL TOP 1 id FROM t ORDER BY id') == [(2,)]
    assert ok(td, "SEL ZEROIFNULL(NULL),NULLIFZERO(0),INDEX('abc','b'),OREPLACE('abc','b','x'),2**3") == [(0, None, 2, 'axc', 8.0)]
    ok(td, 'COLLECT STATISTICS COLUMN(id) ON t')
    ok(td, 'CREATE VIEW v AS LOCKING ROW FOR ACCESS SELECT id FROM t')
    assert ok(td, 'SELECT id FROM v MINUS SELECT id FROM t') == []
    ok(td, 'DEL FROM t WHERE id=2')
    ok(td, 'DROP VIEW v')
    ok(td, 'DROP TABLE t')
    td.execute('SELECT * FROM t')
    assert td.errorcode == 3807


def test_macros(td):
    ok(td, 'CREATE MULTISET TABLE t (id INT,v VARCHAR(10)) NO PRIMARY INDEX')
    ok(td, "REPLACE MACRO m (p INTEGER, v VARCHAR(10)) AS (INSERT INTO t VALUES(:p,:v); SELECT * FROM t WHERE id=:p;)")
    assert ok(td, "EXEC m(1,'a;z')") == [(1, 'a;z')]
    td.execute('EXEC missing(1)')
    assert td.errorcode == 3807


def test_spl(td):
    ok(td, 'CREATE MULTISET TABLE t (id INT) NO PRIMARY INDEX')
    ok(td, '''REPLACE PROCEDURE p (IN a INTEGER, OUT b INTEGER) BEGIN
       DECLARE i INTEGER DEFAULT 0;
       SET b=0;
       WHILE i<a DO
         SET i=i+1;
         IF i=1 THEN INSERT INTO t VALUES(i);
         ELSEIF i=2 THEN INSERT INTO t VALUES(i*10);
         ELSE INSERT INTO t VALUES(i*100); END IF;
       END WHILE;
       FOR r AS c CURSOR FOR SELECT id FROM t DO SET b=b+r.id; END FOR;
       SELECT SUM(id) INTO b FROM t;
       END''')
    ok(td, 'CALL p(3,?)')
    assert 'b = 321' in td.output.getvalue()
    assert ok(td, 'SELECT id FROM t ORDER BY id') == [(1,), (20,), (300,)]
    ok(td, 'CALL p(0,?)')


def test_spl_status(td):
    ok(td, '''CREATE PROCEDURE status_p (OUT code INTEGER) BEGIN
       SELECT * FROM absent;
       IF SQLSTATE <> '00000' THEN SET code=SQLCODE; END IF;
       END''')
    td.execute('CALL status_p(?)')
    assert 'code = 3807' in td.output.getvalue()
    ok(td, 'CREATE MULTISET TABLE t (id INT) NO PRIMARY INDEX')
    ok(td, '''CREATE PROCEDURE count_p (OUT n INTEGER) BEGIN
       INSERT INTO t VALUES(1),(2);
       SET n=ACTIVITY_COUNT;
       END''')
    ok(td, 'CALL count_p(?)')
    assert 'n = 2' in td.output.getvalue()


@pytest.mark.parametrize('statement,code', [('SELECT * FROM absent',3807), ('DATABASE no_schema',3802), ('SELECT 999999999999999999999::INTEGER',2616), ('SELECT FROM',3706)])
def test_errors(td, statement, code):
    td.execute(statement)
    assert td.errorcode == code, td.output.getvalue()


def test_database_ddl(td):
    name = td.conn.execute('SELECT current_schema()').fetchone()[0] + '_other'
    ok(td, f'CREATE DATABASE {name} FROM DBC AS PERM=0')
    ok(td, f'DATABASE {name}')
    td.conn.execute('DROP SCHEMA ' + name)
