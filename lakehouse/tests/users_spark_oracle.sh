#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

: "${NS:?Set NS to the lakehouse parity namespace}"
: "${TD_JDBC_URL:?Point TD_JDBC_URL at a disposable PostgreSQL users oracle}"
: "${TD_JDBC_USER:?Set the oracle database user}"
: "${TD_JDBC_PASSWORD=}"
export TD_JDBC_PASSWORD
[[ "$NS" =~ ^[a-z0-9][a-z0-9-]*$ ]]
export LANDING_DIR="$(realpath "${1:?Pass the shared Spark landing root}")"
export LAKE_DIR="$PWD/lakehouse/.data/$NS/oracle/spark"
export PYSPARK_PYTHON="$PWD/lakehouse/.venv/bin/python"
export SPARK_LOCAL_IP=127.0.0.1 TZ=UTC
export PYTHONPATH="$PWD/etl/spark/jobs/py"

spark="$("$PYSPARK_PYTHON" -c 'import pathlib,pyspark; print(pathlib.Path(pyspark.__file__).parent)')"
mkdir -p "$LAKE_DIR"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/classes"
jdbc="$tmp/postgresql-42.7.5.jar"
curl --fail --silent --show-error --retry 2 -o "$jdbc" \
  https://maven-central.storage-download.googleapis.com/maven2/org/postgresql/postgresql/42.7.5/postgresql-42.7.5.jar

# Only substitute the two hard-coded container mounts; the Scala jobs are compiled unchanged.
scala=etl/spark/scala/src/main/scala/sfx
sed 's@/opt/landing@${sys.env("LANDING_DIR")}@; s@/opt/lake@${sys.env("LAKE_DIR")}@' \
  "$scala/BatchSupport.scala" > "$tmp/BatchSupport.scala"
java -cp "$spark/jars/*" scala.tools.nsc.Main -classpath "$spark/jars/*" -d "$tmp/classes" \
  "$tmp/BatchSupport.scala" "$scala/UsersRiskScore.scala" "$scala/TeamGraphComponents.scala"
jar cf "$tmp/users-jobs.jar" -C "$tmp/classes" .

submit=("$spark/bin/spark-submit" --master 'local[2]' --conf spark.sql.shuffle.partitions=2
  --conf spark.sql.session.timeZone=UTC --conf spark.ui.enabled=false --jars "$jdbc")
for job in users_active_daily users_team_rollup users_login_useragent_parse user_pref_json_flatten; do
  "${submit[@]}" "etl/spark/jobs/py/$job.py"
done
for klass in UsersRiskScore TeamGraphComponents; do
  "${submit[@]}" --class "sfx.$klass" "$tmp/users-jobs.jar"
done
