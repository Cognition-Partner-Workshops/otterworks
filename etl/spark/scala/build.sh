#!/usr/bin/env bash
eval "$(python3 "$(git rev-parse --show-toplevel)/warehouse/run_config.py" env)"
set -euo pipefail
cd "$(dirname "$0")/../../.."
docker compose -f docker-compose.spark.yml -p "${RUN_TOKEN}-spark-${NS:-${RUN_BEFORE_NAMESPACE}}" exec -T spark-master bash -c '
set -euo pipefail
cd /opt/sfx/spark
mkdir -p .cache/classes
find .cache/classes -type f -delete
java -cp ".cache/jars/scala-compiler-2.12.18.jar:/opt/spark/jars/*" scala.tools.nsc.Main -classpath "/opt/spark/jars/*" -d .cache/classes $(find scala/src/main/scala -name "*.scala")
jar cf .cache/sfx-spark-jobs.jar -C .cache/classes .
'
