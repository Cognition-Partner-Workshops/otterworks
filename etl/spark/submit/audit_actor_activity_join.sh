#!/usr/bin/env bash
set -e
export TD_JDBC_PASSWORD="${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 640m --executor-cores 2 --total-executor-cores 4 --conf spark.sql.shuffle.partitions=4 --conf spark.sql.autoBroadcastJoinThreshold=-1 --conf spark.sql.adaptive.enabled=false --conf spark.task.maxFailures=8 --conf spark.memory.fraction=0.094 --conf spark.shuffle.spill.numElementsForceSpillThreshold=4096 \
  --py-files /opt/sfx/spark/.cache/common.zip /opt/sfx/spark/jobs/py/audit_actor_activity_join.py
