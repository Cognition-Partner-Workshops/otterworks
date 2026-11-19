#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/../template/submit.sh" users_risk_score
