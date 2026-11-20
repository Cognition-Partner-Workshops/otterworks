#!/usr/bin/env bash
set -euo pipefail
exec "$(dirname "$0")/../template/submit.sh" doc_version_diff_stats
