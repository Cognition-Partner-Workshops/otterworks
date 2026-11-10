#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
docker compose -f docker-compose.spark.yml -p "sfx-d1110-spark-${NS:-sfx-d1110-before}" exec -T spark-master bash -c '
set -euo pipefail
cd /opt/sfx/spark
mkdir -p .cache/classes
find .cache/classes -type f -delete
java -cp ".cache/jars/scala-compiler-2.12.18.jar:/opt/spark/jars/*" scala.tools.nsc.Main -classpath "/opt/spark/jars/*" -d .cache/classes $(find scala/src/main/scala -name "*.scala")
jar cf .cache/sfx-spark-jobs.jar -C .cache/classes .
'
