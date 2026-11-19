#!/usr/bin/env bash
set -euo pipefail
exec "$(dirname "$0")/../template/submit.sh" security_alert_anomaly
