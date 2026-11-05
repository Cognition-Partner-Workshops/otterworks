"""Stage 2: incoming/CUSTBILL*.dat -> parsed/*.psv. Replaces jobs/parse_custbill_fixedwidth.sh.

The pipe-delimited output is byte-identical to the sed|cut|paste|awk pipeline.
On top of that the job types every column, validates each record and reconciles
the trailer count; problems are written to a quality ledger and, in strict mode,
quarantine the file instead of silently producing a report from bad data.
"""

import logging
import re

from .config import FILE_GLOB, RECORD_WIDTH
from .support import encode_lines, read_file_lines, stage_lock, write_atomic, write_ledger

log = logging.getLogger("custbill_spark.parse")

# awk's string-to-number conversion: the longest numeric prefix after optional
# blanks, or 0 when there is none.
NUMERIC_PREFIX = re.compile(r"^[ \t\n\r\f\v]*[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")
COLUMNS = ((0, 10), (10, 40), (40, 48), (48, 60), (60, 63), (63, 65))
VALID_RECORD_TYPES = ("01", "02")


def awk_number(text):
    match = NUMERIC_PREFIX.match(text)
    return float(match.group(0)) if match else 0.0


def record_kind(line):
    if line.startswith("HDR"):
        return "HDR"
    if line.startswith("TRL"):
        return "TRL"
    return "BODY"


def legacy_psv(line):
    """Exactly what `cut | paste -d'|' | awk` emits for one body line."""
    cust, name, date, amount, currency, rtype = (line[a:b] for a, b in COLUMNS)
    cust, name, currency = (field.rstrip(" ") for field in (cust, name, currency))
    return "|".join((cust, name, f"{date[0:4]}-{date[4:6]}-{date[6:8]}",
                     "%.2f" % (awk_number(amount) / 100), currency, rtype))


def trailer_count(line):
    return int(awk_number(line[3:13]))


def typed_frame(spark, rows):
    """DataFrame of body records with typed columns and per-record validation reasons."""
    from pyspark.sql import functions as F
    from pyspark.sql.types import IntegerType, StringType, StructField, StructType

    schema = StructType([StructField("file", StringType()), StructField("line_no", IntegerType()),
                         StructField("kind", StringType()), StructField("line", StringType()),
                         StructField("psv", StringType())])
    frame = spark.createDataFrame(rows, schema)
    body = frame.filter(F.col("kind") == "BODY")
    date_raw = F.substring("line", 41, 8)
    amount_raw = F.substring("line", 49, 12)
    checks = (
        ("bad-width", F.length("line") != RECORD_WIDTH),
        ("blank-customer", F.rtrim(F.substring("line", 1, 10)) == ""),
        ("blank-name", F.rtrim(F.substring("line", 11, 30)) == ""),
        ("bad-date", F.try_to_timestamp(date_raw, F.lit("yyyyMMdd")).isNull()),
        ("bad-amount", ~amount_raw.rlike(r"^[0-9]{12}$")),
        ("bad-currency", ~F.substring("line", 61, 3).rlike(r"^[A-Z]{3}$")),
        ("bad-record-type", ~F.substring("line", 64, 2).isin(*VALID_RECORD_TYPES)),
    )
    typed = (body.withColumn("customer_id", F.rtrim(F.substring("line", 1, 10)))
             .withColumn("billing_date", F.try_to_timestamp(date_raw, F.lit("yyyyMMdd")).cast("date"))
             .withColumn("amount", (F.regexp_extract(amount_raw, r"^[0-9]{12}$", 0)
                                    .cast("decimal(14,0)") / 100).cast("decimal(14,2)"))
             .withColumn("currency", F.substring("line", 61, 3))
             .withColumn("record_type", F.substring("line", 64, 2))
             .withColumn("reasons", F.concat_ws(",", *[F.when(cond, F.lit(name)) for name, cond in checks])))
    return frame, typed


def quality(frame, typed):
    from pyspark.sql import functions as F

    trailers = (frame.filter(F.col("kind") == "TRL")
                .groupBy("file").agg(F.first("line").alias("trailer_line")))
    per_file = (typed.groupBy("file")
                .agg(F.count("*").alias("records"),
                     F.sum(F.when(F.col("reasons") != "", 1).otherwise(0)).alias("invalid_records"),
                     F.sort_array(F.collect_list(F.when(F.col("reasons") != "",
                                                        F.struct("line_no", "reasons")))).alias("invalid"))
                .join(trailers, "file", "full_outer"))
    result = {}
    for row in per_file.collect():
        trailer = trailer_count(row.trailer_line) if row.trailer_line else None
        records = row.records or 0
        result[row.file] = {"records": records, "trailer_count": trailer,
                            "trailer_reconciled": trailer == records,
                            "invalid_records": int(row.invalid_records or 0),
                            "invalid_sample": [{"line_no": r.line_no + 1, "reasons": r.reasons}
                                               for r in (row.invalid or [])[:25]]}
    return result


def run(settings, spark):
    with stage_lock(settings, "parse"):
        return _run(settings, spark)


def _run(settings, spark):
    settings.parsed.mkdir(parents=True, exist_ok=True)
    inputs = sorted(p for p in settings.incoming.glob(FILE_GLOB) if p.is_file())
    if not inputs:
        log.info("parse: nothing to do in %s", settings.incoming)
        return {"files": {}}
    rows = (read_file_lines(spark, inputs)
            .map(lambda row: (row[0], row[1], record_kind(row[2]), row[2],
                              legacy_psv(row[2]) if record_kind(row[2]) == "BODY" else None)))
    frame, typed = typed_frame(spark, rows)
    frame.cache()
    report = quality(frame, typed)
    lines_by_file = {}
    for row in frame.filter(frame.kind == "BODY").select("file", "line_no", "psv").collect():
        lines_by_file.setdefault(row.file, []).append((row.line_no, row.psv))
    frame.unpersist()
    quarantined = []
    for source in inputs:
        info = report.setdefault(source.name, {"records": 0, "trailer_count": None,
                                               "trailer_reconciled": False,
                                               "invalid_records": 0, "invalid_sample": []})
        problems = info["invalid_records"] or not info["trailer_reconciled"]
        if problems:
            log.warning("%s: %d invalid record(s), trailer %s vs %d records", source.name,
                        info["invalid_records"], info["trailer_count"], info["records"])
        if settings.strict and problems:
            info["status"] = "quarantined"
            quarantined.append(source.name)
            continue
        psv = [psv for _, psv in sorted(lines_by_file.get(source.name, []))]
        write_atomic(settings.parsed / f"{source.stem}.psv", encode_lines(psv))
        source.replace(source.with_name(f"{source.name}.done"))
        info["status"] = "parsed"
        log.info("parsed %s -> %d record(s)", source.name, len(psv))
    ledger = {"files": report, "strict": settings.strict, "quarantined": quarantined}
    write_ledger(settings, "parse", "latest", ledger)
    if quarantined:
        raise RuntimeError(f"parse: {len(quarantined)} file(s) quarantined (strict mode)")
    return ledger
