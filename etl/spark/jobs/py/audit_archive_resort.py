from common.runtime import landing, save, session

spark = session("audit_archive_resort")
archive = landing(spark, "AUDIT_EVENT_ARCHIVE")
ordered = archive.orderBy("EVENT_TYPE", "EVENT_AT", "AUDIT_EVENT_ARCHIVE_ID")
save(ordered, "audit", "audit_archive_resort")
spark.stop()
