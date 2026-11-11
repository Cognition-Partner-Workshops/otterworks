# Databricks notebook source
"""Lakeflow conversion entry point; mappings supply their own transformations."""
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(name="billing_invoice_header", comment="run_token=dbx-d1111 expires=2026-11-24")
def billing_invoice_header():
    return (spark.read.table("cpw.dbx_d1111_bronze.invoice_hdr")  # noqa: F821
            .withColumn("currency_cd", F.upper(F.rtrim("currency_cd"))))
