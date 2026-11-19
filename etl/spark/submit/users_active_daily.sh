#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 768m --executor-cores 1 --total-executor-cores 2 --conf spark.sql.shuffle.partitions=7 --conf spark.shuffle.memoryFraction=0.2 --conf spark.yarn.executor.memoryOverhead=384 \
  --py-files /opt/sfx/spark/.cache/common.zip /opt/sfx/spark/jobs/py/users_active_daily.py
