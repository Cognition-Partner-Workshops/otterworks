import math
from common.runtime import landing, save, session

spark = session("security_alert_anomaly")
records = landing(spark, "SECURITY_ALERT").rdd.map(lambda r: (r.SECURITY_ALERT_ID, r.USER_ID, float(r.SCORE)))
count, total, squares = records.map(lambda r: (1, r[2], r[2] ** 2)).fold(
    (0, 0.0, 0.0), lambda a, b: tuple(x + y for x, y in zip(a, b))
)
mean = total / max(count, 1)
stddev = math.sqrt(max(squares / max(count, 1) - mean ** 2, 0.0)) or 1.0
result = records.map(lambda r: (r[0], r[1], r[2], (r[2] - mean) / stddev))
frame = spark.createDataFrame(result, "ALERT_ID long, USER_ID long, SCORE double, Z_SCORE double")
save(frame, "audit", "security_alert_anomaly", "sfx_audit.SPARK_ALERT_ANOMALY")
spark.stop()
