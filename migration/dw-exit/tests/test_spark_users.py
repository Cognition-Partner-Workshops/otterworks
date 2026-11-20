import ast
import math
import os
from pathlib import Path

import duckdb
import pytest

import assess
from parity import object_board, provenance, spark_billing, spark_users
from parity.ladder import local_compare

ROOT = Path(__file__).resolve().parents[3]
JOBS = ['team_graph_components','user_pref_json_flatten','users_active_daily',
        'users_login_useragent_parse','users_risk_score','users_team_rollup']


@pytest.mark.parametrize('populated',[False,True])
def test_shipped_preference_body_preserves_python_defaults_and_values(populated):
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA SPARK_INPUT; CREATE TABLE SPARK_INPUT.USER_PREF (USER_PREF_ID BIGINT,USER_ID BIGINT,PREF_JSON VARCHAR)')
        if populated:
            db.execute('INSERT INTO SPARK_INPUT.USER_PREF VALUES (1,1,?),(2,1,?),(3,1,NULL),(4,1,?)',
                       ['{"theme": true, "notifications": null, "locale": 7}','{}','broken'])
        rows = db.execute(spark_users.snowpark_query(db,'user_pref_json_flatten')).fetchall()
        assert [r[-3:] for r in rows] == ([('True','None','7'),('','',''),('','',''),(None,None,None)] if populated else [])


@pytest.mark.parametrize('populated',[False,True])
def test_shipped_browser_body_fallback_and_regex(populated):
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA SPARK_INPUT; CREATE TABLE SPARK_INPUT.LOGIN_EVENT (LOGIN_EVENT_ID BIGINT,USER_ID BIGINT,EVENT_AT TIMESTAMP,IP_ADDRESS VARCHAR,USER_AGENT VARCHAR,RAW_LINE VARCHAR)')
        if populated:
            db.execute("INSERT INTO SPARK_INPUT.LOGIN_EVENT (LOGIN_EVENT_ID,USER_AGENT) VALUES (1,NULL),(2,'curl/1'),(3,'agent Firefox/20 other Chrome/99')")
        rows = db.execute(spark_users.snowpark_query(db,'users_login_useragent_parse')).fetchall()
        assert [r[-1] for r in rows] == (['Other','Other','Firefox/20'] if populated else [])


@pytest.mark.parametrize('populated',[False,True])
def test_shipped_risk_body_exact_double_and_nulls(populated):
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA SPARK_INPUT; CREATE TABLE SPARK_INPUT.USER_ACTIVITY_DAILY (USER_ACTIVITY_ID BIGINT,USER_ID BIGINT,ACTIVITY_DATE DATE,LOGIN_COUNT BIGINT,ACTION_COUNT BIGINT)')
        if populated:
            db.execute('INSERT INTO SPARK_INPUT.USER_ACTIVITY_DAILY (LOGIN_COUNT,ACTION_COUNT) VALUES (10,20),(NULL,1)')
        rows = db.execute(spark_users.snowpark_query(db,'users_risk_score')).fetchall()
        assert [r[-1] for r in rows] == ([1/(1+math.exp(-(-2.1+10*0.0004-20*0.0001))),None] if populated else [])


@pytest.mark.parametrize('populated',[False,True])
def test_shipped_graph_body_six_iterations_not_convergence(populated):
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA SPARK_INPUT; CREATE TABLE SPARK_INPUT.TEAM_MEMBER (TEAM_ID BIGINT,USER_ID BIGINT)')
        if populated:
            db.executemany('INSERT INTO SPARK_INPUT.TEAM_MEMBER VALUES (?,?)',[(team,user) for team in range(8) for user in (team,team+1)]+[(99,99),(99,99)])
        rows = dict(db.execute(spark_users.snowpark_query(db,'team_graph_components')).fetchall())
        assert rows == ({user:max(0,user-6) for user in range(9)} if populated else {})


