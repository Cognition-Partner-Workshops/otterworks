#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD=Fake-sfx1119-jdbc
export AWS_ACCESS_KEY_ID=Fake-sfx1119-access
export AWS_SECRET_ACCESS_KEY=Fake-sfx1119-secret
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1g --executor-cores 1 --num-executors 2 --conf spark.sql.shuffle.partitions=8 \
  --class sfx.ComplianceFlagRules /opt/sfx/spark/.cache/sfx-spark-jobs.jar
