#!/usr/bin/env bash
# Run from any directory: bash industries/banking/vmware-wave-1/rates-batch/parity/run-parity.sh
# Requires the original rates-01/report-01 Compose stand-ins and the seeded
# w1-rates-batch kind deployment. Uses kubectl, Docker, curl and Python 3 stdlib.
# Replaces only parity-* Jobs, parity/out evidence and the w1-report-02 container.
# Leaves w1-report-02 running for inspection; stop it with docker rm -f w1-report-02.
# Both sides must run UTC. Only stdout output-location and missing-ticks input-
# location strings are normalised. HTTP compares status, Content-Type and body
# bytes, not Date or other headers. Error cases invoke the VM jar directly to
# capture stderr separately instead of the wrapper's shared log redirection.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
wave="$(cd "$here/../.." && pwd)"
out="$here/out"
k=(kubectl --context kind-w1-rates-batch)
compose=(docker compose -f "$wave/vm/compose.yaml")
mkdir -p "$out"/{vm,container,seed}
printf 'case\tvm value\tcontainer value\tresult\n' > "$here/results.tsv"
printf 'day\tlocal ticks SHA-256\tS3 ticks SHA-256\n' > "$out/seed/hashes.tsv"
failures=0
record() {
  local result=FAIL
  if [[ "$2" == "$3" && "${4:-yes}" == yes ]]; then result=PASS; else failures=$((failures + 1)); fi
  printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$result" >> "$here/results.tsv"
}
hash() { sha256sum "$1" | cut -d' ' -f1; }
vm_zone="$("${compose[@]}" exec -T rates-01 date +%Z)"
report_zone="$("${compose[@]}" exec -T report-01 date +%Z)"
report_tz="$("${compose[@]}" exec -T report-01 sh -c 'printf %s "${TZ-}"')"
[[ "$vm_zone" == UTC && "$report_zone" == UTC && -z "$report_tz" ]]
"${k[@]}" get cronjob rates-batch -n app-rates-batch -o json > "$out/cronjob.json"
python3 - "$out/cronjob.json" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))
env = {e['name']: e.get('value') for e in c['spec']['jobTemplate']['spec']['template']['spec']['containers'][0]['env']}
assert env['BUSINESS_TZ'] == env['TZ'] == 'Etc/UTC'
PY
"${k[@]}" -n deps port-forward svc/s3 "${PARITY_PORT:-18333}:8333" > "$out/port-forward.log" 2>&1 &
pf=$!
trap 'kill "$pf" 2>/dev/null || true; wait "$pf" 2>/dev/null || true' EXIT
host="127.0.0.1:${PARITY_PORT:-18333}"
for _ in $(seq 1 60); do
  if curl -s "http://$host/" -o /dev/null; then break; fi
  kill -0 "$pf"
  sleep 1
done
get() { python3 "$here/s3-get.py" "$host" "/bank-rates/$1" "$2"; }
days=(2026-10-14 2026-10-15 2026-10-16)
expected=(58c7b41354bdee7810fd80521cc5ebd2b92828a85aa21fec088b2574c093690d e2746bf958143e87a41d126866b583d1d97d7365282d6ca17d190c2579262861 0bcf20da1ebabfc06420cc0688a9eaa23d149d31e2b06f55f01291beabd4bc2b)
for day in "${days[@]}"; do
  get "in/ticks-$day.csv" "$out/seed/ticks-$day.csv"
  a="$(hash "$wave/data/rates/in/ticks-$day.csv")"; b="$(hash "$out/seed/ticks-$day.csv")"
  printf '%s\t%s\t%s\n' "$day" "$a" "$b" >> "$out/seed/hashes.tsv"
  [[ "$a" == "$b" ]] || { echo "Seed mismatch: $day" >&2; exit 1; }
