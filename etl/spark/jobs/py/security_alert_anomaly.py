from datetime import datetime, timezone
import math
import os
from pathlib import Path
import re
import shutil

from common.runtime import landing, save_jdbc_refresh, save_partition, session


def anomaly_scores(spark, alerts):
    records = alerts.rdd.map(lambda r: (r.SECURITY_ALERT_ID, r.USER_ID, float(r.SCORE)))
    count, total, squares = records.map(lambda r: (1, r[2], r[2] ** 2)).fold(
        (0, 0.0, 0.0), lambda a, b: tuple(x + y for x, y in zip(a, b))
    )
    mean = total / max(count, 1)
    stddev = math.sqrt(max(squares / max(count, 1) - mean ** 2, 0.0)) or 1.0
    result = records.map(lambda r: (r[0], r[1], r[2], (r[2] - mean) / stddev))
    return spark.createDataFrame(result, "ALERT_ID long, USER_ID long, SCORE double, Z_SCORE double")


def drop_unpartitioned(path):
    root = Path(path)
    if not root.is_dir():
        return
    for entry in root.iterdir():
        if entry.name.startswith("run_date="):
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def main():
    spark = session("security_alert_anomaly")
    try:
        run_date = os.environ.get("SFX_RUN_DATE") or datetime.now(timezone.utc).date().isoformat()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_date):
            raise ValueError("run_date must be YYYY-MM-DD")
        datetime.strptime(run_date, "%Y-%m-%d")
        frame = anomaly_scores(spark, landing(spark, "SECURITY_ALERT"))
        drop_unpartitioned(f"{os.environ.get('LAKE_DIR', '/opt/lake')}/audit/security_alert_anomaly")
        save_partition(frame, "audit", "security_alert_anomaly", run_date)
        save_jdbc_refresh(frame, "sfx_audit.SPARK_ALERT_ANOMALY")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
