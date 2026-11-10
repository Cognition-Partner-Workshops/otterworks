import json
from pyspark.sql.functions import col, lit, udf
from pyspark.sql.types import StringType
from common.runtime import landing, save, session


@udf(StringType())
def preference(raw, key):
    try:
        return str(json.loads(raw or "{}").get(key, ""))
    except (ValueError, TypeError):
        return None


spark = session("user_pref_json_flatten")
result = landing(spark, "USER_PREF")
for key in ("theme", "notifications", "locale"):
    result = result.withColumn(key.upper(), preference(col("PREF_JSON"), lit(key)))
save(result, "users", "user_pref_json_flatten")
spark.stop()
