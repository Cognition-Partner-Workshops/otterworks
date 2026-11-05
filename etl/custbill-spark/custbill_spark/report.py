"""Stage 3: parsed/*.psv -> reports/finance_billing_YYYYMMDD.{csv,xls}.

Replaces jobs/finance_excel_report.pl. The CSV is byte-identical to the Perl
output; the `.xls` is still a byte copy of the CSV because parity pins it (see
README). Delivery is a verified copy to a configured directory and a ledger
naming the configured distribution list, not a hard-coded sendmail.
"""

from decimal import Decimal
import logging
import shutil
import time

from .parse import NUMERIC_PREFIX
from .support import purge_older_than, read_file_lines, sha256, stage_lock, write_atomic, write_ledger

log = logging.getLogger("custbill_spark.report")

HEADER = "Currency,RecordType,RecordCount,TotalAmount"
RECORD_TYPES = {"01": "INVOICE", "02": "CREDIT"}


def record_type_label(code):
    return RECORD_TYPES.get(code, f"UNKNOWN({code})")


def perl_decimal(text):
    """Perl's numeric value of the amount field, as an exact Decimal."""
    match = NUMERIC_PREFIX.match(text)
    return Decimal(match.group(0).strip()) if match else Decimal(0)


def split_record(line):
    fields = line.split("|")
    fields += [""] * (6 - len(fields))
    return fields


def aggregate(spark, inputs):
    from pyspark.sql import functions as F
    from pyspark.sql.types import DecimalType, StringType, StructField, StructType

    schema = StructType([StructField("customer_id", StringType()), StructField("currency", StringType()),
                         StructField("record_type", StringType()),
                         StructField("amount", DecimalType(38, 10))])
    rows = (read_file_lines(spark, inputs)
            .map(lambda row: split_record(row[2]))
            .filter(lambda f: f[0] != "")
            .map(lambda f: (f[0], f[4], f[5], perl_decimal(f[3]))))
    frame = spark.createDataFrame(rows, schema)
    totals = (frame.groupBy("currency", "record_type")
              .agg(F.count("*").alias("n"), F.sum("amount").alias("total")))
    return sorted(((r.currency, r.record_type, int(r.n), r.total) for r in totals.collect()),
                  key=lambda r: f"{r[0]}|{r[1]}")


def render(groups):
    lines = [HEADER]
    for currency, code, count, total in groups:
        lines.append(f"{currency},{record_type_label(code)},{count},{total:.2f}")
    return "".join(line + "\n" for line in lines).encode("latin-1")


def run(settings, spark):
    with stage_lock(settings, "report"):
        return _run(settings, spark)


def _run(settings, spark):
    settings.reports.mkdir(parents=True, exist_ok=True)
    inputs = sorted(p for p in settings.parsed.glob("CUSTBILL*.psv") if p.is_file())
    groups = aggregate(spark, inputs) if inputs else []
    body = render(groups)
    stamp = time.strftime("%Y%m%d")
    csv = settings.reports / f"finance_billing_{stamp}.csv"
    xls = csv.with_suffix(".xls")
    write_atomic(csv, body)
    write_atomic(xls, body)
    digest = sha256(body)
    delivered = None
    if settings.delivery_dir:
        settings.delivery_dir.mkdir(parents=True, exist_ok=True)
        target = settings.delivery_dir / csv.name
        shutil.copyfile(csv, target)
        if sha256(target.read_bytes()) != digest:
            raise RuntimeError(f"report: delivery to {target} did not verify")
        delivered = str(target)
    purged = purge_older_than(settings.incoming, "*.done", settings.done_retention_days)
    ledger = {"report": csv.name, "sha256": digest, "bytes": len(body), "groups": len(groups),
              "inputs": [p.name for p in inputs], "delivered_to": delivered,
              "distribution": list(settings.distribution), "done_purged": purged}
    write_ledger(settings, "report", stamp, ledger)
    log.info("wrote %s (%d bytes, %d group(s))", csv, len(body), len(groups))
    return ledger
