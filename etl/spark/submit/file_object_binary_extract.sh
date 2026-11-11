#!/usr/bin/env bash
# Kept on Spark (common Spark template): binaryFile source over the self-run blob store.
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
exec /opt/sfx/spark/template/submit.sh --job file_object_binary_extract --output documents/file_object_binary_extract -- \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 768m --executor-cores 1 --total-executor-cores 3 \
  --py-files /opt/sfx/spark/.cache/common.zip /opt/sfx/spark/jobs/py/file_object_binary_extract.py
