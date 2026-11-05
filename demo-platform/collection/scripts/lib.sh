# Shared helpers for collection scripts. Sourced, not executed.
COLLECTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${COLLECTION_ENV_FILE:-$COLLECTION_DIR/.env}"
PROJECT_RE='^collection-[a-z0-9][a-z0-9-]{2,40}$'

die() { echo "error: $*" >&2; exit 1; }

load_env() {
  [[ -f "$ENV_FILE" ]] || die "missing $ENV_FILE (run: make env)"
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
  [[ "${COMPOSE_PROJECT_NAME:-}" =~ $PROJECT_RE ]] || die "COMPOSE_PROJECT_NAME must match $PROJECT_RE"
}

compose() {
  docker compose --project-directory "$COLLECTION_DIR" -f "$COLLECTION_DIR/compose.yaml" \
    --env-file "$ENV_FILE" -p "$COMPOSE_PROJECT_NAME" "$@"
}
