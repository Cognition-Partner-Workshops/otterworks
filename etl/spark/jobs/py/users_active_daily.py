from common.runtime import landing, save, session

spark = session("users_active_daily")
landing(spark, "USER_ACTIVITY_DAILY").createOrReplaceTempView("USER_ACTIVITY_DAILY")
result = spark.sql("""
SELECT ACTIVITY_DATE, COUNT(DISTINCT USER_ID) ACTIVE_USERS,
SUM(LOGIN_COUNT) LOGINS, SUM(ACTION_COUNT) ACTIONS
FROM USER_ACTIVITY_DAILY GROUP BY ACTIVITY_DATE
""")
save(result, "users", "users_active_daily")
spark.stop()
