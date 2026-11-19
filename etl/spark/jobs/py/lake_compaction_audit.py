from common.runtime import save, session

spark = session("lake_compaction_audit")
frame = spark.read.parquet("/opt/lake/audit/audit_daily_summary")
save(frame.coalesce(2), "audit", "lake_compaction_audit")
spark.stop()
