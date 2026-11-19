#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1g --executor-cores 2 --total-executor-cores 4 --conf spark.sql.shuffle.partitions=14 \
  --py-files /opt/sfx/spark/.cache/common.zip /opt/sfx/spark/jobs/py/users_team_rollup.py
