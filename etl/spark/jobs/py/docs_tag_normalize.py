import re
from pyspark.sql.functions import col, udf
from pyspark.sql.types import StringType
from common.runtime import landing, save, session


@udf(StringType())
def normalize(tag):
    return re.sub(r"\s+", "-", (tag or "").strip().lower())


spark = session("docs_tag_normalize")
save(landing(spark, "DOC_TAG").withColumn("NORMALIZED_TAG", normalize(col("TAG"))),
     "documents", "docs_tag_normalize")
spark.stop()
