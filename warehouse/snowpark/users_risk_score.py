"""Replaces the Spark lake output users/users_risk_score and JDBC sfx_users.SPARK_RISK_SCORE."""
from snowflake.snowpark.functions import call_udf, col


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."USERS_RISK_SCORE_SCORE"'
    session.sql(f"""
        create or replace temporary function {function}(logins bigint, actions bigint)
        returns float
        language python
        runtime_version = '3.10'
        handler = 'score'
        as $$
import math

def score(logins, actions):
    if logins is None or actions is None:
        return None
    return 1.0 / (1.0 + math.exp(-(-2.1 + logins * 0.0004 - actions * 0.0001)))
$$
    """).collect()
    activity = session.table([database, "SPARK_RAW_USERS", "USER_ACTIVITY_DAILY"])
    result = activity.select(
        "USER_ACTIVITY_ID", "USER_ID", "ACTIVITY_DATE", "LOGIN_COUNT", "ACTION_COUNT",
        call_udf(function, col("LOGIN_COUNT"), col("ACTION_COUNT")).alias("RISK_SCORE"),
    )
    result.write.save_as_table(
        [database, "MART_SPARK", "USERS_RISK_SCORE"],
        mode="overwrite",
        comment="sfx-d1110 Replaces the Spark lake output users/users_risk_score.",
    )
