package sfx

import java.time.{LocalDate, ZoneOffset}

object AuditDailySummary {
  def main(args: Array[String]): Unit = {
    val runDate = sys.env.get("SFX_RUN_DATE").map { value =>
      require(value.matches("\\d{4}-\\d{2}-\\d{2}"), "SFX_RUN_DATE must be YYYY-MM-DD")
      LocalDate.parse(value).toString
    }.getOrElse(LocalDate.now(ZoneOffset.UTC).toString)
    val spark = BatchSupport.session("audit_daily_summary")
    try {
      BatchSupport.register(spark, "audit", "AUDIT_EVENT")
      val result = spark.sql("""
      SELECT to_date(EVENT_AT) EVENT_DATE, EVENT_TYPE, COUNT(*) EVENT_COUNT,
             COUNT(DISTINCT ACTOR_USER_ID) ACTORS
      FROM AUDIT_EVENT GROUP BY to_date(EVENT_AT), EVENT_TYPE
      """)
      BatchSupport.savePartition(result, "audit", "audit_daily_summary", runDate)
      BatchSupport.saveJdbcRefresh(result, "sfx_audit.SPARK_AUDIT_SUMMARY")
    } finally spark.stop()
  }
}
