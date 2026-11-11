"""Replaces the Spark lake output billing/billing_churn_score."""
from snowflake.snowpark.functions import call_udf, col


def run(session):
    database = session.get_current_database()
    function = f'{database}."MART_SPARK"."BILLING_CHURN_SCORE_SCORE"'
    session.sql(f"""
        create or replace temporary function {function}(status varchar, customer_id bigint)
        returns float
        language python
        runtime_version = '3.10'
        handler = 'score'
        as $$
import math

def score(status, customer_id):
    linear = -1.8 + 0.04 * (customer_id % 50) + (1.2 if status == "closed" else 0.0)
    return 1.0 / (1.0 + math.exp(-linear))
$$
    """).collect()
    subscriptions = session.table([database, "SPARK_RAW_BILLING", "SUBSCRIPTION"])
    result = subscriptions.select(
        "SUBSCRIPTION_ID", "CUSTOMER_ID", "PLAN_ID", "START_DATE", "END_DATE", "STATUS",
        call_udf(function, col("STATUS"), col("CUSTOMER_ID")).alias("CHURN_SCORE"),
    )
    result.write.save_as_table(
        [database, "MART_SPARK", "BILLING_CHURN_SCORE"],
        mode="overwrite",
        comment="sfx-d1110 Replaces the Spark lake output billing/billing_churn_score.",
    )
