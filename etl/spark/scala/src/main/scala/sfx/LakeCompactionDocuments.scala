package sfx

import java.time.{LocalDate, ZoneOffset}
import org.apache.spark.sql.execution.datasources.{HadoopFsRelation, LogicalRelation}

object LakeCompactionDocuments {
  def main(args: Array[String]): Unit = {
    val runDate = sys.env.get("SFX_RUN_DATE").map { value =>
      require(value.matches("\\d{4}-\\d{2}-\\d{2}"), "SFX_RUN_DATE must be YYYY-MM-DD")
      LocalDate.parse(value).toString
    }.getOrElse(LocalDate.now(ZoneOffset.UTC).toString)
    val spark = BatchSupport.session("lake_compaction_documents")
    try {
      spark.conf.set("spark.sql.sources.parallelPartitionDiscovery.threshold", "100000")
      val source = spark.read.option("basePath", "/opt/lake/documents/docs_event_export_hourly")
        .parquet("/opt/lake/documents/docs_event_export_hourly")
      val inputBytes = source.queryExecution.analyzed.collect {
        case LogicalRelation(relation: HadoopFsRelation, _, _, _) => relation.location.sizeInBytes
      }.sum
      val targetBytes = 128L * 1024 * 1024
      val partitions = math.max(1L, (inputBytes + targetBytes - 1) / targetBytes).min(Int.MaxValue).toInt
      val output = if (partitions <= source.rdd.getNumPartitions) source.coalesce(partitions)
        else source.repartition(partitions)
      BatchSupport.savePartition(output, "documents", "lake_compaction_documents", runDate)
    } finally {
      spark.stop()
    }
  }
}
