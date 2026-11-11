#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1g --executor-cores 1 --total-executor-cores 3 --conf spark.sql.shuffle.partitions=12 \
  --py-files /opt/sfx/spark/.cache/common.zip /opt/sfx/spark/jobs/py/billing_gl_trial_balance.py
