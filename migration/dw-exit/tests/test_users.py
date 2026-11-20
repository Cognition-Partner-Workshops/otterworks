import json
from pathlib import Path
import re

import duckdb
import pytest
from sqlglot import exp
import yaml

import assess
from parity import local_sql, object_board, provenance, report_outputs, semantics
from parity.ladder import local_compare

ROOT = Path(__file__).resolve().parents[3]
USERS = ROOT/'migration/dw-exit/users'


def tables(connection, schema='USERS'):
    connection.execute('CREATE SCHEMA '+schema)
    for statement in local_sql.statements(USERS/'00_tables.sql', '20261109'):
        for column in statement.find_all(exp.ColumnDef):
            column.set('constraints', [])
        for table in statement.find_all(exp.Table):
            table.set('db', exp.to_identifier(schema))
        connection.execute(statement.sql(dialect='duckdb'))


@pytest.mark.parametrize('populated', [False, True])
def test_users_shipped_chain_preserves_replacement_and_activity_semantics(populated):
    with duckdb.connect() as db:
        tables(db)
        if populated:
            db.execute("INSERT INTO USERS.STG_APP_USER VALUES (1,' Name ','Mixed@EXAMPLE','pending','2020-01-01')")
            db.execute("INSERT INTO USERS.APP_USER VALUES (2,'stale',NULL,NULL,NULL)")
            db.execute("INSERT INTO USERS.STG_USER_PROFILE VALUES (1,1,'Title','us','UTC')")
            db.execute("INSERT INTO USERS.STG_TEAM VALUES (1,1,'Team','2020-01-01')")
            db.execute("INSERT INTO USERS.STG_TEAM_MEMBER VALUES (1,1,1,'owner','2020-01-01')")
            db.execute("INSERT INTO USERS.STG_ROLE_GRANT VALUES (1,1,'admin','2020-01-01')")
            db.execute("INSERT INTO USERS.STG_SSO_IDENTITY VALUES (1,1,'oidc','subject','2020-01-01')")
            db.execute("INSERT INTO USERS.STG_USER_STATUS_HIST VALUES (1,1,'active','2020-01-01',NULL)")
            db.execute("INSERT INTO USERS.STG_LOGIN_EVENT VALUES (1,1,'2026-11-09 00:00:00','FAILED','web'), (2,1,'2026-11-09 23:59:59','SUCCESS','web'), (3,2,'2026-11-08 12:00:00','SUCCESS','web')")
            db.execute("INSERT INTO USERS.STG_USER_ACTIVITY_DAILY VALUES (7,1,'2026-10-01',9,8), (10000000002,2,'2026-10-01',5,4)")
        ready = set()
        assert local_sql.execute(db, USERS, ready, '20261109', 'users') == {}
        assert 'USERS.V_TEAM_MEMBERS' in ready
        assert db.execute('SELECT COUNT(*) FROM USERS.APP_USER').fetchone() == (int(populated),)
        if populated:
            assert db.execute('SELECT DISPLAY_NAME,EMAIL,STATUS_CD FROM USERS.APP_USER').fetchone() == (' Name ','Mixed@EXAMPLE','pending')
            for table in ('USER_PROFILE','TEAM','TEAM_MEMBER','ROLE_GRANT','SSO_IDENTITY','USER_STATUS_HIST'):
                assert db.execute('SELECT COUNT(*) FROM USERS.'+table).fetchone() == (1,)
            assert db.execute('SELECT ACTIVITY_ID,LOGIN_COUNT,DOCUMENT_COUNT FROM USERS.USER_ACTIVITY_DAILY ORDER BY 1').fetchall() == [(7,9,8),(10000000001,2,0)]
            assert db.execute('SELECT * FROM USERS.V_TEAM_MEMBERS').fetchall() == [(1,'Team',1,' Name ')]
        else:
            assert db.execute('SELECT * FROM USERS.USER_ACTIVITY_DAILY').fetchall() == []
        for statement in local_sql.statements(USERS/'20_routines.sql', '20261110', 'P_ACTIVITY_DAILY'):
            db.execute(statement.sql(dialect='duckdb'))
        assert db.execute('SELECT ACTIVITY_ID FROM USERS.USER_ACTIVITY_DAILY').fetchall() == ([(7,)] if populated else [])


