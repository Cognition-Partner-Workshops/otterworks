#!/usr/bin/env bash
set -euo pipefail
exec "$(dirname "$0")/../template/submit.sh" team_graph_components
