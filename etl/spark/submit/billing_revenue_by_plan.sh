#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
exec "$root/template/submit.sh" billing_revenue_by_plan