def test_team_counts_uses_shipped_macro_and_counts_member_ids_not_users():
    source = report_outputs.source_queries('users')
    target = report_outputs.target_queries('users')
    assert set(source) == set(target) == {'M_TEAM_COUNTS_OUTPUT'}
    assert 'p_day' not in source['M_TEAM_COUNTS_OUTPUT'].lower()
    with duckdb.connect() as db:
        tables(db)
        db.execute('CREATE SCHEMA SFX_USERS')
        for table in ('TEAM','TEAM_MEMBER'):
            db.execute('CREATE VIEW SFX_USERS.'+table+' AS SELECT * FROM USERS.'+table)
        for populated in (False, True):
            if populated:
                db.execute("INSERT INTO USERS.TEAM VALUES (1,1,'Team',NULL),(2,2,'Empty',NULL)")
                db.execute('INSERT INTO USERS.TEAM_MEMBER VALUES (1,1,NULL,NULL,NULL),(2,1,3,NULL,NULL),(3,1,3,NULL,NULL)')
            actual = db.execute(target['M_TEAM_COUNTS_OUTPUT']).fetchall()
            assert sorted(actual) == sorted(db.execute(report_outputs.postgres_query(source['M_TEAM_COUNTS_OUTPUT'])).fetchall())
            assert sorted(actual) == ([(1,'Team',3),(2,'Empty',0)] if populated else [])


def test_users_declarations_and_provenance_exclude_retirement():
    estate = assess.build()
    objects = [o for o in estate['objects'] if o['subject_area'] == 'users']
    assert len(objects) == 55
    for obj in objects:
        if obj['system'] == 'spark':
            assert obj['output_relations'] == ['SFX_SPARK.'+obj['name'].upper()]
            continue
        assert obj['output_relations']
        p = provenance.provenance(obj)
        links = p['source'] + list(p['metrics'].values())
        for output in obj['output_relations']:
            assert bool(p['converted'][output]) == (obj['target_type'] != 'retire')
            links += p['converted'][output]
        for entry in links:
            assert '/blob/devin/sfg1120-integration/' in entry['url']
            assert 1 <= entry['start_line'] <= entry['end_line'] <= len((ROOT/entry['file']).read_text().splitlines())
    chain = next(o for o in objects if o['name'] == '10_activity_daily')
    assert chain['output_relations'] == ['SFX_USERS.USER_ACTIVITY_DAILY','SFX_USERS.M_TEAM_COUNTS_OUTPUT']


def test_users_ddl_matches_source_columns_widths_and_collations():
    source = (ROOT/'warehouse/teradata/ddl/users/00_tables.sql').read_text()
    target = {s.this.this.name: s for s in local_sql.statements(USERS/'00_tables.sql','20261109')}
    assert len(target) == 18
    for _, name, sql in assess.ddl_objects(source):
        name = name.split('.')[-1]
        if name in ('USER_PREF','STG_USER_PREF'):
            assert name not in target
            continue
        columns = {c.name: c for c in target[name].find_all(exp.ColumnDef)}
        definitions = re.findall(r'^\s+(\w+)\s+((?:VAR)?CHAR\((\d+)\)|BIGINT|INTEGER|TIMESTAMP\(0\)|DATE)([^\n]*)',sql,re.M)
        assert list(columns) == [c[0] for c in definitions]
        for column, kind, width, rest in definitions:
            rendered = columns[column].sql(dialect='snowflake')
            if width:
                if name == 'APP_USER' and column == 'DISPLAY_NAME':
                    width = '200'
                assert 'VARCHAR('+width+')' in rendered
                assert ("COLLATE 'en-ci-rtrim'" in rendered) == ('NOT CASESPECIFIC' in rest)
            assert ('NOT NULL' in rendered) == ('NOT NULL' in rest)


@pytest.mark.parametrize('source,target,passed', [('active   ','active',True),('Active','ACTIVE',False),(None,None,True)])
def test_users_char_only_padding_rules(source,target,passed):
    with duckdb.connect() as before, duckdb.connect() as after:
        for db,schema,value in ((before,'SFX_USERS',source),(after,'USERS',target)):
            db.execute('CREATE SCHEMA '+schema)
            db.execute('CREATE TABLE '+schema+'.APP_USER (USER_ID BIGINT,STATUS_CD VARCHAR,EMAIL VARCHAR)')
            db.execute('INSERT INTO '+schema+'.APP_USER VALUES (1,?,?)',[value,'user@example'])
        assert semantics.char_columns('SFX_USERS.APP_USER') == ['STATUS_CD']
        assert local_compare(before,after,'SFX_USERS.APP_USER','USERS.APP_USER')['passed'] == passed
        after.execute("UPDATE USERS.APP_USER SET EMAIL='user@example '")
        assert not local_compare(before,after,'SFX_USERS.APP_USER','USERS.APP_USER')['passed']


