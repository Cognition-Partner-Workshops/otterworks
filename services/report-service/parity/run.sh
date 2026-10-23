#!/usr/bin/env bash
# Black-box replay harness for the report-service Java 8 baseline.
#
#   ./run.sh up       build and start postgres, the deterministic stub, and report-service
#   ./run.sh down     stop and remove the stack, including database volumes
#   ./run.sh image    build the image without downloading dependencies inside docker build
#   ./run.sh record   record java-reference.json from the running baseline
#   ./run.sh replay   replay the corpus against the running service
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE=(docker compose -p "${COMPOSE_PROJECT_NAME:-report-parity}" -f docker-compose.yml)
IMAGE_TAG="${IMAGE_TAG:-report-service:parity}"
BASE_URL="${BASE_URL:-http://localhost:${PARITY_PORT:-18091}}"

case "${1:-}" in
  image)
    ctx="$(mktemp -d)"
    trap 'rm -rf "$ctx"' EXIT
    mkdir -p "$HOME/.m2/repository"
    maven_args=(mvn -B -q -Duser.home=/tmp -Dmaven.repo.local=/m2/repository)
    if [[ -f "$HOME/.m2/settings.xml" ]]; then
      maven_args+=(-s /m2/settings.xml)
    fi
    docker run --rm -u "$(id -u):$(id -g)" -e MAVEN_CONFIG=/m2 -v "$HOME/.m2:/m2" \
      -v "$PWD/..:/app" -w /app maven:3.8.7-eclipse-temurin-8 \
      "${maven_args[@]}" package -DskipTests
    mkdir -p "$ctx/app/target"
    cp ../target/report-service.jar "$ctx/app/target/"
    docker buildx build --load --build-context builder="$ctx" -t "$IMAGE_TAG" ..
    ;;
  up)
    if [[ -n "${REPORT_IMAGE:-}" ]]; then
      "${COMPOSE[@]}" up -d --wait --no-build
    else
      REPORT_IMAGE="$IMAGE_TAG" "${COMPOSE[@]}" up -d --wait --build
    fi
    ;;
  down)
    "${COMPOSE[@]}" down -v --remove-orphans
    ;;
  record|replay)
    action="$1"
    shift
    if [[ "$action" == "record" ]]; then
      python3 replay.py --base "$BASE_URL" --record "$@"
    else
      python3 replay.py --base "$BASE_URL" "$@"
    fi
    ;;
  *)
    sed -n '2,9p' "$0"
    exit 2
    ;;
esac
