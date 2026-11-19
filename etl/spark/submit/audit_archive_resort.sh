#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/../template/submit.sh" audit_archive_resort
