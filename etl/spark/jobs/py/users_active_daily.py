from pyspark.sql import SQLContext
from common.runtime import landing, save, session

spark = session("users_active_daily")
sql = SQLContext(spark.sparkContext)
landing(spark, "USER_ACTIVITY_DAILY").registerTempTable("USER_ACTIVITY_DAILY")
result = sql.sql("""
SELECT ACTIVITY_DATE, COUNT(DISTINCT USER_ID) ACTIVE_USERS,
SUM(LOGIN_COUNT) LOGINS, SUM(ACTION_COUNT) ACTIONS
FROM USER_ACTIVITY_DAILY GROUP BY ACTIVITY_DATE
""")
save(result, "users", "users_active_daily")
spark.stop()
