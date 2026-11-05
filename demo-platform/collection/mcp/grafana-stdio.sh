#!/usr/bin/env bash
# stdio launcher for the official Grafana MCP server (grafana/mcp-grafana, read-only: --disable-write,
# Viewer service-account token). Talks to THIS machine's run-scoped Compose stack over the Compose network.
# The Viewer token lives 24h; mcp-grafana re-reads the token file per request, so rerunning this launcher
# or `make up` refreshes it. stdout is reserved for MCP JSON-RPC; all other output goes to stderr.
set -euo pipefail
. "$(dirname "$0")/../scripts/lib.sh"
[[ -f "$ENV_FILE" ]] || "$COLLECTION_DIR/scripts/new-env.sh" >&2
load_env
compose up -d --wait postgres grafana >&2
compose run --rm -T --no-deps grafana-init </dev/null >&2  # exits nonzero (and so does this script) if init fails
exec docker compose --project-directory "$COLLECTION_DIR" -f "$COLLECTION_DIR/compose.yaml" \
  --env-file "$ENV_FILE" -p "$COMPOSE_PROJECT_NAME" --progress quiet run --rm -T --no-deps mcp-grafana
