#!/usr/bin/env bash
# Runs reset.sh against a throwaway bare remote with a stubbed gh: a full reset, a no-op
# second run, NuGet version precedence, and enumeration failures that must stop the reset
# before any destructive step. No network and no GitHub calls.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
git init -q --bare "$work/remote.git"
git init -q "$work/clone" && cd "$work/clone"
git config user.email t@example.com && git config user.name t
git remote add origin "$work/remote.git"
git commit -q --allow-empty -m "seed [skip ci]" && git tag seeded-v1
git push -q origin HEAD:refs/heads/demo-vuln-shared-lib seeded-v1
git commit -q --allow-empty -m "later work"
later="$(git rev-parse HEAD)"
git push -q origin HEAD:refs/heads/demo-vuln-shared-lib HEAD:refs/heads/devin/1-fix \
  HEAD:refs/heads/devin/2-other HEAD:refs/heads/devin/600-old
cat > "$work/gh" <<'STUB'
#!/usr/bin/env bash
# Answers the paginated listings as gh api --paginate would after walking every page.
echo "$*" >> "$GH_LOG"
case "$*" in
  *"--paginate repos/"*"state=open"*)
    [ -z "${FAIL_OPEN:-}" ] || { echo "HTTP 502" >&2; exit 1; }
    [[ "$*" == *"--paginate"* ]] && seq 1 31 ;;
  *"--paginate repos/"*"state=all"*)
    [ -z "${FAIL_ALL:-}" ] || { echo "HTTP 502" >&2; exit 1; }
    for i in $(seq 1 600); do echo "feature/$i"; done
    printf 'devin/1-fix\ndevin/600-old\n' ;;
  "api /orgs/"*)
    [ -z "${FAIL_PACKAGES:-}" ] || { echo "HTTP 403" >&2; exit 1; }
    [ -z "${BAD_VERSION:-}" ] || echo "21 not-a-version"
    printf '11 1.0.0\n12 1.1.0\n13 0.9.0\n14 1.0.0-rc.1\n15 1.0.0+build.5\n16 1.0.0.0\n17 1.1.0-rc.1\n18 1.0.1\n19 2.0.0+b\n20 1.0.0.1\n' ;;
  "pr close"*|"api -X"*) ;;
  *) echo "unexpected gh call: $*" >&2; exit 1 ;;
esac
STUB
chmod +x "$work/gh"
export GH="$work/gh" GH_LOG="$work/gh.log"
remote_head() { git ls-remote origin refs/heads/demo-vuln-shared-lib | cut -f1; }
destructive() { grep -E "pr close|api -X DELETE" "$GH_LOG" || true; }

for failure in FAIL_OPEN FAIL_ALL FAIL_PACKAGES BAD_VERSION; do
  : > "$GH_LOG"
  if env "$failure=1" "$here/reset.sh" >/dev/null 2>&1; then echo "reset ignored $failure"; exit 1; fi
  [ -z "$(destructive)" ] || { echo "$failure: destructive gh call ran"; exit 1; }
  [ "$(remote_head)" = "$later" ] || { echo "$failure: branch moved"; exit 1; }
  git ls-remote --exit-code origin refs/heads/devin/1-fix >/dev/null || { echo "$failure: branch deleted"; exit 1; }
done

: > "$GH_LOG"
"$here/reset.sh"
seeded="$(git rev-parse seeded-v1)"
[ "$(remote_head)" = "$seeded" ]
! git ls-remote --exit-code origin refs/heads/devin/1-fix >/dev/null
! git ls-remote --exit-code origin refs/heads/devin/600-old >/dev/null
git ls-remote --exit-code origin refs/heads/devin/2-other >/dev/null
[ "$(grep -c "pr close -R Cognition-Partner-Workshops/otterworks" "$GH_LOG")" = 31 ]
grep -q "pr close -R Cognition-Partner-Workshops/otterworks 31 " "$GH_LOG"
deleted="$(grep -o 'api -X DELETE .*/versions/[0-9]*' "$GH_LOG" | sed 's#.*/##' | sort -n | tr '\n' ' ')"
[ "$deleted" = "12 17 18 19 20 " ] || { echo "deleted versions: $deleted"; exit 1; }

second="$("$here/reset.sh")"
grep -q "already at seeded-v1" <<<"$second"
[ "$(remote_head)" = "$seeded" ]
echo "reset_test: ok"
