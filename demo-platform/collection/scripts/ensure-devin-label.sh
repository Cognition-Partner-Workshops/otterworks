#!/usr/bin/env bash
# Ensure the GitHub Issues label `devin` exists. Uses the caller's existing gh auth; never changes
# permissions, never creates issues. DRY_RUN=1 (default) only reports.
set -euo pipefail
REPO="${GITHUB_REPOSITORY:-Cognition-Partner-Workshops/otterworks}"
DRY_RUN="${DRY_RUN:-1}"
spec="$(dirname "$0")/../github/labels.json"
name=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))[0]["name"])' "$spec")
color=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))[0]["color"])' "$spec")
desc=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))[0]["description"])' "$spec")
if gh label list -R "$REPO" --search "$name" --limit 100 --json name --jq '.[].name' | grep -qx "$name"; then
  echo "label '$name' exists in $REPO"
elif [[ "$DRY_RUN" == "1" ]]; then
  echo "label '$name' missing in $REPO (DRY_RUN=1; rerun with DRY_RUN=0 to create it)"
else
  gh label create "$name" -R "$REPO" --color "$color" --description "$desc"
fi
