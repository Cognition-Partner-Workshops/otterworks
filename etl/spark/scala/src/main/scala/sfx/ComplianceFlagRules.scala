package sfx

import org.apache.spark.sql.DataFrame
import org.apache.spark.sql.functions.col

object ComplianceFlagRules {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("compliance_flag_rules")
    val result = transform(BatchSupport.landing(spark, "audit", "COMPLIANCE_FLAG"))
    val runDate = sys.env.getOrElse("SFX_RUN_DATE", java.time.LocalDate.now(java.time.ZoneOffset.UTC).toString)
    BatchSupport.savePartition(result, "audit", "compliance_flag_rules", runDate)
    BatchSupport.saveJdbcRefresh(result, "sfx_audit.SPARK_COMPLIANCE_REVIEW")
    spark.stop()
  }

  def transform(frame: DataFrame): DataFrame = {
    val spark = frame.sparkSession
    import spark.implicits._
    frame.withColumn("COMPLIANCE_FLAG_ID", col("COMPLIANCE_FLAG_ID").cast("long"))
      .withColumn("DOCUMENT_ID", col("DOCUMENT_ID").cast("long")).rdd.mapPartitions { rows =>
      val threshold = 7000
      rows.map { row =>
        val severity = row.getAs[Int]("SEVERITY")
        val status = row.getAs[String]("STATUS")
        val disposition =
          if (status == "closed") "resolved"
          else if (severity >= threshold) "review"
          else "monitor"
        (row.getAs[Long]("COMPLIANCE_FLAG_ID"),
         row.getAs[Long]("DOCUMENT_ID"), severity, disposition)
      }
    }.toDF("FLAG_ID", "DOCUMENT_ID", "SEVERITY", "DISPOSITION")
  }
}
