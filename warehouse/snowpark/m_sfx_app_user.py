"""TRANSFORM.M_SFX_APP_USER: keyed lookup/update strategy from PowerCenter."""
from snowflake.snowpark.functions import col, substring, when_matched, when_not_matched


def run(session) -> int:
    database = session.get_current_database()
    target = session.table([database, 'USERS', 'APP_USER'])
    source = session.table([database, 'USERS', 'STG_APP_USER']).select(
        col('USER_ID'), col('DISPLAY_NAME').cast('varchar(200)').alias('DISPLAY_NAME'),
        substring(col('EMAIL'), 1, 120).alias('EMAIL'),
        substring(col('STATUS_CD'), 1, 12).alias('STATUS_CD'), col('CREATED_DT'))
    values = {name:source[name] for name in ('USER_ID','DISPLAY_NAME','EMAIL','STATUS_CD','CREATED_DT')}
    result = target.merge(source, target['USER_ID'] == source['USER_ID'], [
        when_matched().update({name:value for name,value in values.items() if name != 'USER_ID'}),
        when_not_matched().insert(values),
    ])
    return result.rows_inserted + result.rows_updated


def register(session, stage_location):
    return session.sproc.register(run, name=['TRANSFORM','M_SFX_APP_USER'],
        is_permanent=True, stage_location=stage_location, replace=True,
        packages=['snowflake-snowpark-python'], execute_as='owner')
