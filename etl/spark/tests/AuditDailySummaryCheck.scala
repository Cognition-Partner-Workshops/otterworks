package sfx

import java.nio.charset.StandardCharsets
import java.nio.file.Files
import org.apache.spark.sql.SparkSession

object AuditDailySummaryCheck {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder.appName("audit-summary-check").getOrCreate()
    spark.conf.set("spark.sql.shuffle.partitions", "2")
    val directory = Files.createTempDirectory("audit-summary")
    val path = directory.resolve("events.psv")
    val header = "AUDIT_EVENT_ID|ACTOR_USER_ID|DOCUMENT_ID|EVENT_TYPE|EVENT_AT|DETAILS\n"
    try {
      Files.write(path, (header +
        "1|10|20|view|2026-11-09 01:00:00|a\n" +
        "2|10|20|view|2026-11-09 02:00:00|b\n" +
        "3||20|view|2026-11-09 03:00:00|c\n" +
        "4|11|20|edit|2026-11-10 01:00:00|d\n").getBytes(StandardCharsets.UTF_8))
      val events = AuditDailySummary.landing(spark, path.toString)
      val result = AuditDailySummary.summarize(events)
      assert(result.columns.toSeq == Seq("EVENT_DATE", "EVENT_TYPE", "EVENT_COUNT", "ACTORS"))
      val rows = result.orderBy("EVENT_DATE", "EVENT_TYPE").collect()
      assert(rows.length == 2)
      assert(rows(0).getDate(0).toString == "2026-11-09")
      assert(rows(0).getString(1) == "view")
      assert(rows(0).getLong(2) == 3 && rows(0).getLong(3) == 1)
      assert(rows(1).getLong(2) == 1 && rows(1).getLong(3) == 1)
      assert(AuditDailySummary.summarize(events.limit(0)).count() == 0)
      var failed = false
      try AuditDailySummary.landing(spark, directory.resolve("missing.psv").toString).count()
      catch { case _: org.apache.spark.sql.AnalysisException => failed = true }
      assert(failed)
      println("AUDIT_SUMMARY normal, empty and missing-input checks passed")
    } finally {
      spark.stop()
      Files.deleteIfExists(path)
      Files.deleteIfExists(directory)
    }
  }
}
