from datetime import datetime, timezone
import os

from common.runtime import register, save_partition, session

spark = session("audit_actor_activity_join")
register(spark, "AUDIT_EVENT", "USER_ACTIVITY_DAILY", "LOGIN_EVENT")
result = spark.sql("""
WITH activity AS (
    SELECT CASE WHEN LOGIN_COUNT > 12 THEN 0 ELSE USER_ID END USER_KEY,
           ACTIVITY_DATE, SUM(LOGIN_COUNT) LOGIN_COUNT, SUM(ACTION_COUNT) ACTION_COUNT
    FROM USER_ACTIVITY_DAILY
    GROUP BY CASE WHEN LOGIN_COUNT > 12 THEN 0 ELSE USER_ID END, ACTIVITY_DATE
), logins AS (
    SELECT CASE WHEN hour(EVENT_AT) < 8 THEN 0 ELSE USER_ID END USER_KEY,
           MAX(USER_AGENT) USER_AGENT,
           CAST(coalesce(SUM(octet_length(RAW_LINE)), 0) + greatest(COUNT(RAW_LINE) - 1, 0) AS INT) LOGIN_TEXT_BYTES
    FROM LOGIN_EVENT
    GROUP BY CASE WHEN hour(EVENT_AT) < 8 THEN 0 ELSE USER_ID END
)
SELECT coalesce(a.ACTOR_USER_ID, 0) USER_KEY, a.AUDIT_EVENT_ID,
       a.EVENT_AT, d.ACTIVITY_DATE, d.ACTION_COUNT, l.USER_AGENT,
       l.LOGIN_TEXT_BYTES
FROM AUDIT_EVENT a
JOIN activity d ON coalesce(a.ACTOR_USER_ID, 0) = d.USER_KEY
JOIN logins l ON coalesce(a.ACTOR_USER_ID, 0) = l.USER_KEY
""").cache()
run_date = os.environ.get("SFX_RUN_DATE") or datetime.now(timezone.utc).date().isoformat()
save_partition(result, "audit", "audit_actor_activity_join", run_date)
result.unpersist()
spark.stop()
