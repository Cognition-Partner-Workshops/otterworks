import os

from pyspark.sql import SparkSession
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
