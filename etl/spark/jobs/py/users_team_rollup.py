from common.runtime import register, save, session

spark = session("users_team_rollup")
register(spark, "TEAM", "TEAM_MEMBER", "APP_USER")
result = spark.sql("""
SELECT t.TEAM_ID, t.TEAM_NAME, COUNT(m.USER_ID) MEMBERS
FROM TEAM t LEFT JOIN TEAM_MEMBER m ON t.TEAM_ID = m.TEAM_ID
LEFT JOIN APP_USER u ON m.USER_ID = u.USER_ID GROUP BY t.TEAM_ID, t.TEAM_NAME
""")
save(result, "users", "users_team_rollup", "sfx_users.SPARK_TEAM_ROLLUP")
spark.stop()
