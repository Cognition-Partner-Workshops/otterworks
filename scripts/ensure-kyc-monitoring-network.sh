#!/usr/bin/env bash
set -euo pipefail

name=kyc-monitoring
subnet=172.30.250.0/24
management_address=172.30.250.10
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
project=$(docker compose -f "$repo/docker-compose.infra.yml" config --format json |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["name"])')

if docker network inspect "$name" >/dev/null 2>&1; then
  if docker network inspect "$name" | python3 -c '
import json, sys
network = json.load(sys.stdin)[0]
labels = network.get("Labels") or {}
valid = (network["Internal"]
         and (network.get("Options") or {}).get("com.docker.network.bridge.inhibit_ipv4") == "true"
         and any(config.get("Subnet") == sys.argv[2] for config in network["IPAM"]["Config"])
         and not any(config.get("Subnet") == sys.argv[2] and config.get("Gateway") == sys.argv[4]
                     for config in network["IPAM"]["Config"])
         and labels.get("com.docker.compose.project") == sys.argv[1]
         and labels.get("com.docker.compose.network") == sys.argv[3])
sys.exit(0 if valid else 1)
' "$project" "$subnet" "$name" "$management_address"; then
    exit 0
  fi
  containers=$(docker network inspect --format '{{range .Containers}}{{.Name}} {{end}}' "$name")
  if [[ -n "$containers" ]]; then
    echo "Network $name has incompatible ownership or settings and is in use by: $containers" >&2
    echo "Stop and remove those stacks' containers (docker compose down), then rerun $0. No network was removed." >&2
    exit 1
  fi
  echo "Recreating unused network $name with infra project $project ownership."
  docker network rm "$name" >/dev/null
fi

docker network create --driver bridge --internal --subnet "$subnet" \
  --label "com.docker.compose.project=$project" \
  --label "com.docker.compose.network=$name" \
  --opt com.docker.network.bridge.inhibit_ipv4=true "$name" >/dev/null
