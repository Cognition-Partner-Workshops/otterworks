#!/usr/bin/env bash
set -e
: "${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
export TD_JDBC_PASSWORD
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 --deploy-mode client \
  --executor-memory 1g --executor-cores 1 --num-executors 2 --conf spark.default.parallelism=4 \
  --py-files /opt/sfx/spark/.cache/common.zip /opt/sfx/spark/jobs/py/docs_folder_tree_walk.py
