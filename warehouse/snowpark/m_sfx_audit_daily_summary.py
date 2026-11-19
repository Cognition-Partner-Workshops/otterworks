"""Replaces the PowerCenter mapping m_SFX_AUDIT_DAILY_SUMMARY (SFX_AUDIT.AUDIT_DAILY_SUMMARY).

AGG_DAILY_EVENTS groups by TRUNC(EVENT_TS,'DD') and CUSTOMER_ID. SEQ_AUDIT_SUMMARY (Current Value
50001, Reset NO) numbers groups in first-seen read order, which is EVENT_ID order for the audit
target, so new groups are ranked by MIN(EVENT_ID). Intended difference: the legacy session appends a
second copy of every group on a rerun; here existing groups keep their SUMMARY_ID, their counts are
refreshed, new groups continue from MAX(SUMMARY_ID)+1 and groups without events are removed.
Single writer: do not run concurrently.
"""

from snowflake.snowpark import Window
from snowflake.snowpark.functions import (coalesce, col, count, iff, lit, max as max_, min as min_, row_number,
                                          rtrim, sum as sum_, to_date)
from snowflake.snowpark.types import DateType, LongType, StructField, StructType

SOURCE = ("PC_AUDIT", "AUDIT_EVENT")
TARGET = ("TRANSFORM", "M_SFX_AUDIT_DAILY_SUMMARY")
SEQUENCE_START = 50001
SCHEMA = StructType([
    StructField("SUMMARY_ID", LongType(), nullable=False),
    StructField("SUMMARY_DT", DateType()),
    StructField("CUSTOMER_ID", LongType()),
    StructField("EVENT_COUNT", LongType()),
    StructField("EXPORT_COUNT", LongType()),
])
# Sentinels make the nullable group keys joinable; neither value is a legal key.
_NO_DATE = "0001-01-01"
_NO_CUSTOMER = -1


def _keyed(frame):
    return frame.with_column("DT_KEY", coalesce(col("SUMMARY_DT"), to_date(lit(_NO_DATE)))) \
                .with_column("CUSTOMER_KEY", coalesce(col("CUSTOMER_ID"), lit(_NO_CUSTOMER)))


def run(session):
    database = session.get_current_database()
    target = [database, *TARGET]
    session.create_dataframe([], schema=SCHEMA).write.save_as_table(target, mode="ignore")
    existing = session.table(target)
    assigned, highest = existing.agg(count("SUMMARY_ID"), max_("SUMMARY_ID")).collect()[0]
    next_id = int(highest) + 1 if assigned else SEQUENCE_START

    # EXP_SUMMARY_KEYS, then AGG_DAILY_EVENTS.
    keys = session.table([database, *SOURCE]).select(
        col("EVENT_ID"), to_date(col("EVENT_TS")).alias("SUMMARY_DT"), col("CUSTOMER_ID"),
        iff(rtrim(col("EVENT_TYPE")) == "DOC_EXPORT", 1, 0).alias("IS_EXPORT"))
    grouped = _keyed(keys.group_by("SUMMARY_DT", "CUSTOMER_ID").agg(
        count("EVENT_ID").alias("EVENT_COUNT"), sum_("IS_EXPORT").alias("EXPORT_COUNT"),
        min_("EVENT_ID").alias("FIRST_EVENT_ID")))
    known = _keyed(existing).select(col("SUMMARY_ID").alias("KNOWN_ID"), col("DT_KEY").alias("KNOWN_DT"),
                                    col("CUSTOMER_KEY").alias("KNOWN_CUSTOMER"))
    joined = grouped.join(known, (grouped["DT_KEY"] == known["KNOWN_DT"])
                          & (grouped["CUSTOMER_KEY"] == known["KNOWN_CUSTOMER"]), "left")
    joined = joined.with_column("IS_NEW", col("KNOWN_ID").is_null())
    rank = row_number().over(Window.partition_by("IS_NEW").order_by(col("FIRST_EVENT_ID")))
    result = joined.with_column("SUMMARY_ID", iff(col("IS_NEW"), lit(next_id - 1) + rank, col("KNOWN_ID"))) \
                   .select(*[col(field.name).cast(field.datatype).alias(field.name) for field in SCHEMA.fields])
    # Materialise before replacing the table the frame reads from.
    rows = result.cache_result()
    rows.write.save_as_table(target, mode="overwrite", copy_grants=True)
    return rows.count()
