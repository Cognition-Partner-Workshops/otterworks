from common.runtime import register, save, session

spark = session("docs_storage_by_owner")
register(spark, "DOCUMENT", "FILE_OBJECT", "APP_USER")
result = spark.sql("""
SELECT u.USER_ID, u.EMAIL, COUNT(*) FILE_COUNT, SUM(f.SIZE_BYTES) SIZE_BYTES
FROM DOCUMENT d JOIN FILE_OBJECT f ON d.DOCUMENT_ID = f.DOCUMENT_ID
JOIN APP_USER u ON d.OWNER_USER_ID = u.USER_ID GROUP BY u.USER_ID, u.EMAIL
""")
save(result, "documents", "docs_storage_by_owner")
spark.stop()
