#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD=etl_batch_dev # gitleaks:allow
export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE # gitleaks:allow
export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY # gitleaks:allow
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1200m --executor-cores 1 --num-executors 2 --conf spark.sql.shuffle.partitions=8 \
  --class sfx.AuditDailySummary /opt/sfx/spark/.cache/sfx-spark-jobs.jar
