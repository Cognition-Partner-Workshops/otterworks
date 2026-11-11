# Databricks notebook source
"""Serverless PySpark entry point; require the migration to supply real logic."""
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
spark.conf.set("spark.sql.adaptive.enabled", "true")
source = spark.table("cpw.dbx_d1111_before.billing__invoice_hdr")
# This receipt validates access only. A count is not migration parity.
print({"run_token": "dbx-d1111", "baseline_rows": source.count()})
