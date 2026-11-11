package sfx

object ComplianceFlagRules {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("compliance_flag_rules")
    import spark.implicits._
    val result = BatchSupport.landing(spark, "audit", "COMPLIANCE_FLAG").rdd.mapPartitions { rows =>
      val threshold = 7000
      rows.map { row =>
        val severity = row.getAs[Int]("SEVERITY")
        val status = row.getAs[String]("STATUS")
        val disposition =
          if (status == "closed") "resolved"
          else if (severity >= threshold) "review"
          else "monitor"
        (row.getAs[Int]("COMPLIANCE_FLAG_ID").toLong,
         row.getAs[Int]("DOCUMENT_ID").toLong, severity, disposition)
      }
    }.toDF("FLAG_ID", "DOCUMENT_ID", "SEVERITY", "DISPOSITION")
    BatchSupport.save(result, "audit", "compliance_flag_rules", Some("sfx_audit.SPARK_COMPLIANCE_REVIEW"))
    spark.stop()
  }
}
