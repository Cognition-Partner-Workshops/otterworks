#!/usr/bin/env bash
# stdio launcher for the read-only PostgreSQL MCP server (crystaldba/postgres-mcp, --access-mode=restricted,
# collection_reader role: SELECT on synthetic collection tables, default_transaction_read_only=on).
# stdout is reserved for MCP JSON-RPC; all other output goes to stderr.
set -euo pipefail
. "$(dirname "$0")/../scripts/lib.sh"
[[ -f "$ENV_FILE" ]] || "$COLLECTION_DIR/scripts/new-env.sh" >&2
load_env
compose up -d --wait postgres >&2
exec docker compose --project-directory "$COLLECTION_DIR" -f "$COLLECTION_DIR/compose.yaml" \
  --env-file "$ENV_FILE" -p "$COMPOSE_PROJECT_NAME" --progress quiet run --rm -T --no-deps mcp-postgres
