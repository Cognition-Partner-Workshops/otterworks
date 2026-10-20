#!/usr/bin/env bash
# Local claims-hub-camel for the claims screens: backing containers, seeded database, the hub jar, corpus replay.
#   ./hub.sh up        containers + seed + start the hub (logs in run/hub.log)
#   ./hub.sh replay    drop the 10 assignment requests, 14 payment instructions and the FNOLs not given as arguments
#   ./hub.sh down      stop the hub and remove every container and volume
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
INS="$(cd "$HERE/../.." && pwd)"
HUB="$INS/claims-hub-camel"
CORPUS="$INS/biztalk-claims-intake/corpus/inputs"
RUN="$HERE/run"
compose() { docker compose -f "$HERE/docker-compose.yml" "$@"; }

up() {
  rm -rf "$RUN"; mkdir -p "$RUN/keys" "$RUN/vendor-inbox/tmp" "$RUN/inbox"/{fnol,assignment,payment,tracking/fnol} "$RUN/archive"
  chmod -R 777 "$RUN/vendor-inbox"
  ssh-keygen -q -t rsa -b 3072 -m PEM -N "" -C thistlecombe-remit -f "$RUN/keys/id_rsa"
  compose up -d --wait
  python3 "$HERE/seed.py" | compose exec -T postgres psql -q -v ON_ERROR_STOP=1 -U claimshub -d claimshub >/dev/null
  for i in $(seq 1 30); do ssh-keyscan -p 2222 127.0.0.1 2>/dev/null | sed 's/^127.0.0.1/[127.0.0.1]:2222/' > "$RUN/keys/known_hosts"; [ -s "$RUN/keys/known_hosts" ] && break; sleep 1; done
  [ -f "$HUB/target/claims-hub-camel.jar" ] || (cd "$HUB" && ./mvnw -B -q -DskipTests package)
  (cd "$RUN" && \
    CLAIMS_DB_URL=jdbc:postgresql://127.0.0.1:55432/claimshub CLAIMS_DB_USER=claimshub CLAIMS_DB_PASSWORD=claimshub \
    CLAIMS_LEDGER_MIGRATE=true \
    CLAIMS_FIXTURE_DIR="$INS/biztalk-claims-intake" \
    CLAIMSHUB_FNOL_FIXTURE_DIR="$INS/biztalk-claims-intake" \
    CLAIMSHUB_FNOL_OUT_DIR="$RUN/out" \
    CLAIMSHUB_FNOL_CORRECTION_WINDOW="${CORRECTION_WINDOW:-5s}" \
    CLAIMSHUB_FNOL_COMPLETED_URI=direct:tracking.fnol CLAIMSHUB_FNOL_SUSPENDED_URI=direct:tracking.fnol \
    CLAIMSHUB_LOCAL_INBOX_ENABLED=true CLAIMSHUB_LOCAL_INBOX_DIR="$RUN/inbox" \
    CLAIMSHUB_ARCHIVE_DIR="$RUN/archive" CLAIMSHUB_SMTP_HOST=127.0.0.1 CLAIMSHUB_SMTP_PORT=1025 \
    CLAIMS_PAYMENT_INBOX="$RUN/inbox/payment" \
    CLAIMS_PAYMENT_VENDOR_HOST=127.0.0.1 CLAIMS_PAYMENT_VENDOR_PORT=2222 \
    PAYVENDOR_SFTP_KEY="$RUN/keys/id_rsa" PAYVENDOR_SFTP_KNOWN_HOSTS="$RUN/keys/known_hosts" \
    CLAIMS_PAYMENT_VENDOR_WINDOW_ENABLED="${VENDOR_WINDOW:-false}" \
    CLAIMS_OPS_SMTP_HOST=127.0.0.1 CLAIMS_OPS_SMTP_PORT=1025 \
    nohup java -jar "$HUB/target/claims-hub-camel.jar" > "$RUN/hub.log" 2>&1 & echo $! > "$RUN/hub.pid")
  for i in $(seq 1 60); do curl -fsS http://127.0.0.1:8092/health >/dev/null 2>&1 && { echo "hub up (pid $(cat "$RUN/hub.pid"))"; return; }; sleep 1; done
  echo "hub did not come up; see $RUN/hub.log" >&2; exit 1
}

drop() { cp "$1" "$2/.$(basename "$1").tmp" && mv "$2/.$(basename "$1").tmp" "$2/$(basename "$1")"; }

replay() {
  for f in "$CORPUS"/assignment/*.xml; do drop "$f" "$RUN/inbox/assignment"; done
  for f in "$CORPUS"/payment/*.xml; do drop "$f" "$RUN/inbox/payment"; done
  for f in "$CORPUS"/fnol/*.xml; do
    claim="$(basename "$f" .xml)"; [[ " $* " == *" $claim "* ]] && continue
    drop "$f" "$RUN/inbox/fnol"
  done
}

down() {
  if [ -f "$RUN/hub.pid" ]; then
    pid="$(cat "$RUN/hub.pid")"
    kill "$pid" 2>/dev/null || true
    for i in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -9 "$pid" 2>/dev/null || true
  fi
  compose down -v --remove-orphans
}

"${1:-up}" "${@:2}"
