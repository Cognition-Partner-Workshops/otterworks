from pyspark.sql.functions import coalesce, col, lit, lower, regexp_replace
from common.runtime import landing, save, session

# Exactly the characters Python's str.isspace() and re's \s match, so the native
# expression reproduces the former Python UDF: strip, lowercase, collapse runs to "-".
WHITESPACE = "[\\t\\n\\x0b\\x0c\\r\\x1c-\\x1f \\x85\\xa0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000]"


def normalized(tag):
    stripped = regexp_replace(coalesce(tag, lit("")), f"^{WHITESPACE}+|{WHITESPACE}+$", "")
    return regexp_replace(lower(stripped), f"{WHITESPACE}+", "-")


if __name__ == "__main__":
    spark = session("docs_tag_normalize")
    save(landing(spark, "DOC_TAG").withColumn("NORMALIZED_TAG", normalized(col("TAG"))),
         "documents", "docs_tag_normalize")
    spark.stop()
