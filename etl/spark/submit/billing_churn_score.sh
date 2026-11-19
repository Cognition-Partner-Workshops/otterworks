#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1200m --executor-cores 1 --num-executors 3 --conf spark.sql.shuffle.partitions=12 \
  --py-files /opt/sfx/spark/.cache/common.zip /opt/sfx/spark/jobs/py/billing_churn_score.py
