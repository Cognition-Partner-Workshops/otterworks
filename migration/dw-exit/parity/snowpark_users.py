"""Run the shipped APP_USER handler only with Snowpark's in-process emulator."""
import hashlib

import duckdb

from warehouse.snowpark.m_sfx_app_user import run
from . import owner_decisions, pc_users
from .ladder import local_compare


def execute(initial, staging):
    from snowflake.snowpark import Session
    from snowflake.snowpark.types import StructType, StructField, LongType, StringType, DateType
    schema = StructType([StructField('USER_ID',LongType()), StructField('DISPLAY_NAME',StringType(200)),
        StructField('EMAIL',StringType()), StructField('STATUS_CD',StringType()), StructField('CREATED_DT',DateType())])
    with Session.builder.config('local_testing', True).create() as session:
        session.create_dataframe(initial,schema).write.save_as_table(['SFX_USERS','APP_USER'],mode='overwrite')
        session.create_dataframe(staging,schema).write.save_as_table(['SFX_USERS','STG_APP_USER'],mode='overwrite')
        changed = run(session)
        return [tuple(row) for row in session.table(['SFX_USERS','APP_USER']).collect()], changed


def proof(namespace, landing, day):
    pc_results, metadata = pc_users.proofs(namespace,landing,day)
    with duckdb.connect(str(pc_users.OUT/'capture.duckdb'),read_only=True) as before, duckdb.connect() as after:
        initial = before.execute('SELECT * FROM INITIAL.APP_USER').fetchall()
        staging = before.execute('SELECT * FROM SFX_USERS.STG_APP_USER').fetchall()
        rows, changed = execute(initial,staging)
        after.execute('CREATE SCHEMA USERS; CREATE TABLE USERS.APP_USER (USER_ID BIGINT,DISPLAY_NAME VARCHAR,EMAIL VARCHAR,STATUS_CD VARCHAR,CREATED_DT DATE)')
        if rows:
            after.executemany('INSERT INTO USERS.APP_USER VALUES (?,?,?,?,?)',rows)
        measurement = local_compare(before,after,'SFX_USERS.APP_USER','USERS.APP_USER')
        output_scope = owner_decisions.display_names(before,after,'SFX_USERS.APP_USER','USERS.APP_USER')
        input_scope = pc_results['m_SFX_STG_APP_USER']['owner_decision']
        output_scope['scope_valid'] &= input_scope['scope_valid']
        return dict(status='green' if measurement['passed'] and input_scope['scope_valid'] else 'red',measurement=measurement,
            owner_decision=output_scope, input_owner_decision=input_scope,
            mode='Session.builder.config("local_testing", True).create()', changed_rows=changed,
            capture_sha256=metadata['capture_sha256'],
            handler_sha256=hashlib.sha256((pc_users.ROOT/'warehouse/snowpark/m_sfx_app_user.py').read_bytes()).hexdigest())
