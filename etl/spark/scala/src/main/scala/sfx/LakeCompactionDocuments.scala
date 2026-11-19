package sfx

object LakeCompactionDocuments {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("lake_compaction_documents")
    val source = spark.read.option("basePath", "/opt/lake/documents/docs_event_export_hourly")
      .parquet("/opt/lake/documents/docs_event_export_hourly")
    BatchSupport.save(source.coalesce(4), "documents", "lake_compaction_documents")
    spark.stop()
  }
}
