package sfx

import java.time.{LocalDate, ZoneOffset}
import org.apache.hadoop.fs.Path

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
      val output = new Path(s"${sys.env.getOrElse("LAKE_DIR", "/opt/lake")}/audit/audit_daily_summary")
      val fs = output.getFileSystem(spark.sparkContext.hadoopConfiguration)
      BatchSupport.savePartition(result, "audit", "audit_daily_summary", runDate)
      // The active legacy compactor reads the root as one full-refresh snapshot.
      fs.listStatus(output).filter { entry =>
        val name = entry.getPath.getName
        name.startsWith("run_date=") && name != s"run_date=$runDate" ||
          entry.isFile && (name.endsWith(".parquet") || name.endsWith(".parquet.crc"))
      }.foreach(entry => require(fs.delete(entry.getPath, true), s"Cannot remove ${entry.getPath}"))
      BatchSupport.saveJdbcRefresh(result, "sfx_audit.SPARK_AUDIT_SUMMARY")
    } finally spark.stop()
  }
}
