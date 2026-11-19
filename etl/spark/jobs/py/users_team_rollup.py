from datetime import datetime, timezone
import os
from pathlib import Path

from common.runtime import register, save_jdbc_refresh, save_partition, session


def main():
    spark = session("users_team_rollup")
    try:
        run_date = os.environ.get("SFX_RUN_DATE") or datetime.now(timezone.utc).date().isoformat()
        register(spark, "TEAM", "TEAM_MEMBER", "APP_USER")
        result = spark.sql("""
SELECT t.TEAM_ID, t.TEAM_NAME, COUNT(m.USER_ID) MEMBERS
FROM TEAM t LEFT JOIN TEAM_MEMBER m ON t.TEAM_ID = m.TEAM_ID
LEFT JOIN APP_USER u ON m.USER_ID = u.USER_ID GROUP BY t.TEAM_ID, t.TEAM_NAME
""")
        save_partition(result, "users", "users_team_rollup", run_date)
        root = Path(os.environ.get("LAKE_DIR", "/opt/lake")) / "users/users_team_rollup"
        for path in root.glob("*.parquet"):
            path.unlink()
        save_jdbc_refresh(result, "sfx_users.SPARK_TEAM_ROLLUP")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