done
job() {
  local name="parity-$1"; shift
  "${k[@]}" delete job "$name" -n app-rates-batch --ignore-not-found --wait=true >/dev/null
  python3 - "$out/cronjob.json" "$name" "$@" <<'PY' | "${k[@]}" create -f - >/dev/null
import json, sys
c = json.load(open(sys.argv[1]))
spec = c['spec']['jobTemplate']['spec']
spec['backoffLimit'] = 0
spec['activeDeadlineSeconds'] = 120
spec['template']['spec']['containers'][0]['command'] = ['java', '-XX:MaxRAMPercentage=70', '-jar', '/app/rates-batch.jar'] + sys.argv[3:]
print(json.dumps({'apiVersion': 'batch/v1', 'kind': 'Job',
                 'metadata': {'name': sys.argv[2], 'namespace': 'app-rates-batch', 'labels': c['metadata']['labels']}, 'spec': spec}))
PY
  job_rc=""
  for _ in $(seq 1 150); do
    job_rc="$("${k[@]}" get pods -n app-rates-batch -l "job-name=$name" -o 'jsonpath={.items[0].status.containerStatuses[0].state.terminated.exitCode}' 2>/dev/null || true)"
    [[ -z "$job_rc" ]] || break
    sleep 1
  done
  [[ -n "$job_rc" ]] || { echo "$name did not terminate" >&2; exit 1; }
  "${k[@]}" logs -n app-rates-batch "job/$name" > "$out/container/${name#parity-}.log"
  if [[ "$job_rc" == 0 ]]; then "${k[@]}" wait -n app-rates-batch --for=condition=Complete "job/$name" --timeout=30s >/dev/null; fi
}
for i in "${!days[@]}"; do
  day="${days[$i]}"
  job "$day" s3://bank-rates/in s3://bank-rates/out "$day"
  [[ "$job_rc" == 0 ]]
  get "out/rates-$day.csv" "$out/container/rates-$day.csv"
  "${compose[@]}" exec -T rates-01 /opt/rates/bin/run-rates.sh "$day"
  "${compose[@]}" exec -T rates-01 tail -n 1 /var/log/rates/rates.log > "$out/vm/$day.log"
  "${compose[@]}" exec -T rates-01 cat "/var/spool/rates/out/rates-$day.csv" > "$out/vm/rates-$day.csv"
  a="$(hash "$out/vm/rates-$day.csv")"; b="$(hash "$out/container/rates-$day.csv")"
  valid=no; [[ "$a" != "${expected[$i]}" || "$b" != "${expected[$i]}" ]] || valid=yes
  record "$((i + 1))-csv-$day" "$a" "$b" "$valid"
done
for i in "${!days[@]}"; do
  day="${days[$i]}"
  a="$(sed 's#/var/spool/rates/out#<OUT>#g' "$out/vm/$day.log")"
  b="$(sed 's#s3://bank-rates/out#<OUT>#g' "$out/container/$day.log")"
  record "$((i + 4))-stdout-$day" "$a" "$b"
done
vm_error() {
  local name="$1"; shift
  vm_rc=0
  "${compose[@]}" exec -T rates-01 java -Xmx256m -jar /opt/rates/lib/rates-batch.jar "$@" > "$out/vm/$name.stdout" 2> "$out/vm/$name.stderr" || vm_rc=$?
}
vm_error unknown /var/spool/rates/in /var/spool/rates/out 2026-10-17
job unknown s3://bank-rates/in s3://bank-rates/out 2026-10-17
a="$vm_rc: $(sed 's#/var/spool/rates/in#<IN>#g' "$out/vm/unknown.stderr")"
b="$job_rc: $(sed 's#s3://bank-rates/in#<IN>#g' "$out/container/unknown.log")"
record 7-unknown-day "$a" "$b" "$([[ "$vm_rc" == 1 ]] && echo yes || echo no)"
vm_error invalid /var/spool/rates/in /var/spool/rates/out 2026-13-01
job invalid s3://bank-rates/in s3://bank-rates/out 2026-13-01
record 8-invalid-day "$vm_rc: $(head -n 1 "$out/vm/invalid.stderr")" "$job_rc: $(head -n 1 "$out/container/invalid.log")"
vm_error usage /var/spool/rates/in
job usage s3://bank-rates/in
record 9-missing-argument "$vm_rc: $(cat "$out/vm/usage.stderr")" "$job_rc: $(cat "$out/container/usage.log")" "$([[ "$vm_rc" == 2 ]] && echo yes || echo no)"
docker rm -f w1-report-02 >/dev/null 2>&1 || true
docker run -d --name w1-report-02 -v "$out/container:/mnt/rates-out:ro" -p 127.0.0.1:8087:80 wave1/fx-report-vm > "$out/report-container.id"
for _ in $(seq 1 60); do
  if curl -s http://127.0.0.1:8087/ -o /dev/null; then break; fi
  sleep 1
done
for i in "${!days[@]}"; do
  day="${days[$i]}"
  a="$(curl -sS -o "$out/vm/page-$day.html" -w '%{http_code};%{content_type}' "http://localhost:8086/fx/fx-report.cgi?day=$day")"
  b="$(curl -sS -o "$out/container/page-$day.html" -w '%{http_code};%{content_type}' "http://localhost:8087/fx/fx-report.cgi?day=$day")"
  record "$((i + 10))-report-$day" "$a;$(hash "$out/vm/page-$day.html")" "$b;$(hash "$out/container/page-$day.html")" "$([[ "$a" == 200\;* ]] && echo yes || echo no)"
done
cat "$here/results.tsv"
[[ "$failures" == 0 ]]
