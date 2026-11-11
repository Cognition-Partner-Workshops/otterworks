from pyspark.sql import SQLContext
from common.runtime import landing, save, session

spark = session("docs_folder_legacy_report")
sql = SQLContext(spark.sparkContext)
landing(spark, "FOLDER").registerTempTable("FOLDER")
landing(spark, "DOCUMENT").registerTempTable("DOCUMENT")
result = sql.sql("""
SELECT f.FOLDER_ID, f.FOLDER_NAME, f.PARENT_FOLDER_ID, COUNT(d.DOCUMENT_ID) DOCUMENTS
FROM FOLDER f LEFT JOIN DOCUMENT d ON f.FOLDER_ID = d.FOLDER_ID
GROUP BY f.FOLDER_ID, f.FOLDER_NAME, f.PARENT_FOLDER_ID
""")
save(result, "documents", "docs_folder_legacy_report")
spark.stop()
