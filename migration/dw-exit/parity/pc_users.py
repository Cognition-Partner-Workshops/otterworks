"""Execute users PC conversions against captured runner inputs, not BTEQ outputs."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import duckdb
from jinja2 import Environment, StrictUndefined, TemplateError
import psycopg
from psycopg import sql
import sqlglot
from sqlglot import exp

from warehouse.run_config import RunConfig
from .ladder import local_compare

ROOT = Path(__file__).resolve().parents[3]
ESTATE = ROOT/'etl/informatica'
MODELS = ROOT/'warehouse/dbt/models/pc/content'
MACROS = ROOT/'warehouse/dbt/macros'
TABLES = ('STG_APP_USER','APP_USER','LOGIN_EVENT','ROLE_GRANT','TEAM_MEMBER')
MAPPINGS = {'m_SFX_'+table: table for table in TABLES}
OUT = ROOT/'migration/dw-exit/.runs/pc-users-sessions'


def fingerprint(landing, day):
    paths = list((ESTATE/'repository/SFX_CONTENT').rglob('*.XML'))
    paths += list((ESTATE/'runner').glob('*.py')) + list((ESTATE/'params').glob('*.par'))
    paths += list(MODELS.glob('*.sql')) + list(MACROS.glob('*.sql'))
    paths += [landing/'users'/t/(day+'.psv') for t in TABLES if not t.startswith('STG_')]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def copy_table(pg, db, table, schema):
    with pg.cursor() as cursor:
        cursor.execute(sql.SQL('SELECT * FROM sfx_users.{}').format(sql.Identifier(table.lower())))
        rows = cursor.fetchall()
        kinds = {20:'BIGINT',23:'INTEGER',25:'VARCHAR',1042:'VARCHAR',1043:'VARCHAR',1082:'DATE',1114:'TIMESTAMP'}
        columns = ['"'+c.name.upper()+'" '+kinds[c.type_code] for c in cursor.description]
        name = schema+'.'+table
        db.execute('CREATE TABLE '+name+' ('+', '.join(columns)+')')
        if rows:
            db.executemany('INSERT INTO '+name+' VALUES ('+','.join('?' for _ in columns)+')',rows)


def capture(dsn, namespace, landing, day, out=OUT):
    """Run the documented pmcmd CLI, restoring only the five local target tables."""
    if psycopg.conninfo.conninfo_to_dict(dsn).get('host') not in ('localhost','127.0.0.1'):
        raise ValueError('PC capture restricted to local PostgreSQL')
    out.mkdir(parents=True,exist_ok=True)
    path = out/'capture.duckdb'
    if path.exists():
        raise FileExistsError('Refusing to overwrite PC capture: '+str(path))
    inputs = fingerprint(landing,day)
    environment = dict(os.environ, RUN_TOKEN=RunConfig.from_env().token, NS=namespace,
                       LANDING_DIR=str(landing), PMROOTDIR=str(out/'runner'))
    params = psycopg.conninfo.conninfo_to_dict(dsn)
    environment.update(TD_HOST=params['host'],TD_PORT=params.get('port','5432'),
                       TD_DB=params.get('dbname','teradata'),TD_USER=params.get('user','postgres'))
    if params.get('password'):
        environment['TD_PASSWORD'] = params['password']
    command = [sys.executable,'-m','runner','startworkflow','-f','SFX_CONTENT',
               '-mappings',','.join(MAPPINGS),'wf_SFX_CONTENT_DAILY']
    with psycopg.connect(dsn,autocommit=True) as pg, duckdb.connect(str(path)) as db:
        db.execute('CREATE SCHEMA INITIAL; CREATE SCHEMA SFX_USERS')
        for table in TABLES:
            pg.execute(sql.SQL('CREATE TEMP TABLE {} AS SELECT * FROM sfx_users.{}').format(
                sql.Identifier('pc_backup_'+table.lower()),sql.Identifier(table.lower())))
            copy_table(pg,db,table,'INITIAL')
        try:
            result = subprocess.run(command,cwd=ESTATE,env=environment,text=True,capture_output=True)
            (out/'runner.stdout').write_text(result.stdout+'\n'+result.stderr)
            if result.returncode:
                raise RuntimeError('PC workflow failed; see '+str(out/'runner.stdout'))
            session_command = [sys.executable,'-m','runner','startsession','-f','SFX_CONTENT',
                               '-w','wf_SFX_CONTENT_DAILY','s_m_SFX_TEAM_MEMBER']
            session = subprocess.run(session_command,cwd=ESTATE,env=environment,text=True,capture_output=True)
            with (out/'runner.stdout').open('a') as handle:
                handle.write(session.stdout+'\n'+session.stderr)
            if session.returncode:
                raise RuntimeError('PC standalone session failed; see '+str(out/'runner.stdout'))
            for table in TABLES:
                copy_table(pg,db,table,'SFX_USERS')
        finally:
            with pg.transaction():
                for table in TABLES:
                    pg.execute(sql.SQL('DELETE FROM sfx_users.{}').format(sql.Identifier(table.lower())))
                    pg.execute(sql.SQL('INSERT INTO sfx_users.{} SELECT * FROM {}').format(
                        sql.Identifier(table.lower()),sql.Identifier('pc_backup_'+table.lower())))
    if inputs != fingerprint(landing,day):
        raise ValueError('PC inputs changed during capture')
    metadata = dict(run_token=RunConfig.from_env().token,namespace=namespace,business_date=day,
                    inputs=inputs,command=command,standalone_command=session_command,returncode=result.returncode,
                    input_policy='independent mapping proofs; APP_USER reads captured actual PC STG_APP_USER, other mappings read the same landing PSVs',
                    team_member_execution='standalone session; workflow task is disabled in source XML',
                    capture_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    stdout_sha256=hashlib.sha256((out/'runner.stdout').read_bytes()).hexdigest())
    (out/'capture.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(result.stdout)


def model_query(table, connection, config):
    environment = Environment(undefined=StrictUndefined)
    def configure(**kwargs):
        config.update(kwargs)
        return ''
    environment.globals.update(config=configure, source=lambda area,name:'INPUT.'+name,
                               ref=lambda name:'INPUT.'+name.removeprefix('pc_content__').upper())
    paths = list(MACROS.glob('pc_content*.sql')) + list(MACROS.glob('unt8*.sql'))
    text = '\n'.join(p.read_text() for p in sorted(paths))
    template = text+'\n'+(MODELS/('pc_content__'+table.lower()+'.sql')).read_text()
    rendered = environment.from_string(template).render()
    query = sqlglot.parse_one(rendered,read='snowflake')
    for node in list(query.find_all(exp.ArrayToString)):
        mapping = node.find(exp.ParseJSON)
        characters = node.find(exp.RegexpExtractAll)
        if mapping is None or characters is None or characters.expression.this != '.':
            raise ValueError('Unsupported PC array expression')
        values = json.loads(mapping.this.this)
        connection.create_function('pc_mapped_upper',lambda value: ''.join(values.get(c,c) for c in value),
                                   ['VARCHAR'],'VARCHAR')
        node.replace(exp.Anonymous(this='pc_mapped_upper',expressions=[characters.this.copy()]))
    for node in list(query.find_all(exp.Anonymous)):
        if node.name.upper() == 'TRY_TO_DECIMAL':
            value,precision,scale = node.expressions
            node.replace(exp.TryCast(this=value.copy(),to=exp.DataType.build('DECIMAL('+precision.this+','+scale.this+')')))
    for node in list(query.find_all(exp.TsOrDsToDate)):
        if node.args.get('safe'):
            if node.args.get('format').this != '%Y-%m-%d':
                raise ValueError('Unsupported PC date parse format')
            node.replace(exp.TryCast(this=node.this.copy(),to=exp.DataType.build('DATE')))
    for node in list(query.find_all(exp.RegexpExtract)):
        node.replace(exp.Nullif(this=node.copy(),expression=exp.Literal.string('')))
    for node in list(query.find_all(exp.ToChar)):
        if node.args['format'].this != 'YYYY-MM-DD':
            raise ValueError('Unsupported PC date format')
        node.replace(exp.TimeToStr(this=node.this.copy(),format=exp.Literal.string('%Y-%m-%d')))
    return query.sql(dialect='duckdb')


def load_inputs(db, captured, landing, day):
    db.execute('CREATE SCHEMA INPUT; CREATE SCHEMA USERS')
    for table in TABLES:
        if table == 'STG_APP_USER':
            rows = captured.execute('SELECT * FROM SFX_USERS.STG_APP_USER').fetchall()
            definitions = captured.execute('DESCRIBE SFX_USERS.STG_APP_USER').fetchall()
        else:
            with (landing/'users'/table/(day+'.psv')).open() as handle:
                rows = [tuple(v if v else None for v in row) for row in csv.reader(handle,delimiter='|')]
            definitions = captured.execute('DESCRIBE INITIAL.'+table).fetchall()
        db.execute('CREATE TABLE INPUT.'+table+' ('+', '.join('"'+c[0]+'" '+c[1] for c in definitions)+')')
        if rows:
            db.executemany('INSERT INTO INPUT.'+table+' VALUES ('+','.join('?' for _ in definitions)+')',rows)
        initial = captured.execute('SELECT * FROM INITIAL.'+table).fetchall()
        db.execute('CREATE TABLE USERS.'+table+' ('+', '.join('"'+c[0]+'" '+c[1] for c in definitions)+')')
        if initial:
            db.executemany('INSERT INTO USERS.'+table+' VALUES ('+','.join('?' for _ in definitions)+')',initial)


def execute_model(db,table):
    config = {}
    query = model_query(table,db,config)
    db.execute('CREATE OR REPLACE TABLE CANDIDATES AS '+query)
    if config['materialized'] == 'table':
        db.execute('DELETE FROM USERS.'+table)
        db.execute('INSERT INTO USERS.'+table+' SELECT * FROM CANDIDATES')
    else:
        columns = [c[0] for c in db.execute('DESCRIBE CANDIDATES').fetchall()]
        if config['materialized'] != 'incremental' or config['incremental_strategy'] != 'merge':
            raise ValueError('Unsupported PC model materialization')
        key = config['unique_key']
        if key not in columns:
            raise ValueError('PC merge key not in projection')
        db.execute('MERGE INTO USERS.'+table+' t USING CANDIDATES s ON t.'+key+'=s.'+key+
                   ' WHEN MATCHED THEN UPDATE SET '+','.join(c+'=s.'+c for c in columns[1:])+
                   ' WHEN NOT MATCHED THEN INSERT ('+','.join(columns)+') VALUES ('+','.join('s.'+c for c in columns)+')')


def proofs(namespace,landing,day,out=OUT):
    metadata = json.loads((out/'capture.json').read_text())
    if metadata['returncode'] != 0:
        raise ValueError('PC source execution was unsuccessful')
    if (metadata['run_token'],metadata['namespace'],metadata['business_date']) != (RunConfig.from_env().token,namespace,day):
        raise ValueError('PC evidence scope differs')
    if metadata['inputs'] != fingerprint(landing,day):
        raise ValueError('PC evidence inputs changed; capture again in a new directory')
    for name,key in [('capture.duckdb','capture_sha256'),('runner.stdout','stdout_sha256')]:
        if hashlib.sha256((out/name).read_bytes()).hexdigest() != metadata[key]:
            raise ValueError('PC evidence checksum differs: '+name)
    results = {}
    with duckdb.connect(str(out/'capture.duckdb'),read_only=True) as captured, duckdb.connect() as converted:
        load_inputs(converted,captured,landing,day)
        for mapping,table in MAPPINGS.items():
            try:
                execute_model(converted,table)
                measurement = local_compare(captured,converted,'SFX_USERS.'+table,'USERS.'+table)
                results[mapping] = dict(status='green' if measurement['passed'] else 'red',
                    reason=None if measurement['passed'] else 'PowerCenter runner / shipped dbt parity mismatch',
                    measurement=measurement)
            except (ValueError,duckdb.Error,sqlglot.errors.SqlglotError,TemplateError) as error:
                results[mapping] = dict(status='red',reason='PC conversion execution failed: '+str(error),measurement=None)
    return results, metadata


def router_probe(dsn, namespace, landing, day):
    out = OUT/'router-probe'
    probe_landing = OUT/'router-landing'
    probe_landing.mkdir(parents=True,exist_ok=False)
    for table in TABLES:
        if not table.startswith('STG_'):
            directory = probe_landing/'users'/table
            directory.mkdir(parents=True)
            shutil.copyfile(landing/'users'/table/(day+'.psv'),directory/(day+'.psv'))
    with (probe_landing/'users/LOGIN_EVENT'/(day+'.psv')).open('a') as handle:
        timestamp = datetime.strptime(day,'%Y%m%d').strftime('%Y-%m-%d 12:00:00')
        for index,code in enumerate(('UNROUTED','FAILED','LOCKED','MFA_FAILED')):
            handle.write(f'{9900000000+index}|1|{timestamp}|{code}|WEB\n')
    capture(dsn,namespace,probe_landing,day,out)
    results,metadata = proofs(namespace,probe_landing,day,out)
    (out/'proofs.json').write_text(json.dumps(dict(results=results,evidence=metadata),default=str,indent=2)+'\n')
    return results['m_SFX_LOGIN_EVENT']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture',action='store_true')
    parser.add_argument('--router-probe',action='store_true')
    parser.add_argument('--dsn',required=True)
    parser.add_argument('--namespace',required=True)
    parser.add_argument('--landing',type=Path,default=ROOT/'warehouse/landing')
    parser.add_argument('--business-date',default='20261109')
    parser.add_argument('--output',type=Path,default=OUT)
    args = parser.parse_args()
    if args.router_probe:
        print(json.dumps(router_probe(args.dsn,args.namespace,args.landing,args.business_date),default=str,indent=2))
    elif args.capture:
        capture(args.dsn,args.namespace,args.landing,args.business_date,args.output)
    else:
        print(json.dumps(proofs(args.namespace,args.landing,args.business_date,args.output)[0],default=str,indent=2))
