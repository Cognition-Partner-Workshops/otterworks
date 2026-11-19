import argparse
import os
from pathlib import Path

from pyspark.sql import functions as F

from lakehouse.runtime.ingest import business_date
from lakehouse.runtime.layout import ROOT, delta_path
from lakehouse.runtime.session import create_session


FEEDS = {
    'audit_event': ('audit', 'AUDIT_EVENT_ID long, ACTOR_USER_ID long, DOCUMENT_ID long, EVENT_TYPE string, EVENT_AT timestamp, DETAILS string'),
    'audit_event_archive': ('audit', 'AUDIT_EVENT_ARCHIVE_ID long, ACTOR_USER_ID long, DOCUMENT_ID long, EVENT_TYPE string, EVENT_AT timestamp, DETAILS string'),
    'compliance_flag': ('audit', 'COMPLIANCE_FLAG_ID long, DOCUMENT_ID long, USER_ID long, FLAG_TYPE string, SEVERITY long, STATUS string'),
    'security_alert': ('audit', 'SECURITY_ALERT_ID long, USER_ID long, EVENT_AT timestamp, ALERT_TYPE string, SCORE decimal(18,2)'),
    'user_activity_daily': ('users', 'USER_ACTIVITY_ID long, USER_ID long, ACTIVITY_DATE date, LOGIN_COUNT long, ACTION_COUNT long'),
    'login_event': ('users', 'LOGIN_EVENT_ID long, USER_ID long, EVENT_AT timestamp, IP_ADDRESS string, USER_AGENT string, RAW_LINE string'),
}

QUERIES = {
    'audit_daily_summary': """
        select to_date(EVENT_AT) EVENT_DATE, EVENT_TYPE, count(*) EVENT_COUNT,
               count(distinct ACTOR_USER_ID) ACTORS
        from audit_spark_audit_event group by to_date(EVENT_AT), EVENT_TYPE
    """,
    'audit_actor_activity_join': """
        with activity as (
            select case when LOGIN_COUNT > 12 then 0 else USER_ID end USER_KEY,
                   ACTIVITY_DATE, sum(LOGIN_COUNT) LOGIN_COUNT, sum(ACTION_COUNT) ACTION_COUNT
            from audit_spark_user_activity_daily
            group by case when LOGIN_COUNT > 12 then 0 else USER_ID end, ACTIVITY_DATE
        ), logins as (
            select case when hour(EVENT_AT) < 8 then 0 else USER_ID end USER_KEY,
                   max(USER_AGENT) USER_AGENT,
                   concat_ws('\n', collect_list(RAW_LINE)) LOGIN_TEXT
            from audit_spark_login_event
            group by case when hour(EVENT_AT) < 8 then 0 else USER_ID end
        )
        select coalesce(a.ACTOR_USER_ID, 0) USER_KEY, a.AUDIT_EVENT_ID,
               a.EVENT_AT, d.ACTIVITY_DATE, d.ACTION_COUNT, l.USER_AGENT,
               octet_length(l.LOGIN_TEXT) LOGIN_TEXT_BYTES
        from audit_spark_audit_event a
        join activity d on coalesce(a.ACTOR_USER_ID, 0) = d.USER_KEY
        join logins l on coalesce(a.ACTOR_USER_ID, 0) = l.USER_KEY
    """,
    'audit_archive_resort': """
        select * from audit_spark_audit_event_archive
        order by EVENT_TYPE, EVENT_AT, AUDIT_EVENT_ARCHIVE_ID
    """,
    'security_alert_anomaly': """
        with scored as (
            select SECURITY_ALERT_ID ALERT_ID, USER_ID, cast(SCORE as double) SCORE
            from audit_spark_security_alert
        ), stats as (
            select count(*) n, sum(SCORE) total, sum(SCORE*SCORE) squares from scored
        ), moments as (
            select total/greatest(n,1) mean,
                   sqrt(greatest(squares/greatest(n,1)-pow(total/greatest(n,1),2),0)) sd
            from stats
        )
        select ALERT_ID, USER_ID, SCORE,
               (SCORE-mean)/(case when sd=0 then 1.0 else sd end) Z_SCORE
        from scored cross join moments
    """,
    'compliance_flag_rules': """
        select COMPLIANCE_FLAG_ID FLAG_ID, DOCUMENT_ID, cast(SEVERITY as int) SEVERITY,
               case when STATUS='closed' then 'resolved'
                    when SEVERITY >= 7000 then 'review' else 'monitor' end DISPOSITION
        from audit_spark_compliance_flag
    """,
}


def publish(frame, layer, name):
    path = delta_path(layer, 'audit', name)
    frame.write.format('delta').mode('overwrite').option('overwriteSchema', 'true').save(str(path))
    frame.sparkSession.sql(
        f"CREATE TABLE IF NOT EXISTS {layer}_audit.{name} USING DELTA LOCATION '{path.as_uri()}'")


def ingest(spark, landing, day):
    batch = business_date(day)
    for name, (domain, schema) in FEEDS.items():
        directory = Path(landing) / domain / name.upper()
        files = sorted(directory.glob('*.psv'))
        if not files:
            raise FileNotFoundError(f'No Spark landing files: {directory}')
        frame = (spark.read.option('header', True).option('sep', '|').option('escape', '"')
                 .option('mode', 'FAILFAST').schema(schema).csv([str(path) for path in files]))
        frame = frame.withColumn('_business_date', F.lit(batch)).withColumn('_source_file', F.input_file_name())
        publish(frame, 'bronze', 'spark_' + name)


def build(spark, day):
    batch = business_date(day)
    for name in FEEDS:
        (spark.table('bronze_audit.spark_' + name).where(F.col('_business_date') == F.lit(batch))
         .drop('_business_date', '_source_file').createOrReplaceTempView('audit_spark_' + name))
    for name, query in QUERIES.items():
        publish(spark.sql(query), 'gold', 'spark_' + name)


def compact(spark):
    spark.sql('OPTIMIZE gold_audit.spark_audit_daily_summary').collect()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--business-date', required=True)
    parser.add_argument('--compact', action='store_true')
    args = parser.parse_args()
    business_date(args.business_date)
    spark = create_session()
    try:
        if args.compact:
            compact(spark)
        else:
            landing = Path(os.environ.get('AUDIT_SPARK_LANDING', ROOT.parent / 'etl/spark/.data'
                                           / os.environ.get('LEGACY_NS', 'sfx-d1110-before') / 'landing'))
            ingest(spark, landing, args.business_date)
            build(spark, args.business_date)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
