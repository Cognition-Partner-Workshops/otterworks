# ow_tp_custbill_ldp — Lakeflow Declarative Pipeline for the CUSTBILL month-end chain.
#
# Conversion of the legacy pair:
#   jobs/parse_custbill_fixedwidth.sh  -> parsed_records (+ quarantine)
#   jobs/finance_excel_report.pl     -> finance_billing_totals
#
# Source of record is ow_tp_custbill.custbill_feed (one staged row per CBCUST01
# 65-char detail record; HDR/TRL never landed). The legacy shell parser did no
# validation — bad records passed through to the .psv. The converted pipeline
# enforces the record contract as data expectations and routes every failing
# row to ow_tp_custbill.quarantine with its reasons.
#
# Copybook CBCUST01 layout (1-based):
#   pos  1-10   CUST-ID     X(10)
#   pos 11-40   CUST-NAME   X(30)
#   pos 41-48   BILL-DATE   9(8) YYYYMMDD
#   pos 49-60   BILL-AMT    9(10)V99 implied decimal
#   pos 61-63   CURRENCY    X(3)
#   pos 64-65   REC-TYPE    X(2) (01=invoice, 02=credit)

from pyspark import pipelines as dp
from pyspark.sql import functions as F

FEED = "ow_tp.ow_tp_custbill.custbill_feed"

EXPECTATIONS = {
    "cbcust01_len65": "length(raw_line) = 65",
    "cbcust01_bill_date": "to_date(substring(raw_line, 41, 8), 'yyyyMMdd') is not null",
    "cbcust01_currency": "upper(substring(raw_line, 61, 3)) in ('USD', 'EUR', 'GBP')",
    "cbcust01_record_type": "substring(raw_line, 64, 2) in ('01', '02')",
}

_REJECT_PREDICATE = " or ".join(f"not ({expr})" for expr in EXPECTATIONS.values())


def _parse(feed):
    """The six CBCUST01 fields, exactly as the awk/cut chain emitted them:
    trimmed id/name, ISO bill_date, unsigned implied-decimal bill_amt,
    upper-cased currency, two-char record_type."""
    return feed.select(
        "invoice_id",
        F.trim(F.substring("raw_line", 1, 10)).alias("cust_no"),
        F.trim(F.substring("raw_line", 11, 30)).alias("cust_name"),
        F.to_date(F.substring("raw_line", 41, 8), "yyyyMMdd").alias("bill_date"),
        (F.col("raw_line").substr(49, 12).cast("decimal(12,2)") / 100).alias("bill_amt"),
        F.upper(F.trim(F.substring("raw_line", 61, 3))).alias("currency"),
        F.substring("raw_line", 64, 2).alias("record_type"),
        "raw_line",
        "source_file",
        "batch_no",
        "landed_at",
    )


@dp.table(
    name="parsed_records",
    comment="CBCUST01 detail rows parsed from custbill_feed; expectation violations are dropped here and captured in quarantine.",
)
@dp.expect_or_drop("cbcust01_len65", EXPECTATIONS["cbcust01_len65"])
@dp.expect_or_drop("cbcust01_bill_date", EXPECTATIONS["cbcust01_bill_date"])
@dp.expect_or_drop("cbcust01_currency", EXPECTATIONS["cbcust01_currency"])
@dp.expect_or_drop("cbcust01_record_type", EXPECTATIONS["cbcust01_record_type"])
def parsed_records():
    return _parse(spark.read.table(FEED))


@dp.table(
    name="quarantine",
    comment="CBCUST01 rows that failed a data expectation; carries the verbatim record and every reason it was rejected.",
)
def quarantine():
    feed = spark.read.table(FEED)
    reasons = F.array_compact(
        F.array(
            *[
                F.when(F.expr(f"not ({expr})"), F.lit(name))
                for name, expr in EXPECTATIONS.items()
            ]
        )
    )
    return (
        _parse(feed.filter(_REJECT_PREDICATE))
        .withColumn("reject_reasons", reasons)
        .withColumn("quarantined_at", F.current_timestamp())
    )


@dp.table(
    name="finance_billing_totals",
    comment="Month-end billing rollup keyed (currency, record_type); the finance_billing_YYYYMMDD.csv surface: Currency,RecordType,RecordCount,TotalAmount.",
)
def finance_billing_totals():
    parsed = spark.read.table("parsed_records")
    return (
        parsed.withColumn("billing_period", F.last_day("bill_date"))
        .withColumn(
            "record_type",
            F.when(F.col("record_type") == "01", F.lit("INVOICE"))
            .when(F.col("record_type") == "02", F.lit("CREDIT"))
            .otherwise(F.concat(F.lit("UNKNOWN"), F.col("record_type"))),
        )
        .groupBy("billing_period", "currency", "record_type")
        .agg(
            F.count("*").alias("record_count"),
            F.sum("bill_amt").alias("total_amount"),
        )
        .select(
            "billing_period",
            "currency",
            "record_type",
            "record_count",
            F.round("total_amount", 2).alias("total_amount"),
        )
    )
