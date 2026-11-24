#!/usr/bin/env bash
set -e
: "${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1200m --executor-cores 1 --num-executors 2 --conf spark.sql.shuffle.partitions=8 \
  --class sfx.AuditDailySummary /opt/sfx/spark/.cache/sfx-spark-jobs.jar
