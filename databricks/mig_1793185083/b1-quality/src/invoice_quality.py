# ow_tp_invoice_quality_1793185083 — Lakeflow Spark Declarative Pipeline
#
# Conversion of the OW_BILLING invoice quality checks (unit
# u-invoice-quality-pipeline): an unfiltered, full-estate scan of the three
# legacy roots. Rows that violate a declared expectation route into the
# matching quarantine sink under ow_tp.mig_1793185083; nothing else is
# written. Expectations come verbatim from the unit's mapping_spec.json:
#
#   line_has_header            INVOICE_ID IS NOT NULL AND INVOICE_ID IN
#                              (SELECT INVOICE_ID FROM OW_BILLING.INVOICE_HEADER)
#   line_invoice_dt_parseable  INVOICE_DT IS NULL OR
#                              try_to_date(INVOICE_DT, 'dd-MMM-yy') IS NOT NULL
#   header_invoice_dt_parseable / header_due_dt_parseable   same rule, INVOICE_HEADER
#   cm_signup_dt_parseable     same rule, CUSTOMER_MASTER.SIGNUP_DT
#
# Source of record: a SELECT-only CSV snapshot of the three OW_BILLING roots
# landed by extract/ow_billing_extract.py at the volume path below (no
# federation, JDBC, or CDC — the legacy estate is read-only). Every sink row
# carries `reject_reasons`, the names of the expectations the row failed.

from pyspark import pipelines as dp
from pyspark.sql import functions as F

_EXTRACT = "/Volumes/ow_tp/mig_1793185083/ow_tp_invoice_quality_extract"
_DATE_FMT = "dd-MMM-yy"


def _root(name, cols):
    # CSV snapshot read; every field is a string and spec fields declare
    # empty_string_is_null, so an empty CSV field lands as NULL.
    return (
        spark.read.format("csv")
        .option("header", "true")
        .load(f"{_EXTRACT}/{name}.csv")
        .select(*[F.nullif(F.col(c), F.lit("")).alias(c) for c in cols])
    )


def _unparseable(col):
    # NOT (col IS NULL OR try_to_date(col, 'dd-MMM-yy') IS NOT NULL)
    return F.col(col).isNotNull() & F.expr(
        f"try_to_date({col}, '{_DATE_FMT}') IS NULL"
    )


@dp.temporary_view()
def src_invoice_header():
    return _root("invoice_header", ["invoice_id", "invoice_dt", "due_dt"])


@dp.temporary_view()
def src_invoice_line():
    return _root("invoice_line", ["line_id", "invoice_id", "invoice_dt"])


@dp.temporary_view()
def src_customer_master():
    return _root("customer_master", ["cust_id", "signup_dt"])


@dp.materialized_view(
    name="invoice_line_quarantine",
    schema="""line_id STRING NOT NULL,
              invoice_id STRING,
              invoice_dt STRING,
              reject_reasons ARRAY<STRING>""",
    comment="INVOICE_LINE rows failing line_has_header (orphan or NULL invoice_id) "
    "or line_invoice_dt_parseable. Target-only output; expect_or_quarantine routing.",
)
def invoice_line_quarantine():
    lines = spark.read.table("src_invoice_line")
    headers = (
        spark.read.table("src_invoice_header")
        .select("invoice_id")
        .dropDuplicates()
        .withColumnRenamed("invoice_id", "_hdr_invoice_id")
    )
    joined = lines.join(headers, lines.invoice_id == F.col("_hdr_invoice_id"), "left")
    reasons = F.array_compact(
        F.array(
            F.when(F.col("_hdr_invoice_id").isNull(), F.lit("line_has_header")),
            F.when(_unparseable("invoice_dt"), F.lit("line_invoice_dt_parseable")),
        )
    )
    return (
        joined.withColumn("reject_reasons", reasons)
        .filter(F.size("reject_reasons") > 0)
        .select("line_id", "invoice_id", "invoice_dt", "reject_reasons")
    )


@dp.materialized_view(
    name="invoice_header_quarantine",
    schema="""invoice_id STRING NOT NULL,
              invoice_dt STRING,
              due_dt STRING,
              reject_reasons ARRAY<STRING>""",
    comment="INVOICE_HEADER rows failing header_invoice_dt_parseable or "
    "header_due_dt_parseable. Target-only output; expect_or_quarantine routing.",
)
def invoice_header_quarantine():
    headers = spark.read.table("src_invoice_header")
    reasons = F.array_compact(
        F.array(
            F.when(_unparseable("invoice_dt"), F.lit("header_invoice_dt_parseable")),
            F.when(_unparseable("due_dt"), F.lit("header_due_dt_parseable")),
        )
    )
    return (
        headers.withColumn("reject_reasons", reasons)
        .filter(F.size("reject_reasons") > 0)
        .select("invoice_id", "invoice_dt", "due_dt", "reject_reasons")
    )


@dp.materialized_view(
    name="customer_master_quarantine",
    schema="""cust_id STRING NOT NULL,
              signup_dt STRING,
              reject_reasons ARRAY<STRING>""",
    comment="CUSTOMER_MASTER rows failing cm_signup_dt_parseable. Target-only "
    "output; expect_or_quarantine routing.",
)
def customer_master_quarantine():
    customers = spark.read.table("src_customer_master")
    reasons = F.array_compact(
        F.array(
            F.when(_unparseable("signup_dt"), F.lit("cm_signup_dt_parseable")),
        )
    )
    return (
        customers.withColumn("reject_reasons", reasons)
        .filter(F.size("reject_reasons") > 0)
        .select("cust_id", "signup_dt", "reject_reasons")
    )
