import re
from pyspark.sql.functions import col, udf
from pyspark.sql.types import StringType
from common.runtime import landing, save, session


@udf(StringType())
def parse_action(line):
    match = re.search(r"action=(\w+)", line or "")
    return match.group(1) if match else None


spark = session("docs_search_log_parse")
result = landing(spark, "SEARCH_INDEX_LOG").withColumn("PARSED_ACTION", parse_action(col("RAW_LINE")))
save(result, "documents", "docs_search_log_parse")
spark.stop()
