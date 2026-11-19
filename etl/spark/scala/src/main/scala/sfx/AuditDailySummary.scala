package sfx

object AuditDailySummary {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("audit_daily_summary")
    BatchSupport.register(spark, "audit", "AUDIT_EVENT")
    val result = spark.sql("""
      SELECT to_date(EVENT_AT) EVENT_DATE, EVENT_TYPE, COUNT(*) EVENT_COUNT,
             COUNT(DISTINCT ACTOR_USER_ID) ACTORS
      FROM AUDIT_EVENT GROUP BY to_date(EVENT_AT), EVENT_TYPE
    """)
    BatchSupport.save(result, "audit", "audit_daily_summary", Some("sfx_audit.SPARK_AUDIT_SUMMARY"))
    spark.stop()
  }
}
