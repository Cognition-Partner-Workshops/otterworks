#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1100m --executor-cores 1 --num-executors 3 --conf spark.sql.shuffle.partitions=10 \
  --class sfx.DocsShareActivity /opt/sfx/spark/.cache/sfx-spark-jobs.jar
