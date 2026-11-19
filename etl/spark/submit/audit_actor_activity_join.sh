#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
exec "$root/template/submit.sh" audit_actor_activity_join
