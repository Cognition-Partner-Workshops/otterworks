#!/usr/bin/env bash
# Characterization harness for report-service. Black-box only: it talks HTTP to the running
# containers and inspects the files they serve, so it runs unchanged before and after the upgrade.
#
#   ./run.sh up       build the image from ../Dockerfile and start postgres, db2, stub, 3 instances
#   ./run.sh test     run the suite against the baseline in baseline/snapshots (extra args go to pytest)
#   ./run.sh record   re-record baseline/snapshots (only on the reference code)
#   ./run.sh down     stop and remove everything, volumes included
#
#   ./run.sh image    build report-service:characterization without reaching Maven Central from
#                     inside docker build (for rate-limited networks): the jar is built in the same
#                     builder image as ../Dockerfile (maven:3.8.7-eclipse-temurin-8, mvn package
#                     -DskipTests -B, host ~/.m2 so settings.xml mirrors apply) and handed to the
#                     unmodified runtime stage of ../Dockerfile as its `builder` stage.
#
# REPORT_IMAGE=<tag> ./run.sh up uses a prebuilt image instead of building one.
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE=(docker compose -f docker-compose.yml)

wait_db2() {
  local deadline=$((SECONDS + ${DB2_WAIT_SECONDS:-900}))
  until "${COMPOSE[@]}" logs db2 2>/dev/null | grep -q "Setup has completed"; do
    (( SECONDS < deadline )) || { echo "db2 did not finish setup in time" >&2; exit 1; }
    sleep 10
  done
  "${COMPOSE[@]}" exec -T -u db2inst1 db2 bash /fixtures/load.sh
}

case "${1:-}" in
  image)
    ctx="$(mktemp -d)"
    trap 'rm -rf "$ctx"' EXIT
    docker run --rm -u "$(id -u):$(id -g)" -e MAVEN_CONFIG=/m2 -v "$HOME/.m2:/m2" \
      -v "$PWD/..:/app" -w /app maven:3.8.7-eclipse-temurin-8 \
      mvn -B -q -Duser.home=/tmp -Dmaven.repo.local=/m2/repository -s /m2/settings.xml package -DskipTests
    mkdir -p "$ctx/app/target"
    cp ../target/report-service.jar "$ctx/app/target/"
    docker buildx build --load --build-context builder="$ctx" -t report-service:characterization ..
    ;;
  up)
    if [[ -n "${REPORT_IMAGE:-}" ]]; then
      "${COMPOSE[@]}" up -d --no-build
    else
      "${COMPOSE[@]}" up -d --build
    fi
    wait_db2
    "${COMPOSE[@]}" up -d --wait --no-build report-off report-db2 report-pg
    ;;
  test)
    shift
    uv run pytest "$@"
    ;;
  record)
    shift
    CHAR_RECORD=1 uv run pytest "$@"
    ;;
  down)
    "${COMPOSE[@]}" down -v --remove-orphans
    ;;
  *)
    sed -n '2,12p' "$0"
    exit 2
    ;;
esac
