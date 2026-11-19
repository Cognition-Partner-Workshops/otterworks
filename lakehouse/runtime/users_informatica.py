"""Independent Delta targets for the users mappings in SFX_CONTENT."""

import argparse
from contextlib import contextmanager

from delta.tables import DeltaTable
from pyspark.sql import functions as F

from .ingest import business_date
from .layout import delta_path
from .session import create_session


def source(spark, table, day):
    frame = spark.table(f'bronze_users.{table}').where(F.col('_business_date') == F.lit(day))
    return frame.select(*(F.when(F.col(name) != '', F.col(name)).alias(name)
                          for name in frame.columns if not name.startswith('_')))


def bigint(name):
    return F.when(F.length(F.trim(F.col(name))) > 0, F.col(name).cast('bigint')).alias(name)


def code(name):
    return F.upper(F.trim(F.col(name))).alias(name)


@contextmanager
def validate_keys(frame, table, key):
    frame = frame.cache()
    try:
        if (frame.groupBy(key).count().where(F.col(key).isNull() | (F.col('count') > 1)).take(1)):
            raise ValueError(f'{table}: missing or duplicate {key}; no rows applied')
        yield frame
    finally:
        frame.unpersist()


def store(spark, frame, table, key, *, merge=False, validate=True):
    path = delta_path('silver', 'users', table)
    name = f'silver_users.{table}'

    def publish(rows):
        if merge and DeltaTable.isDeltaTable(spark, str(path)):
            (DeltaTable.forPath(spark, str(path)).alias('target')
             .merge(rows.alias('source'), f'target.{key} = source.{key}')
             .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
        else:
            rows.write.format('delta').mode('overwrite').save(str(path))
        spark.sql(f"CREATE TABLE IF NOT EXISTS {name} USING DELTA LOCATION '{path.as_uri()}'")

    if validate:
        with validate_keys(frame, table, key) as rows:
            publish(rows)
    else:
        publish(frame)


def app(spark, day):
    raw = source(spark, 'app_user', day)
    stage = raw.select(bigint('user_id'),
                       F.trim(F.substring('display_name', 1, 60)).alias('display_name'),
                       F.lower(F.trim(F.substring('email', 1, 120))).alias('email'),
                       F.upper(F.trim(F.substring('status_cd', 1, 12))).alias('status_cd'),
                       F.to_date('created_dt', 'yyyy-MM-dd').alias('created_dt'))
    store(spark, stage, 'infa_stg_app_user', 'user_id', validate=False)
    store(spark, spark.table('silver_users.infa_stg_app_user'), 'infa_app_user', 'user_id', merge=True)


def roles(spark, day):
    grants = source(spark, 'role_grant', day).select(
        bigint('grant_id'), bigint('user_id'), code('role_cd'),
        F.to_date('granted_dt', 'yyyy-MM-dd').alias('granted_dt'))
    store(spark, grants, 'infa_role_grant', 'grant_id')


def events(spark, day):
    logins = source(spark, 'login_event', day).select(
        bigint('login_id'), bigint('user_id'), F.to_timestamp('login_ts', 'yyyy-MM-dd HH:mm:ss').alias('login_ts'),
        code('result_cd'), code('client_type')).where(F.col('result_cd').isin('SUCCESS', 'FAILED', 'LOCKED', 'MFA_FAILED'))
    store(spark, logins, 'infa_login_event', 'login_id', merge=True)


def members(spark, day):
    members = source(spark, 'team_member', day).select(
        bigint('team_member_id'), bigint('team_id'), bigint('user_id'), code('role_cd'),
        F.to_date('joined_dt', 'yyyy-MM-dd').alias('joined_dt'))
    store(spark, members, 'infa_team_member', 'team_member_id', merge=True)


def main():
    operations = {'app': app, 'roles': roles, 'events': events, 'members': members}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=operations, required=True)
    parser.add_argument('--business-date', required=True)
    args = parser.parse_args()
    day = business_date(args.business_date)
    spark = create_session()
    try:
        operations[args.stage](spark, day)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
