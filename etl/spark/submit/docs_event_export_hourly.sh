#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
exec "$root/template/submit.sh" docs_event_export_hourly
