#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
OUT="${1:-compliance/evidence/out}"
mkdir -p "$OUT" "$HOME/bin"
OUT="$(cd "$OUT" && pwd)"
export PATH="$HOME/bin:$PATH"
if ! command -v trivy >/dev/null || ! trivy --version | head -1 | grep -q '0.71.0$'; then
  curl -fsSL https://github.com/aquasecurity/trivy/releases/download/v0.71.0/trivy_0.71.0_Linux-64bit.tar.gz -o "$OUT/trivy.tar.gz"
  tar -xzf "$OUT/trivy.tar.gz" -C "$HOME/bin" trivy
fi
if ! command -v gitleaks >/dev/null || [[ "$(gitleaks version)" != 8.21.2 ]]; then
  curl -fsSL https://github.com/gitleaks/gitleaks/releases/download/v8.21.2/gitleaks_8.21.2_linux_x64.tar.gz -o "$OUT/gitleaks.tar.gz"
  tar -xzf "$OUT/gitleaks.tar.gz" -C "$HOME/bin" gitleaks
fi
: > "$OUT/empty.ignore"
: > "$OUT/status.tsv"
scan() {
  local name="$1"; shift
  rm -f "$OUT/$name.json"
  local rc=0
  "$@" > "$OUT/$name.log" 2>&1 || rc=$?
  printf '%s\t%s\n' "$name" "$rc" >> "$OUT/status.tsv"
  echo "$name: exit $rc (see $OUT/$name.log)"
}
scan fs-with-ignore trivy fs . --offline-scan --severity CRITICAL,HIGH --skip-dirs services/report-service --ignorefile .trivyignore --format json --output "$OUT/fs-with-ignore.json"
scan fs-no-ignore trivy fs . --offline-scan --severity CRITICAL,HIGH --skip-dirs services/report-service --ignorefile "$OUT/empty.ignore" --format json --output "$OUT/fs-no-ignore.json"
scan report-service trivy fs services/report-service --offline-scan --severity CRITICAL,HIGH --ignorefile "$OUT/empty.ignore" --format json --output "$OUT/report-service.json"
python3 "$ROOT/compliance/evidence/build_evidence_pack.py" --runtime-images > "$OUT/runtime-images.json"
while IFS=$'\t' read -r name image; do
  [[ "$image" == scratch ]] && continue
  scan "image-$name" trivy image --severity CRITICAL,HIGH --ignorefile "$OUT/empty.ignore" --format json --output "$OUT/image-$name.json" "$image"
done < <(python3 - "$OUT/runtime-images.json" <<'PY'
import json, sys
seen = set()
for row in json.load(open(sys.argv[1])):
    if row['resolved'] and row['image'] not in seen:
        seen.add(row['image'])
        print(row['key'] + '\t' + row['image'])
PY
)
scan gitleaks-with-ignore gitleaks detect --source . --redact --report-format json --report-path "$OUT/gitleaks-with-ignore.json"
scan gitleaks-no-ignore gitleaks detect --source . --redact --gitleaks-ignore-path /dev/null --report-format json --report-path "$OUT/gitleaks-no-ignore.json"
python3 - "$OUT" "$ROOT" <<'PY'
import datetime, json, pathlib, subprocess, sys
out = pathlib.Path(sys.argv[1])
meta = {'scanned_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'trivy': subprocess.check_output(['trivy', '--version'], text=True).strip(),
        'gitleaks': subprocess.check_output(['gitleaks', 'version'], text=True).strip(),
        'offline_dependency_resolution': True}
(out / 'scan-metadata.json').write_text(json.dumps(meta, indent=2) + '\n')
PY