def test_users_errors_fail_closed_and_local_green_is_not_live(tmp_path):
    with duckdb.connect() as db:
        ready = {'USERS.T'}
        assert 'FileNotFoundError' in local_sql.execute(db,tmp_path,ready,'20261109','users')['*']
        assert not ready
    path = tmp_path/'20_routines.sql'
    path.write_text('')
    with pytest.raises(ValueError,match='Expected one P_ACTIVITY_DAILY'):
        list(local_sql.statements(path,'20261109','P_ACTIVITY_DAILY'))
    with pytest.raises(ValueError):
        list(local_sql.statements(USERS/'20_routines.sql','20260229','P_ACTIVITY_DAILY'))
    manifest = yaml.safe_load((ROOT/'migration/dw-exit/manifest.yaml').read_text())
    obj = next(o for o in manifest['objects'] if o['name'] == 'SFX_USERS.APP_USER')
    with duckdb.connect() as before, duckdb.connect() as after:
        tables(before,'SFX_USERS')
        tables(after)
        result = object_board.build_board({'objects':[obj]},before,after,{'USERS.APP_USER'})
        row = result['rows'][0]
        assert row['local_duckdb'] == 'green' and row['snowflake'] == 'red'
        assert row['snowflake_reason'] == object_board.SNOWFLAKE_REASON
        assert result['summary']['users']['local_green'] == 1
        assert result['summary']['users']['snowflake'] == 'red'
        assert '## Users parity provenance' in provenance.markdown(result['rows'])
        red = object_board.build_board({'objects':[obj]})['rows'][0]
        assert red['local_duckdb'] == 'red' and red['row_count'] is None


def test_users_materialize_uses_only_staging_and_runs_shipped_chain():
    with duckdb.connect() as before:
        tables(before,'SFX_USERS')
        before.execute("INSERT INTO SFX_USERS.STG_APP_USER VALUES (1,'Name','mail','active','2020-01-01')")
        names = {'SFX_USERS.'+r[0] for r in before.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='SFX_USERS'").fetchall()}
        after,ready,errors = object_board.materialize(before,names,USERS,subject='users')
        try:
            assert errors == {}
            assert after.execute('SELECT USER_ID FROM USERS.APP_USER').fetchall() == [(1,)]
            assert len(ready) == 19
            assert after.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name LIKE '%PREF%'").fetchone() == (0,)
        finally:
            after.close()


def test_users_implicit_source_truncation_remains_a_measured_mismatch():
    objects = [o for o in assess.build()['objects'] if o['name'] in
               ('SFX_USERS.APP_USER','01_load_users','m_SFX_APP_USER','s_m_SFX_APP_USER')]
    display_name = 'Name - Senior Workspace Operations and Records Governance Coordinator'
    with duckdb.connect() as before:
        tables(before,'SFX_USERS')
        before.execute("INSERT INTO SFX_USERS.STG_APP_USER VALUES (1,?,'mail','ACTIVE','2020-01-01')",[display_name])
        before.execute("INSERT INTO SFX_USERS.APP_USER SELECT USER_ID,LEFT(DISPLAY_NAME,60),EMAIL,STATUS_CD,CREATED_DT FROM SFX_USERS.STG_APP_USER")
        names = {'SFX_USERS.'+r[0] for r in before.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='SFX_USERS'").fetchall()}
        after,ready,errors = object_board.materialize(before,names,USERS,subject='users')
        try:
            assert errors == {}
            assert after.execute('SELECT DISPLAY_NAME FROM USERS.APP_USER').fetchone() == (display_name,)
            rows = object_board.build_board({'objects':objects},before,after,ready)['rows']
            assert len(rows) == 4
            for row in rows:
                assert row['local_duckdb'] == ('red' if row['kind'] in ('mapping','session') else 'approved_deviation')
                assert row['measurement_status'] == 'red'
                assert row['decision_state'] == 'approved'
                assert row['sampled_differences']['SFX_USERS.APP_USER']
        finally:
            after.close()
