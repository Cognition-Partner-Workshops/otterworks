#!/usr/bin/env bash
set -euo pipefail

name=kyc-monitoring
subnet=172.30.250.0/24

if ! docker network inspect "$name" >/dev/null 2>&1; then
  docker network create --driver bridge --internal --subnet "$subnet" \
    --opt com.docker.network.bridge.inhibit_ipv4=true "$name" >/dev/null ||
    docker network inspect "$name" >/dev/null
fi

actual=$(docker network inspect --format '{{.Driver}} {{.Internal}} {{index .Options "com.docker.network.bridge.inhibit_ipv4"}} {{range .IPAM.Config}}{{.Subnet}} {{end}}' "$name")
if [[ "$actual" != "bridge true true $subnet " ]]; then
  echo "Network $name must be an internal bridge with inhibit_ipv4=true and subnet $subnet; found: $actual" >&2
  exit 1
fi
