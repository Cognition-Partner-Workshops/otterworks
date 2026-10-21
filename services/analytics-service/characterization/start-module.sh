#!/usr/bin/env bash
# Builds analytics-service from its own Dockerfile and starts it next to a fresh
# PostgreSQL 15 (the same backing store docker-compose wires), on a private
# docker network. The service is published on localhost:${HOST_PORT:-18088}.
#
#   characterization/start-module.sh <image-tag>     # build + start
#   characterization/start-module.sh --down           # stop + remove
#
# MAVEN_MIRROR (optional): a Maven Central mirror URL. When set, the module's
# Dockerfile is copied to a temp file with an sbt repositories override injected
# into the builder stage (useful when repo1.maven.org rate-limits with HTTP 429).
# The module's Dockerfile itself is used unmodified otherwise.
set -euo pipefail

MODULE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NET="${CHAR_NETWORK:-analytics-char}"
PG="${NET}-pg"
APP="${NET}-app"
HOST_PORT="${HOST_PORT:-18088}"

down() {
  docker rm -f "$APP" "$PG" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}

if [[ "${1:-}" == "--down" ]]; then down; exit 0; fi
TAG="${1:?usage: start-module.sh <image-tag> | --down}"

DOCKERFILE="$MODULE_DIR/Dockerfile"
if [[ -n "${MAVEN_MIRROR:-}" ]]; then
  DOCKERFILE="$(mktemp)"
  trap 'rm -f "$DOCKERFILE"' EXIT
  awk -v mirror="$MAVEN_MIRROR" '
    { print }
    !done && /^WORKDIR \/app/ {
      print "RUN mkdir -p /root/.sbt && printf \"[repositories]\\n  local\\n  mirror: " mirror "\\n  sbt-plugin-releases: https://repo.scala-sbt.org/scalasbt/sbt-plugin-releases/, [organization]/[module]/(scala_[scalaVersion]/)(sbt_[sbtVersion]/)[revision]/[type]s/[artifact](-[classifier]).[ext]\\n\" > /root/.sbt/repositories"
      print "ENV SBT_OPTS=\"-Dsbt.override.build.repos=true\""
      done = 1
    }' "$MODULE_DIR/Dockerfile" > "$DOCKERFILE"
fi

docker build -t "$TAG" -f "$DOCKERFILE" "$MODULE_DIR"

down
docker network create "$NET" >/dev/null
docker run -d --name "$PG" --network "$NET" \
  -e POSTGRES_USER=otterworks -e POSTGRES_PASSWORD=otterworks_dev -e POSTGRES_DB=otterworks \
  postgres:15-alpine >/dev/null
until docker exec "$PG" pg_isready -U otterworks >/dev/null 2>&1; do sleep 1; done
sleep 2

# Same environment as the docker-compose.yml analytics-service entry, minus
# localstack/redis/otel (SQS start-up failure is non-fatal by design).
docker run -d --name "$APP" --network "$NET" -p "127.0.0.1:${HOST_PORT}:8088" \
  -e AWS_REGION=us-east-1 -e AWS_ACCESS_KEY_ID=test -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_ENDPOINT_URL=http://localstack.invalid:4566 \
  -e POSTGRES_HOST="$PG" -e POSTGRES_PORT=5432 -e POSTGRES_USER=otterworks \
  -e POSTGRES_PASSWORD=otterworks_dev -e POSTGRES_DB=otterworks \
  -e S3_DATA_LAKE_BUCKET=otterworks-data-lake \
  "$TAG" >/dev/null

for _ in $(seq 1 120); do
  if curl -fs "http://localhost:${HOST_PORT}/health" >/dev/null; then
    echo "analytics-service ($TAG) healthy on http://localhost:${HOST_PORT}"
    docker exec "$APP" java -version 2>&1 | sed 's/^/  runtime: /'
    exit 0
  fi
  sleep 2
done
echo "analytics-service did not become healthy" >&2
docker logs "$APP" | tail -50 >&2
exit 1
