package sfx

object DocsShareActivity {
  def main(args: Array[String]): Unit = {
    val spark = BatchSupport.session("docs_share_activity")
    BatchSupport.register(spark, "documents", "DOC_SHARE", "DOCUMENT")
    val result = spark.sql("""
      SELECT d.OWNER_USER_ID, s.PERMISSION, COUNT(*) SHARES,
             COUNT(DISTINCT s.SHARED_WITH_USER_ID) RECIPIENTS
      FROM DOC_SHARE s JOIN DOCUMENT d ON s.DOCUMENT_ID = d.DOCUMENT_ID
      GROUP BY d.OWNER_USER_ID, s.PERMISSION
    """)
    BatchSupport.save(result, "documents", "docs_share_activity")
    spark.stop()
  }
}
