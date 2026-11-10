#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1200m --executor-cores 2 --total-executor-cores 4 --conf spark.default.parallelism=4 \
  --class sfx.TeamGraphComponents /opt/sfx/spark/.cache/sfx-spark-jobs.jar
