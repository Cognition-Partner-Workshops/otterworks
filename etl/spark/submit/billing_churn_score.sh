#!/usr/bin/env bash
set -euo pipefail
exec "$(dirname "$0")/../template/submit.sh" billing_churn_score