@pytest.mark.parametrize('name',['users_active_daily','users_team_rollup'])
@pytest.mark.parametrize('populated',[False,True])
def test_shipped_dbt_matches_source_sql(name,populated):
    tree = ast.parse((ROOT/'etl/spark/jobs/py'/(name+'.py')).read_text())
    source = next(n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr == 'sql')
    model = (ROOT/'warehouse/dbt/models/spark'/name/(name+'.sql')).read_text()
    with duckdb.connect() as db:
        db.execute('CREATE SCHEMA SPARK_INPUT; CREATE TABLE SPARK_INPUT.USER_ACTIVITY_DAILY (ACTIVITY_DATE DATE,USER_ID BIGINT,LOGIN_COUNT BIGINT,ACTION_COUNT BIGINT)')
        db.execute('CREATE TABLE SPARK_INPUT.TEAM (TEAM_ID BIGINT,TEAM_NAME VARCHAR); CREATE TABLE SPARK_INPUT.TEAM_MEMBER (TEAM_ID BIGINT,USER_ID BIGINT); CREATE TABLE SPARK_INPUT.APP_USER (USER_ID BIGINT)')
        for table in ('USER_ACTIVITY_DAILY','TEAM','TEAM_MEMBER','APP_USER'):
            db.execute('CREATE VIEW '+table+' AS SELECT * FROM SPARK_INPUT.'+table)
        if populated:
            db.execute("INSERT INTO SPARK_INPUT.USER_ACTIVITY_DAILY VALUES ('2026-11-09',1,2,3),('2026-11-09',1,NULL,4)")
            db.execute("INSERT INTO SPARK_INPUT.TEAM VALUES (1,'members'),(2,'empty'); INSERT INTO SPARK_INPUT.TEAM_MEMBER VALUES (1,1),(1,1); INSERT INTO SPARK_INPUT.APP_USER VALUES (1),(1)")
        query = spark_billing.render_model(model.replace("'spark_users'","'spark_billing'"))
        assert sorted(db.execute(query).fetchall()) == sorted(db.execute(source).fetchall())


def test_users_spark_declarations_and_provenance():
    objects = {obj['name']:obj for obj in object_board.relation_contract(assess.build()['objects'])}
    for name in JOBS:
        obj = objects[name]
        assert obj['output_relations'] == ['SFX_SPARK.'+name.upper()]
        assert obj['target_type'] == 'dbt_model'
        p = provenance.provenance(obj)
        assert p['converted'][obj['output_relations'][0]]
        assert all('devin/sfx1119-users-migration' in link['url'] for links in p['converted'].values() for link in links)


def test_missing_snowpark_body_fails_closed(tmp_path,monkeypatch):
    path = tmp_path/'warehouse/snowpark/users_risk_score.py'
    path.parent.mkdir(parents=True)
    path.write_text('def run(session):\n    pass\n')
    monkeypatch.setattr(spark_users,'ROOT',tmp_path)
    with duckdb.connect() as db, pytest.raises(ValueError,match='one shipped Python UDF body'):
        spark_users.snowpark_query(db,'users_risk_score')


def test_materialization_missing_stale_and_actual_parquet(tmp_path,monkeypatch):
    name = 'users_active_daily'
    model = Path('warehouse/dbt/models/spark')/name/(name+'.sql')
    (tmp_path/model).parent.mkdir(parents=True)
    (tmp_path/model).write_text((ROOT/model).read_text())
    runtime = tmp_path/'etl/spark/.data/test'
    landing = runtime/'landing/users/USER_ACTIVITY_DAILY/input.psv'
    landing.parent.mkdir(parents=True)
    landing.write_text('USER_ACTIVITY_ID|USER_ID|ACTIVITY_DATE|LOGIN_COUNT|ACTION_COUNT\n1|1|2026-11-09|2|3\n')
    obj = dict(name=name,system='spark',subject_area='users')
    monkeypatch.setattr(spark_users,'ROOT',tmp_path)
    with duckdb.connect() as before, duckdb.connect() as after:
        ready,errors,evidence = spark_users.materialize(before,after,[obj],'test')
        assert not ready and not evidence
        assert 'Missing Spark parquet' in errors['SPARK.USERS_ACTIVE_DAILY']
    output = runtime/'lake/users/users_active_daily/part.parquet'
    output.parent.mkdir(parents=True)
    with duckdb.connect() as db:
        db.execute("COPY (SELECT DATE '2026-11-09' ACTIVITY_DATE,1 ACTIVE_USERS,2 LOGINS,3 ACTIONS) TO ? (FORMAT PARQUET)",[str(output)])
    with duckdb.connect() as before, duckdb.connect() as after:
        ready,errors,evidence = spark_users.materialize(before,after,[obj],'test')
        assert ready == {'SPARK.USERS_ACTIVE_DAILY'} and not errors
        assert evidence[name]['landing_sha256']
        assert local_compare(before,after,'SFX_SPARK.USERS_ACTIVE_DAILY','SPARK.USERS_ACTIVE_DAILY')['passed']
    os.utime(output,(0,0))
    with duckdb.connect() as before, duckdb.connect() as after:
        ready,errors,evidence = spark_users.materialize(before,after,[obj],'test')
        assert not ready and not evidence
        assert 'predates landing inputs' in errors['SPARK.USERS_ACTIVE_DAILY']
