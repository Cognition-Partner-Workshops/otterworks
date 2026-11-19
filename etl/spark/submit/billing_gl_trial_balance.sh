#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
exec "$root/template/submit.sh" billing_gl_trial_balance
