#!/usr/bin/env bash
# Builds auth-service from its own Dockerfile and runs it against a throwaway
# postgres:15-alpine (same image/credentials as docker-compose.infra.yml).
# Usage: characterization/start-local.sh [image-tag]   (stop with: stop-local.sh)
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="${1:-auth-service:characterization}"
NET=auth-char-net
PORT="${AUTH_PORT:-8081}"

docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET" >/dev/null
docker rm -f auth-char-svc auth-char-pg >/dev/null 2>&1 || true

docker run -d --name auth-char-pg --network "$NET" \
  -e POSTGRES_USER=otterworks -e POSTGRES_PASSWORD=otterworks_dev -e POSTGRES_DB=otterworks \
  postgres:15-alpine >/dev/null
until docker exec auth-char-pg pg_isready -U otterworks >/dev/null 2>&1; do sleep 1; done

# USE_MAVEN_MIRROR=1 builds from the module's own Dockerfile with only the
# mirror init script added to the builder stage (see maven-mirror.init.gradle).
if [ "${USE_MAVEN_MIRROR:-0}" = "1" ]; then
  DF="$(mktemp)"
  awk 'NR==1{print; print "COPY characterization/maven-mirror.init.gradle /home/gradle/.gradle/init.d/mirror.gradle"; next}1' Dockerfile > "$DF"
  docker build -q -f "$DF" -t "$TAG" . >/dev/null
  rm -f "$DF"
else
  docker build -q -t "$TAG" . >/dev/null
fi

docker run -d --name auth-char-svc --network "$NET" -p "$PORT":8081 \
  -e SPRING_DATASOURCE_URL=jdbc:postgresql://auth-char-pg:5432/otterworks \
  -e SPRING_DATASOURCE_USERNAME=otterworks -e SPRING_DATASOURCE_PASSWORD=otterworks_dev \
  -e JWT_SECRET=otterworks-local-dev-jwt-secret-change-me-in-production \
  "$TAG" >/dev/null

for _ in $(seq 1 120); do
  if curl -fs "http://localhost:$PORT/health" >/dev/null; then
    docker exec auth-char-svc java -version 2>&1 | head -1
    echo "auth-service up on http://localhost:$PORT ($TAG)"
    exit 0
  fi
  sleep 2
done
docker logs auth-char-svc | tail -50
exit 1
