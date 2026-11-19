from pyspark.sql.functions import col, concat, lit, regexp_extract, when
from common.runtime import landing, save, session

# Python str-mode \S: every character except those for which str.isspace() is true.
NON_SPACE = "[^\\t\\n\\x0B\\f\\r\\x1C-\\x1F \\x85\\xA0\\u1680\\u2000-\\u200A\\u2028\\u2029\\u202F\\u205F\\u3000]"
PATTERN = f"(Chrome|Firefox|Safari)/({NON_SPACE}+)"


def browser(agent):
    return when(agent.rlike(PATTERN), concat(
        regexp_extract(agent, PATTERN, 1), lit("/"), regexp_extract(agent, PATTERN, 2),
    )).otherwise(lit("Other"))


if __name__ == "__main__":
    spark = session("users_login_useragent_parse")
    result = landing(spark, "LOGIN_EVENT").withColumn("BROWSER", browser(col("USER_AGENT")))
    save(result, "users", "users_login_useragent_parse")
    spark.stop()
