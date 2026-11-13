#!/usr/bin/env bash
# Runs reset.sh against a throwaway bare remote with a stubbed gh, twice, and checks the
# second run is a no-op. No network and no GitHub calls.
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
git push -q origin HEAD:refs/heads/demo-vuln-shared-lib HEAD:refs/heads/devin/1-fix HEAD:refs/heads/devin/2-other
cat > "$work/gh" <<'STUB'
#!/usr/bin/env bash
echo "$*" >> "$GH_LOG"
case "$1 $2" in
  "pr list") if [[ "$*" == *"--state open"* ]]; then echo 41; else printf 'devin/1-fix\nfeature/x\n'; fi ;;
  "pr close") ;;
  "api /orgs/"*) printf '11 1.0.0\n12 1.1.0\n13 0.9.0\n' ;;
  "api -X") ;;
esac
STUB
chmod +x "$work/gh"
export GH="$work/gh" GH_LOG="$work/gh.log"
"$here/reset.sh"
seeded="$(git rev-parse seeded-v1)"
[ "$(git ls-remote origin refs/heads/demo-vuln-shared-lib | cut -f1)" = "$seeded" ]
! git ls-remote --exit-code origin refs/heads/devin/1-fix >/dev/null
git ls-remote --exit-code origin refs/heads/devin/2-other >/dev/null
grep -q "pr close -R Cognition-Partner-Workshops/otterworks 41" "$GH_LOG"
grep -q "api -X DELETE /orgs/Cognition-Partner-Workshops/packages/nuget/Platform.Shared/versions/12" "$GH_LOG"
! grep -q "versions/1[13]" <(grep DELETE "$GH_LOG")
second="$("$here/reset.sh")"
grep -q "already at seeded-v1" <<<"$second"
[ "$(git ls-remote origin refs/heads/demo-vuln-shared-lib | cut -f1)" = "$seeded" ]
echo "reset_test: ok"
