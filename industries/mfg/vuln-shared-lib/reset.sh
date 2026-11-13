#!/usr/bin/env bash
# Reset the vuln-shared-lib estate to tag seeded-v1. Touches only this collection:
#   1. closes open PRs whose base is demo-vuln-shared-lib
#   2. deletes devin/* branches that were opened as PRs into demo-vuln-shared-lib
#   3. moves demo-vuln-shared-lib back to seeded-v1
#   4. removes Platform.Shared package versions above 1.0.0 from GitHub Packages
#      (GitHub Packages has no NuGet unlist, so a version is removed by deleting it)
#
# Usage: reset.sh [--dry-run]   (needs gh authenticated with repo and delete:packages)
# Repeatable: every step reads current state and does nothing when it is already reset.
set -euo pipefail

REPO="${VSL_REPO:-Cognition-Partner-Workshops/otterworks}"
OWNER="${REPO%%/*}"
BRANCH="demo-vuln-shared-lib"
TAG="seeded-v1"
PACKAGE="Platform.Shared"
BASELINE_VERSION="1.0.0"
REMOTE="${VSL_REMOTE:-origin}"
GH="${GH:-gh}"
DRY_RUN=false
[ "${1:-}" = "--dry-run" ] && DRY_RUN=true

log() { printf '[vsl-reset] %s\n' "$*"; }
act() { if $DRY_RUN; then log "would run: $*"; else "$@"; fi; }

# NuGet precedence against the (release) baseline: build metadata is ignored, versions are
# compared on four numeric parts, and a prerelease ranks below its own release. So only a
# release part strictly above the baseline counts: 1.0.0-rc.1, 1.0.0.0 and 1.0.0+b are kept,
# 1.1.0-rc.1 is deleted.
above_baseline() {
  local v="${1%%+*}" release i
  release="${v%%-*}"
  local -a have want
  IFS=. read -ra have <<<"$release"
  IFS=. read -ra want <<<"$BASELINE_VERSION"
  for i in 0 1 2 3; do
    local h="${have[i]:-0}" w="${want[i]:-0}"
    [[ "$h" =~ ^[0-9]+$ ]] || { log "refusing: unparseable $PACKAGE version '$1'"; exit 1; }
    if ((10#$h > 10#$w)); then return 0; fi
    if ((10#$h < 10#$w)); then return 1; fi
  done
  return 1
}

git fetch --quiet "$REMOTE" "refs/tags/$TAG:refs/tags/$TAG" "+refs/heads/$BRANCH:refs/remotes/$REMOTE/$BRANCH"
target="$(git rev-parse "$TAG^{commit}")"
# Moving a demo-* branch fires the tenant CD workflow unless the head commit skips CI.
git log -1 --format=%B "$target" | grep -q '\[skip ci\]' \
  || { log "refusing: $TAG ($target) does not carry [skip ci], so the reset push would deploy"; exit 1; }

# Every listing runs before any destructive step, in a checked assignment, so a failed or
# partial query aborts the reset instead of acting on an incomplete view of the estate.
open_prs="$($GH api --paginate "repos/$REPO/pulls?base=$BRANCH&state=open&per_page=100" --jq '.[].number')"
pr_heads="$($GH api --paginate "repos/$REPO/pulls?base=$BRANCH&state=all&per_page=100" --jq '.[].head.ref' | sort -u)"
existing="$(git ls-remote --heads "$REMOTE" 'devin/*' | awk '{sub("refs/heads/","",$2); print $2}')"
if ! versions="$($GH api "/orgs/$OWNER/packages/nuget/$PACKAGE/versions" --paginate \
                   --jq '.[] | "\(.id) \(.name)"' 2>&1)"; then
  log "cannot list $PACKAGE versions (token needs read:packages and delete:packages): $versions"
  exit 1
fi
stale_versions=""
while read -r id name; do
  [ -n "${id:-}" ] || continue
  if above_baseline "$name"; then stale_versions+="$id "; fi
done <<<"$versions"

log "1/4 open PRs into $BRANCH"
for number in $open_prs; do
  act "$GH" pr close -R "$REPO" "$number" --comment "Estate reset to $TAG."
done

log "2/4 devin/* branches opened against $BRANCH"
for head in $pr_heads; do
  case "$head" in devin/*) ;; *) continue ;; esac
  grep -qxF "$head" <<<"$existing" || continue
  act git push --quiet "$REMOTE" --delete "$head"
done

log "3/4 $BRANCH -> $TAG ($target)"
if [ "$(git rev-parse "refs/remotes/$REMOTE/$BRANCH")" = "$target" ]; then
  log "already at $TAG"
else
  act git push --quiet --force "$REMOTE" "$target:refs/heads/$BRANCH"
fi

log "4/4 $PACKAGE versions above $BASELINE_VERSION"
for id in $stale_versions; do
  act "$GH" api -X DELETE "/orgs/$OWNER/packages/nuget/$PACKAGE/versions/$id"
done

log "done$($DRY_RUN && echo ' (dry run)')"
