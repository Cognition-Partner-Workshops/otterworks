"""Replaces the Spark lake output audit/security_alert_anomaly and JDBC sfx_audit.SPARK_ALERT_ANOMALY."""
import json

from snowflake.snowpark.functions import call_udf, col, lit


def run(session):
    database = session.get_current_database()
    moments = f'{database}."MART_SPARK"."SECURITY_ALERT_ANOMALY_MOMENTS"'
    z_score = f'{database}."MART_SPARK"."SECURITY_ALERT_ANOMALY_Z_SCORE"'
    session.sql(f"""
        create or replace temporary aggregate function {moments}(score float)
        returns object
        language python
        runtime_version = '3.10'
        handler = 'Moments'
        as $$
import math

class Moments:
    def __init__(self):
        self._state = (0, 0.0, 0.0)

    @property
    def aggregate_state(self):
        return self._state

    def accumulate(self, score):
        count, total, squares = self._state
        self._state = (count + 1, total + score, squares + score ** 2)

    def merge(self, other):
        self._state = tuple(x + y for x, y in zip(self._state, other))

    def finish(self):
        count, total, squares = self._state
        mean = total / max(count, 1)
        stddev = math.sqrt(max(squares / max(count, 1) - mean ** 2, 0.0)) or 1.0
        return {{"mean": mean, "stddev": stddev}}
$$
    """).collect()
    session.sql(f"""
        create or replace temporary function {z_score}(score float, mean float, stddev float)
        returns float
        language python
        runtime_version = '3.10'
        handler = 'z_score'
        as $$
def z_score(score, mean, stddev):
    return (score - mean) / stddev
$$
    """).collect()
    alerts = session.table([database, "SPARK_RAW_AUDIT", "SECURITY_ALERT"]).select(
        col("SECURITY_ALERT_ID").alias("ALERT_ID"),
        "USER_ID",
        col("SCORE").cast("double").alias("SCORE"),
    )
    distribution = alerts.select(call_udf(moments, col("SCORE")).alias("M")).collect()[0]["M"]
    stats = json.loads(distribution)
    result = alerts.select(
        "ALERT_ID", "USER_ID", "SCORE",
        call_udf(z_score, col("SCORE"), lit(stats["mean"]), lit(stats["stddev"])).alias("Z_SCORE"),
    )
    result.write.save_as_table(
        [database, "MART_SPARK", "SECURITY_ALERT_ANOMALY"],
        mode="overwrite",
        comment="sfx-d1110 Replaces the Spark lake output audit/security_alert_anomaly.",
    )
