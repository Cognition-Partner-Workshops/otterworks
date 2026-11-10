from bteq.parser import commands, split


def test_sql_case_inside_procedure(td):
    td.execute('''REPLACE PROCEDURE p_case (IN amount INTEGER, OUT result INTEGER)
BEGIN
IF amount > 0 THEN
SET result=CASE WHEN amount>10 THEN CASE WHEN amount>20 THEN 3 ELSE 2 END ELSE 1 END;
ELSE
SET result=0;
END IF;
END''')
    assert td.errorcode == 0
    for value, expected in ((0, 0), (5, 1), (15, 2), (25, 3)):
        td.execute(f'CALL p_case({value}, ?)')
        assert td.errorcode == 0, td.output.getvalue()
        assert f'result = {expected}' in td.output.getvalue()


def test_parser():
    assert list(commands("-- comment\n.LOGON ${TD_USER}\nSELECT 'a;--x',\n'it''s'; /* c */\n.QUIT 0")) == ['.LOGON ${TD_USER}', "SELECT 'a;--x',\n'it''s'", '.QUIT 0']
    assert split("a(1,2),'x,y',z", ',') == ['a(1,2)', "'x,y'", 'z']
    assert list(commands('')) == []
    assert list(commands('SELECT 1; SELECT 2\n;')) == ['SELECT 1', 'SELECT 2']
    assert len(list(commands('REPLACE MACRO m(p INT) AS (\nSELECT :p;\nSELECT :p+1;\n);'))) == 1


def test_control_flow(td):
    assert td.run('SELECT * FROM absent;\n.IF ERRORCODE <> 0 THEN .GOTO fail\n.QUIT 1\n.LABEL fail\n.QUIT 7') == 7
    assert td.run('SELECT 1 WHERE 1=0;\n.IF ACTIVITYCOUNT = 0 THEN .QUIT 3') == 3
    assert td.run('SELECT * FROM absent;') == 0
    assert td.run('.LABEL prior\n.GOTO prior') == 3706
    assert td.run('') == 0
    assert td.run('.IF ERRORLEVEL >= 8 THEN .QUIT 4') == 4


def test_import_export_run_variables(td, tmp_path):
    feed, out, nested = (tmp_path / p for p in ('feed', 'out', 'nested'))
    feed.write_text('1|abcdef\n2|xyz\n')
    nested.write_text('SELECT 99;')
    td.variables['TABLE'] = 'items'
    result = td.run(f'''CREATE MULTISET TABLE ${{TABLE}} (id INT,v VARCHAR(3)) NO PRIMARY INDEX;
.SET SEPARATOR '|'
.IMPORT VARTEXT '|' FILE={feed}
.REPEAT *
USING (id INTEGER,v VARCHAR(20)) INSERT INTO items VALUES(:id,:v);
.EXPORT DATA FILE={out}
SELECT * FROM items ORDER BY id;
.EXPORT RESET
.RUN FILE={nested}
.LOGOFF
.EXIT 0''')
    assert result == 0
    assert td.errorcode == 0, td.output.getvalue()
    assert out.read_text() == '1|abc\n2|xyz\n'
    assert td.rows == [(99,)]


def test_multiline_routines(td):
    assert td.run('''CREATE MULTISET TABLE t (id INT) NO PRIMARY INDEX;
REPLACE MACRO m(p INT) AS (
INSERT INTO t VALUES(:p);
INSERT INTO t VALUES(:p+1);
);
CREATE PROCEDURE p(IN n INT,OUT total INT)
BEGIN
IF n>0 THEN
EXEC m(n);
END IF;
SELECT COUNT(*) INTO total FROM t;
END;
CALL p(4,?);
.IF ERRORCODE <> 0 THEN .QUIT 1
.QUIT 0''') == 0
    assert 'total = 2' in td.output.getvalue()


def test_cli(td, tmp_path):
    import subprocess
    from pathlib import Path

    shim = Path(__file__).resolve().parents[1] / 'bin' / 'bteq'
    result = subprocess.run([str(shim)], input='SELECT 1;\n.QUIT 7', text=True, capture_output=True)
    assert result.returncode == 7, result.stderr
    assert '*** Query completed. 1 rows found.' in result.stdout
    script = tmp_path / 'script.bteq'
    script.write_text('SELECT ${N};\n.QUIT 0')
    result = subprocess.run([str(shim), 'run', str(script), '--var', 'N=42'], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert '42' in result.stdout
