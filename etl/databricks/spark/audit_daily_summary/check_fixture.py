# run_token=dbx-d1111 expires=2026-11-24
"""Local-only fixture evidence. This never connects to Databricks or proves live parity."""
import importlib.util
import json
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from common.runtime import landing

JOBS = ["audit_daily_summary", "audit_actor_activity_join", "lake_compaction_audit",
        "security_alert_anomaly", "audit_archive_resort", "compliance_flag_rules"]
BASE = Path(__file__).resolve().parents[1]


def module(job):
    spec = importlib.util.spec_from_file_location(job, BASE / job / "migrate.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fingerprint(frame):
    canonical = F.concat_ws("|", *[F.coalesce(F.col(c).cast("string"), F.lit("<NULL>"))
                                  for c in frame.columns])
    return frame.agg(F.count("*").alias("count"), F.sum(F.conv(F.substring(
        F.md5(canonical), 1, 15), 16, 10).cast("decimal(38,0)")).alias("hash")).first().asDict()


def check_edges(spark):
    rules = module("compliance_flag_rules")
    frame = spark.createDataFrame([(1, 2, 6999, "active"), (2, 2, 7000, "active"),
                                   (3, 2, 9000, "closed"), (4, 2, None, None)],
                                  "COMPLIANCE_FLAG_ID int, DOCUMENT_ID int, SEVERITY int, STATUS string")
    assert [r.DISPOSITION for r in rules.transform(frame).orderBy("FLAG_ID").collect()] == [
        "monitor", "review", "resolved", "monitor"]
    alerts = module("security_alert_anomaly")
    same = spark.createDataFrame([(1, None, 5.0), (2, 9, 5.0)],
                                 "SECURITY_ALERT_ID long, USER_ID long, SCORE double")
    assert all(r.Z_SCORE == 0.0 for r in alerts.transform(same).collect())
    assert alerts.transform(same.limit(0)).count() == 0
    try:
        alerts.transform(same.withColumn("SCORE", F.lit(None).cast("double")))
        raise AssertionError("null score accepted")
    except ValueError:
        pass
    for mod, frame in [(alerts, same.drop("SCORE")), (rules, frame.drop("SEVERITY"))]:
        try:
            mod.transform(frame)
            raise AssertionError("missing field accepted")
        except ValueError:
            pass


def main():
    spark = SparkSession.builder.appName("audit_migrated_fixture_check").getOrCreate()
    check_edges(spark)
    for table in ["AUDIT_EVENT", "USER_ACTIVITY_DAILY", "LOGIN_EVENT"]:
        landing(spark, table).createOrReplaceTempView(table)
    spark.read.parquet("/opt/lake/audit/audit_daily_summary").createOrReplaceTempView("AUDIT_DAILY_SUMMARY")
    for job in JOBS:
        evidence = {"scope": "default local fixture ONLY; not live parity",
                    "aqe": spark.conf.get("spark.sql.adaptive.enabled"), "edge_tests": "passed"}
        try:
            before = spark.read.parquet(f"/opt/lake/audit/{job}")
            if (BASE / job / "transform.sql").exists():
                frame = spark.sql((BASE / job / "transform.sql").read_text())
            else:
                table = {"security_alert_anomaly": "SECURITY_ALERT",
                         "audit_archive_resort": "AUDIT_EVENT_ARCHIVE",
                         "compliance_flag_rules": "COMPLIANCE_FLAG"}[job]
                frame = module(job).transform(landing(spark, table))
            evidence["before_schema"] = before.schema.simpleString()
            evidence["after_schema"] = frame.schema.simpleString()
            evidence["before"] = fingerprint(before)
            # Persist each run separately so a lazy plan cannot fake idempotence.
            for run in (1, 2):
                path = f"/opt/lake/audit/migrated_fixture_{job}"
                frame.write.mode("overwrite").parquet(path)
                after = spark.read.parquet(path).select(*before.columns)
                evidence[f"run{run}"] = fingerprint(after)
            evidence["before_minus_after"] = [r.asDict() for r in before.exceptAll(after).limit(20).collect()]
            evidence["after_minus_before"] = [r.asDict() for r in after.exceptAll(before).limit(20).collect()]
            evidence["exact_parity"] = (evidence["before"] == evidence["run1"]
                and not evidence["before_minus_after"] and not evidence["after_minus_before"])
            evidence["idempotent"] = evidence["run1"] == evidence["run2"]
        except Exception as exc:
            evidence["error"] = str(exc)[:4000]
        (BASE / job / "fixture-evidence.json").write_text(json.dumps(evidence, indent=2, default=str) + "\n")
        print(job, json.dumps(evidence, default=str), flush=True)
    spark.stop()


if __name__ == "__main__":
    main()
