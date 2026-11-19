#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
exec bash "$root/template/submit.sh" billing_invoice_summary_daily
