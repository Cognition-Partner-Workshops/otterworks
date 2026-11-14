#!/usr/bin/env bash
# Build notification-service from its own Dockerfile and run it against the
# repo's LocalStack + Redis (docker-compose.infra.yml), with the same env as the
# notification-service entry in docker-compose.yml.
#
#   ./start-local.sh            # build + run on :8086 (container ow-notification-char)
#   ./start-local.sh stop
#
# GRADLE_BUILDER_IMAGE=<image> swaps the Dockerfile's builder stage for a
# compatible image (e.g. one carrying a Maven Central mirror init script) via a
# BuildKit named context; the Dockerfile itself is used unchanged.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
module="$(dirname "$here")"
repo="$(cd "$module/../.." && pwd)"
name="${CONTAINER_NAME:-ow-notification-char}"
image="${IMAGE:-ow-notification:char}"
port="${PORT:-8086}"

if [[ "${1:-}" == "stop" ]]; then
  docker rm -f "$name" >/dev/null 2>&1 || true
  exit 0
fi

docker compose -f "$repo/docker-compose.infra.yml" up -d --wait redis localstack

builder="$(sed -n 's/^FROM \([^ ]*\) AS builder.*/\1/p' "$module/Dockerfile")"
ctx=()
if [[ -n "${GRADLE_BUILDER_IMAGE:-}" ]]; then
  ctx=(--build-context "$builder=docker-image://$GRADLE_BUILDER_IMAGE")
fi
docker build "${ctx[@]}" -t "$image" "$module"

docker rm -f "$name" >/dev/null 2>&1 || true
docker run -d --name "$name" --network otterworks-network -p "$port:8086" \
  -e AWS_REGION=us-east-1 -e AWS_ACCESS_KEY_ID=test -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_ENDPOINT_URL=http://localstack:4566 \
  -e REDIS_HOST=redis -e REDIS_PORT=6379 \
  -e SQS_QUEUE_URL=http://localstack:4566/000000000000/otterworks-notifications \
  -e SNS_TOPIC_ARN=arn:aws:sns:us-east-1:000000000000:otterworks-events \
  -e DYNAMODB_TABLE_NOTIFICATIONS=otterworks-notifications \
  -e DYNAMODB_TABLE_PREFERENCES=otterworks-notification-preferences \
  -e OTEL_SERVICE_NAME=notification-service \
  "$image" >/dev/null

for _ in $(seq 1 60); do
  [[ "$(docker inspect -f '{{.State.Health.Status}}' "$name")" == healthy ]] && break
  sleep 2
done
status="$(docker inspect -f '{{.State.Health.Status}}' "$name")"
echo "$status"
if [[ "$status" != healthy ]]; then
  docker logs --tail 50 "$name" >&2 || true
  exit 1
fi
docker exec "$name" java -version 2>&1 | head -1
