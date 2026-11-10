from pyspark.sql.functions import col, regexp_extract, sum as total, udf
from pyspark.sql.types import LongType, StringType, StructField, StructType
from common.binary_documents import extract_document
from common.runtime import landing, save, session


EXTRACT_SCHEMA = StructType([
    StructField("MEDIA_TYPE", StringType()), StructField("TEXT", StringType()),
    StructField("PAGE_COUNT", LongType()), StructField("SHA256", StringType()),
    StructField("ERROR", StringType()),
])


extract = udf(extract_document, EXTRACT_SCHEMA)


spark = session("file_object_binary_extract")
files = spark.read.format("binaryFile").load("/opt/landing/documents/FILE_OBJECT_BLOBS/*")
stats = files.agg(total("length").alias("bytes")).first()
print(f"BINARY_INPUT_FILES={len(files.inputFiles())} BINARY_INPUT_BYTES={stats.bytes or 0}")
extracted = files.select(
    regexp_extract("path", r"(documents/FILE_OBJECT_BLOBS/[^/]+)$", 1).alias("STORAGE_KEY"),
    extract(col("content")).alias("EXTRACT"),
).select("STORAGE_KEY", "EXTRACT.*").cache()
extracted.count()
objects = landing(spark, "FILE_OBJECT")
result = objects.join(extracted, "STORAGE_KEY")
save(result, "documents", "file_object_binary_extract")
print(f"BINARY_OUTPUT_ROWS={result.count()}")
spark.stop()
