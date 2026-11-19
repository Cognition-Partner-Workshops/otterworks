import os
from pathlib import Path
import re
import shutil
import uuid

from common.runtime import (
    jdbc_options, quote_identifier, refresh_columns, register, save_partition, session, target_columns,
)

LAKE_AREA = "billing"
LAKE_NAME = "billing_usage_append_daily"
JDBC_TABLE = "sfx_billing.SPARK_USAGE_DAILY"


def drop_unpartitioned(path):
    """Legacy runs appended parquet straight into the job directory; keep only run_date= partitions."""
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


def replace_usage_date(frame, table, usage_date):
    """Stage the rows, then replace exactly one USAGE_DATE in the target in one transaction."""
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]*\.[a-zA-Z_][a-zA-Z_0-9]*", table):
        raise ValueError("Expected schema.table identifier")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", usage_date):
        raise ValueError("usage_date must be YYYY-MM-DD")
    options = jdbc_options()
    stage = table.split(".")[0] + "._sfx_stage_" + uuid.uuid4().hex
    jvm = frame.sparkSession.sparkContext._jvm
    connection = jvm.java.sql.DriverManager.getConnection(options["url"], options["user"], options["password"])
    statement = connection.createStatement()
    try:
        frame.write.format("jdbc").options(**options).option("dbtable", stage).mode("error").save()
        connection.setAutoCommit(False)
        # JDBC identifiers cannot be bound; table is regex-validated, stage adds only a UUID, date is validated.
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        statement.execute(f"CREATE TABLE IF NOT EXISTS {table} (LIKE {stage} INCLUDING ALL)")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        statement.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        pairs = refresh_columns(frame.columns, target_columns(connection, table))
        date_column = next(target for target, source in pairs if source == "USAGE_DATE")
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        statement.executeUpdate(f"DELETE FROM {table} WHERE {quote_identifier(date_column)} = DATE '{usage_date}'")
        targets = ", ".join(quote_identifier(target) for target, _ in pairs)
        sources = ", ".join(quote_identifier(source) for _, source in pairs)
        # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        statement.executeUpdate(f"INSERT INTO {table} ({targets}) SELECT {sources} FROM {stage}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.setAutoCommit(True)
            # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            statement.execute(f"DROP TABLE IF EXISTS {stage}")
        finally:
            statement.close()
            connection.close()


def main():
    spark = session("billing_usage_append_daily")
    register(spark, "USAGE_DAILY")
    usage = spark.table("USAGE_DAILY").cache()
    latest = usage.agg({"USAGE_DATE": "max"}).first()[0]
    if latest is None:
        print("USAGE_ROWS=0")
        spark.stop()
        return
    usage_date = latest.isoformat()
    result = usage.where(f"USAGE_DATE = DATE '{usage_date}'")
    drop_unpartitioned(f"{os.environ.get('LAKE_DIR', '/opt/lake')}/{LAKE_AREA}/{LAKE_NAME}")
    save_partition(result, LAKE_AREA, LAKE_NAME, usage_date)
    replace_usage_date(result, JDBC_TABLE, usage_date)
    print(f"USAGE_ROWS={result.count()} USAGE_DATE={usage_date}")
    spark.stop()


if __name__ == "__main__":
    main()
