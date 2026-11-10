import re
from pyspark.sql.functions import col, udf
from pyspark.sql.types import StringType
from common.runtime import landing, save, session


@udf(StringType())
def browser(agent):
    match = re.search(r"(Chrome|Firefox|Safari)/(\S+)", agent or "")
    return match.group(1) + "/" + match.group(2) if match else "Other"


spark = session("users_login_useragent_parse")
result = landing(spark, "LOGIN_EVENT").withColumn("BROWSER", browser(col("USER_AGENT")))
save(result, "users", "users_login_useragent_parse")
spark.stop()
