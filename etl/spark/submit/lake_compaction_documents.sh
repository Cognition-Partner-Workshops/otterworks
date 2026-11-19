#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1500m --executor-cores 2 --total-executor-cores 4 --conf spark.sql.files.maxPartitionBytes=16777216 \
  --class sfx.LakeCompactionDocuments /opt/sfx/spark/.cache/sfx-spark-jobs.jar
