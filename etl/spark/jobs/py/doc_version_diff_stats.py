import difflib
from pyspark.sql.functions import col, lag, udf
from pyspark.sql.types import DoubleType
from pyspark.sql.window import Window
from common.runtime import landing, save, session


@udf(DoubleType())
def similarity(before, after):
    return difflib.SequenceMatcher(None, before or "", after or "").ratio()


spark = session("doc_version_diff_stats")
versions = landing(spark, "DOC_VERSION")
previous = lag("BODY").over(Window.partitionBy("DOCUMENT_ID").orderBy("VERSION_NUMBER"))
result = versions.withColumn("PREVIOUS_BODY", previous).withColumn("SIMILARITY", similarity(col("PREVIOUS_BODY"), col("BODY")))
save(result, "documents", "doc_version_diff_stats")
spark.stop()
