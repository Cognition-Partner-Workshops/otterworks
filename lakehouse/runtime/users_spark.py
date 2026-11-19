"""Move the six Spark users jobs from raw PSV/Parquet/JDBC to typed reads and Delta."""

import argparse
import json
from pathlib import Path

from pyspark.sql import functions as F

from .layout import delta_path
from .session import create_session


INPUTS = {
    'app_user': 'user_id LONG, email STRING, display_name STRING, created_at TIMESTAMP, status STRING',
    'team': 'team_id LONG, owner_user_id LONG, team_name STRING',
    'team_member': 'team_member_id LONG, team_id LONG, user_id LONG, role STRING',
    'login_event': 'login_event_id LONG, user_id LONG, event_at TIMESTAMP, ip_address STRING, user_agent STRING, raw_line STRING',
    'user_activity_daily': 'user_activity_id LONG, user_id LONG, activity_date DATE, login_count LONG, action_count LONG',
    'user_pref': 'user_pref_id LONG, user_id LONG, pref_json STRING',
}


def read_inputs(spark, directory):
    feeds = {}
    for table, schema in INPUTS.items():
        paths = sorted((directory / 'users' / table.upper()).glob('*.psv'))
        if not paths:
            raise FileNotFoundError(f'Missing Spark landing: {directory}/users/{table.upper()}/*.psv')
        feeds[table] = (spark.read.schema(schema).option('header', True).option('sep', '|')
                        .option('escape', '"').option('enforceSchema', False).csv([str(path) for path in paths]))
    return feeds


def preferences(raw):
    try:
        payload = json.loads(raw or '{}')
        return tuple(str(payload.get(key, '')) for key in ('theme', 'notifications', 'locale'))
    except (ValueError, TypeError):
        return None


def components(teams, members):
    if (teams.where('team_id is null').take(1)
            or members.where('team_id is null or user_id is null').take(1)):
        raise ValueError('Team graph cannot label null team/user IDs')
    edges = members.select('team_id', 'user_id').distinct().cache()
    labels = None
    try:
        labels = (teams.select('team_id').union(edges.select('team_id')).distinct()
                  .withColumn('component_id', F.col('team_id')).localCheckpoint(eager=True))
        while True:
            # Share the minimum label per user instead of producing every team-to-team pair.
            user_minimum = edges.join(labels, 'team_id').groupBy('user_id').agg(
                F.min('component_id').alias('component_id'))
            next_labels = (edges.join(user_minimum, 'user_id').select('team_id', 'component_id').union(labels)
                           .groupBy('team_id').agg(F.min('component_id').alias('component_id'))
                           .localCheckpoint(eager=True))
            changed = labels.alias('old').join(next_labels.alias('new'), 'team_id').where(
                F.col('old.component_id') != F.col('new.component_id')).take(1)
            labels.unpersist()
            labels = next_labels
            if not changed:
                return labels
    finally:
        edges.unpersist()


def outputs(feeds):
    activity = feeds['user_activity_daily']
    yield 'users_active_daily', activity.groupBy('activity_date').agg(
        F.countDistinct('user_id').alias('active_users'), F.sum('login_count').alias('logins'),
        F.sum('action_count').alias('actions'))

    team, member = feeds['team'].alias('t'), feeds['team_member'].alias('m')
    rollup = (team.join(member, F.col('t.team_id') == F.col('m.team_id'), 'left')
              .join(feeds['app_user'].alias('u'), F.col('m.user_id') == F.col('u.user_id'), 'left')
              .groupBy('t.team_id', 't.team_name').agg(F.count('m.user_id').alias('members')))
    yield 'users_team_rollup', rollup

    events = feeds['login_event']
    pattern = r'(?U)(Chrome|Firefox|Safari)/(\S+)'
    browser = F.regexp_extract('user_agent', pattern, 0)
    yield 'users_login_useragent_parse', events.withColumn(
        'browser', F.when(F.length(browser) > 0, browser).otherwise(F.lit('Other')))

    # Match Spark 2/3 non-ANSI BIGINT -> Int narrowing at the Scala UDF boundary.
    logins = F.expr('cast((login_count & 2147483647L) - (login_count & 2147483648L) as int)')
    actions = F.expr('cast((action_count & 2147483647L) - (action_count & 2147483648L) as int)')
    yield 'users_risk_score', activity.withColumn(
        'risk_score', 1.0 / (1.0 + F.exp(-(-2.1 + logins * 0.0004 - actions * 0.0001))))

    parse = F.udf(preferences, 'struct<theme:string,notifications:string,locale:string>')
    yield 'user_pref_json_flatten', (feeds['user_pref'].withColumn('_parsed', parse('pref_json'))
                                    .select(*feeds['user_pref'].columns, '_parsed.*'))
    yield 'team_graph_components', components(team, member)


def run(spark, directory):
    for name, frame in outputs(read_inputs(spark, directory)):
        path = delta_path('gold', 'users', name)
        frame.write.format('delta').mode('overwrite').save(str(path))
        spark.sql(f"CREATE TABLE IF NOT EXISTS gold_users.{name} USING DELTA LOCATION '{path.as_uri()}'")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--landing', required=True, type=Path)
    args = parser.parse_args()
    spark = create_session()
    try:
        run(spark, args.landing)
    finally:
        spark.stop()


if __name__ == '__main__':
    main()
