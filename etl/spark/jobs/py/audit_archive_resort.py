from common.runtime import landing, save, session

spark = session("audit_archive_resort")
records = landing(spark, "AUDIT_EVENT_ARCHIVE").rdd.map(
    lambda r: ((r.EVENT_TYPE, r.EVENT_AT, r.AUDIT_EVENT_ARCHIVE_ID), tuple(r))
)
ordered = records.sortByKey(numPartitions=2).values()
frame = spark.createDataFrame(ordered, landing(spark, "AUDIT_EVENT_ARCHIVE").schema)
save(frame.sortWithinPartitions("EVENT_TYPE", "EVENT_AT", "AUDIT_EVENT_ARCHIVE_ID"),
     "audit", "audit_archive_resort")
spark.stop()
