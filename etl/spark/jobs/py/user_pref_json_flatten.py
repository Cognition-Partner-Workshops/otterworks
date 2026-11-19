import json
from pyspark.sql.functions import col, udf
from pyspark.sql.types import StringType, StructField, StructType
from common.runtime import landing, save, session


def preferences(raw):
    try:
        parsed = json.loads(raw or "{}")
        return tuple(str(parsed.get(key, "")) for key in ("theme", "notifications", "locale"))
    except (ValueError, TypeError):
        return (None, None, None)


def main():
    spark = session("user_pref_json_flatten")
    extract = udf(preferences, StructType([
        StructField(key, StringType(), True) for key in ("THEME", "NOTIFICATIONS", "LOCALE")
    ]))
    result = landing(spark, "USER_PREF").withColumn("_preferences", extract(col("PREF_JSON")))
    save(result.select("USER_PREF_ID", "USER_ID", "PREF_JSON", "_preferences.*"),
         "users", "user_pref_json_flatten")
    spark.stop()


if __name__ == "__main__":
    main()
