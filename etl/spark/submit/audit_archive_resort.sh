#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 512m --executor-cores 1 --total-executor-cores 2 --conf spark.python.worker.memory=8m --conf spark.memory.fraction=0.1 --conf spark.default.parallelism=2 --conf spark.shuffle.spill.numElementsForceSpillThreshold=4096 \
  --py-files /opt/sfx/spark/.cache/common.zip /opt/sfx/spark/jobs/py/audit_archive_resort.py
