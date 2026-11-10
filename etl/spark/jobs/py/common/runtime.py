import os
import re
import uuid

from pyspark.sql import SparkSession
from pyspark.sql.functions import lit
from pyspark.sql.types import (
    StructType, StructField, LongType, StringType, DateType, TimestampType, DecimalType,
)

from common.schemas import SCHEMAS, TABLES


def session(name):
    return SparkSession.builder.appName(name).getOrCreate()


def landing(spark, table):
    area = next(area for area, tables in TABLES.items() if table in tables)
    types = {"BIGINT": LongType(), "TEXT": StringType(), "DATE": DateType(), "TIMESTAMP": TimestampType()}
    fields = []
    for name, kind in SCHEMAS[table]:
        datatype = types.get(kind)
        if datatype is None:
            precision, scale = map(int, kind[8:-1].split(","))
            datatype = DecimalType(precision, scale)
        fields.append(StructField(name, datatype, True))
    return spark.read.option("header", True).option("sep", "|").option("escape", '"').schema(StructType(fields)).csv(
        f"{os.environ.get('LANDING_DIR', '/opt/landing')}/{area}/{table}/*.psv"
    )


def register(spark, *tables):
    for table in tables:
        landing(spark, table).registerTempTable(table)


def jdbc_options():
    return {
        "url": os.environ.get("TD_JDBC_URL", "jdbc:postgresql://sfx-tdemu:5432/sfx_teradata"),
        "user": os.environ.get("TD_JDBC_USER", "etl_batch"),
        "password": os.environ["TD_JDBC_PASSWORD"],
        "driver": "org.postgresql.Driver",
    }


def jdbc_read(spark, table):
    return spark.read.format("jdbc").options(**jdbc_options()).option("dbtable", table).load()


def save(frame, area, name, jdbc_table=None, mode="overwrite"):
    frame.write.mode(mode).parquet(f"{os.environ.get('LAKE_DIR', '/opt/lake')}/{area}/{name}")
    if jdbc_table:
        frame.coalesce(2).write.format("jdbc").options(**jdbc_options()).option(
            "dbtable", jdbc_table
        ).mode(mode).save()


def save_partition(frame, area, name, run_date):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_date):
        raise ValueError("run_date must be YYYY-MM-DD")
    path = f"{os.environ.get('LAKE_DIR', '/opt/lake')}/{area}/{name}"
    if frame.isEmpty():
        frame.write.mode("overwrite").option("partitionOverwriteMode", "static").parquet(
            f"{path}/run_date={run_date}"
        )
    else:
        frame.withColumn("run_date", lit(run_date)).write.mode("overwrite").option(
            "partitionOverwriteMode", "dynamic"
        ).partitionBy("run_date").parquet(path)


def save_jdbc_refresh(frame, table):
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]*\.[a-zA-Z_][a-zA-Z_0-9]*", table):
        raise ValueError("Expected schema.table identifier")
    options = jdbc_options()
    stage = table.split(".")[0] + "._sfx_stage_" + uuid.uuid4().hex
    jvm = frame.sparkSession.sparkContext._jvm
    connection = jvm.java.sql.DriverManager.getConnection(options["url"], options["user"], options["password"])
    statement = connection.createStatement()
    try:
        frame.write.format("jdbc").options(**options).option("dbtable", stage).mode("error").save()
        connection.setAutoCommit(False)
        statement.execute(f"CREATE TABLE IF NOT EXISTS {table} (LIKE {stage} INCLUDING ALL)")
        statement.execute(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE")
        statement.executeUpdate(f"DELETE FROM {table}")
        columns = ", ".join('"' + column.replace('"', '""') + '"' for column in frame.columns)
        statement.executeUpdate(f"INSERT INTO {table} ({columns}) SELECT {columns} FROM {stage}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            connection.setAutoCommit(True)
            statement.execute(f"DROP TABLE IF EXISTS {stage}")
        finally:
            statement.close()
            connection.close()
