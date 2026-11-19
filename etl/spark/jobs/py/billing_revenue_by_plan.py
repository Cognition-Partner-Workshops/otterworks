from datetime import datetime, timezone
import os

from common.runtime import landing, save_partition, session


def main():
    run_date = os.environ.get("SFX_RUN_DATE") or datetime.now(timezone.utc).date().isoformat()
    spark = session("billing_revenue_by_plan")
    try:
        landing(spark, "INVOICE_LINE").createOrReplaceTempView("INVOICE_LINE")
        landing(spark, "PLAN_CATALOG").createOrReplaceTempView("PLAN_CATALOG")
        result = spark.sql("""
            SELECT p.PLAN_ID, p.PLAN_NAME, SUM(l.AMOUNT) REVENUE
            FROM INVOICE_LINE l JOIN PLAN_CATALOG p ON l.PLAN_ID = p.PLAN_ID
            GROUP BY p.PLAN_ID, p.PLAN_NAME
        """)
        save_partition(result, "billing", "billing_revenue_by_plan", run_date)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
