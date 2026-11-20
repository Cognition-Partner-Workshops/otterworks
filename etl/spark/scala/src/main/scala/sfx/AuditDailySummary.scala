package sfx

import org.apache.spark.sql.{DataFrame, SparkSession}

object AuditDailySummary {
  def landing(spark: SparkSession, path: String): DataFrame =
    spark.read.option("header", "true").option("sep", "|").option("escape", "\"")
      .schema("AUDIT_EVENT_ID BIGINT, ACTOR_USER_ID BIGINT, DOCUMENT_ID BIGINT, EVENT_TYPE STRING, EVENT_AT TIMESTAMP, DETAILS STRING")
      .csv(path)

  def summarize(events: DataFrame): DataFrame = {
    events.createOrReplaceTempView("AUDIT_EVENT")
    events.sparkSession.sql("""
      SELECT to_date(EVENT_AT) EVENT_DATE, EVENT_TYPE, COUNT(*) EVENT_COUNT,
             COUNT(DISTINCT ACTOR_USER_ID) ACTORS
      FROM AUDIT_EVENT GROUP BY to_date(EVENT_AT), EVENT_TYPE
    """)
  }

  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("audit_daily_summary")
    try {
      spark.conf.set("spark.sql.shuffle.partitions", "2")
      val events = landing(spark, s"${sys.env.getOrElse("LANDING_DIR", "/opt/landing")}/audit/AUDIT_EVENT/*.psv").cache()
      try {
        val result = summarize(events).coalesce(1).cache()
        try {
          result.write.mode("overwrite").parquet(
            s"${sys.env.getOrElse("LAKE_DIR", "/opt/lake")}/audit/audit_daily_summary")
          BatchSupport.saveJdbcRefresh(result, "sfx_audit.SPARK_AUDIT_SUMMARY")
        } finally result.unpersist()
      } finally events.unpersist()
    } finally spark.stop()
  }
}
