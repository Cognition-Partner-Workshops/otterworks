#!/usr/bin/env bash
# Create the per-run working branch for a migration rehearsal.
#
#   scripts/tp-run-branch.sh mongodb            # cut tp-run/mongodb-<UTC timestamp> from origin/main and push it
#   DRY_RUN=1 scripts/tp-run-branch.sh mongodb  # stamp a detached worktree, print the diff, push nothing
#   TP_RUN_BASE=<rev> overrides the base revision for a dry run (default origin/main)
#
# The mongodb track names its migration database after the run token (ow_tp_billing_<token>).
# The committed harness carries the reference run's token in mapping_spec.json, units.json and
# the Mongo backend, so the first commit on a fresh branch restamps that token. The stamp is the
# only edit made to the gate files outside a plan decision, and it changes nothing but the name.
# Every unit PR of the run targets the branch printed on success.
set -euo pipefail

track="${1:-}"
case "$track" in
  mongodb) ;;
  *) echo "usage: $0 mongodb" >&2; exit 2 ;;
esac

REF_TOKEN="20261001T233613Z"
token="$(date -u +%Y%m%dT%H%M%SZ)"
branch="tp-run/${track}-${token}"
base="${TP_RUN_BASE:-origin/main}"
if [ "$base" != origin/main ] && [ "${DRY_RUN:-}" != 1 ]; then
  echo "TP_RUN_BASE is only honoured with DRY_RUN=1; run branches are cut from origin/main" >&2
  exit 2
fi
git fetch -q origin main
wt="$(mktemp -d)"
trap 'git worktree remove --force "$wt" >/dev/null 2>&1 || true' EXIT
git worktree add -q --detach "$wt" "$base"
files=$(git -C "$wt" grep -l "$REF_TOKEN" -- migration/billing services/legacy-billing \
  ':!migration/billing/*.md' ':!migration/billing/**/*.md' || true)
for f in $files; do sed -i "s/$REF_TOKEN/$token/g" "$wt/$f"; done
git -C "$wt" add -A
if [ "${DRY_RUN:-}" = 1 ]; then
  git -C "$wt" diff --cached --stat
  echo "dry run: would create $branch (database ow_tp_billing_$token); nothing created or pushed"
  exit 0
fi
git -C "$wt" commit -q -m "run: stamp migration database ow_tp_billing_${token} for ${branch}"
git -C "$wt" push -q origin "HEAD:refs/heads/$branch"
echo "$branch"
