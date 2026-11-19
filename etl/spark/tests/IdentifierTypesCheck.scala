package sfx

import org.apache.spark.sql.{AnalysisException, Row, SparkSession}
import org.apache.spark.sql.types._

object IdentifierTypesCheck {
  def main(args: Array[String]): Unit = {
    val spark = SparkSession.builder.appName("identifier-types-check").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    try {
      for (idType <- Seq(IntegerType, LongType)) {
        val base = if (idType == IntegerType) 17L else 3000000000L
        def id(value: Long): Any = if (idType == IntegerType) Int.box(value.toInt) else Long.box(value)
        val flags = spark.createDataFrame(java.util.Arrays.asList(
          Row(id(base), id(base + 10), 7000, "open"),
          Row(id(base + 1), id(base + 11), 1, "closed")), StructType(Seq(
          StructField("COMPLIANCE_FLAG_ID", idType), StructField("DOCUMENT_ID", idType),
          StructField("SEVERITY", IntegerType), StructField("STATUS", StringType))))
        val result = ComplianceFlagRules.transform(flags)
        assert(result.schema("FLAG_ID").dataType == LongType)
        assert(result.schema("DOCUMENT_ID").dataType == LongType)
        val rows = result.orderBy("FLAG_ID").collect()
        assert(rows.map(_.getLong(0)).toSeq == Seq(base, base + 1))
        assert(rows.map(_.getLong(1)).toSeq == Seq(base + 10, base + 11))
        assert(rows.map(_.getString(3)).toSeq == Seq("review", "resolved"))
        assert(ComplianceFlagRules.transform(flags.limit(0)).collect().isEmpty)

        val members = spark.createDataFrame(java.util.Arrays.asList(
          Row(id(base + 20), id(base)), Row(id(base + 20), id(base + 1))), StructType(Seq(
          StructField("TEAM_ID", idType), StructField("USER_ID", idType))))
        val components = TeamGraphComponents.transform(members)
        assert(components.schema("USER_ID").dataType == LongType)
        assert(components.schema("COMPONENT_ID").dataType == LongType)
        assert(components.collect().map(r => r.getLong(0) -> r.getLong(1)).toMap ==
          Map(base -> base, (base + 1) -> base))
        assert(TeamGraphComponents.transform(members.limit(0)).collect().isEmpty)
      }
      for (transform <- Seq(ComplianceFlagRules.transform _, TeamGraphComponents.transform _)) {
        var rejected = false
        try transform(spark.emptyDataFrame) catch { case _: AnalysisException => rejected = true }
        assert(rejected, "Missing identifier columns must fail analysis")
      }
      println("SCALA_IDS IntegerType, LongType (>2^31), empty inputs and missing columns: OK")
    } finally spark.stop()
  }
}
