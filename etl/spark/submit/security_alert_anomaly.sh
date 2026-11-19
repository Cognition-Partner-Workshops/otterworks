#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 900m --executor-cores 1 --num-executors 2 --conf spark.python.worker.memory=96m \
  --py-files /opt/sfx/spark/.cache/common.zip /opt/sfx/spark/jobs/py/security_alert_anomaly.py
