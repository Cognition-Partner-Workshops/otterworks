#!/usr/bin/env bash
# parity.sh — golden capture and byte-for-byte cmp parity for the CUSTBILL chain.
#
#   parity.sh capture <legacy|python> <job|chain> <ns> <outdir>
#   parity.sh compare <capture-a> <capture-b>        # cmp every captured file
#   parity.sh check   <job|chain> <ns>               # capture both impls, compare
#   parity.sh golden  <job> <ns>                     # write pyjobs/tests/golden/<job>/<ns>
#
# A job capture starts from a fresh run root seeded by gen_sample_data.pl for
# <ns>, runs every upstream stage with the legacy implementation, snapshots
# before/, runs <job> with the chosen implementation, snapshots after/. A chain
# capture runs run_all.sh (RUN_ALL_SLEEP=0, CUSTBILL_IMPL=<impl>) instead.
# A snapshot is tree/ (copy of the run root), manifest (path type size),
# stdout, stderr, exit_code and locks (state of the three /tmp lock files).
#
# Determinism: TZ=UTC, LC_ALL=C, clock frozen at CUSTBILL_NOW (default
# 2026-01-15 00:00:00) via tools/detclock (date shim + Perl module) for legacy
# and custbill_common.now_epoch() for Python. The run root path is redacted to
# $OTTERWORKS_LEGACY_ROOT in stdout/stderr. The job's /tmp lock files are
# removed before each run so both sides start from the same lock state.
set -euo pipefail

ESTATE=$(cd "$(dirname "$0")/.." && pwd)
PYTHON=${CUSTBILL_PYTHON:-python3}
NOW=${CUSTBILL_NOW:-2026-01-15 00:00:00}
OUT_BASE=${PARITY_OUT:-/tmp/custbill-parity}
JOBS="sftp_ingest_poll parse_custbill_fixedwidth finance_excel_report"
LOCKS="/tmp/sftp_ingest.lock /tmp/parse_custbill.lock /tmp/finance_report.lock"

die() { echo "parity: $*" >&2; exit 2; }

valid_job() { case " $JOBS chain " in *" $1 "*) ;; *) die "unknown job '$1' (one of: $JOBS chain)";; esac; }
valid_ns()  { [[ "$1" =~ ^[A-Za-z0-9_]+$ ]] || die "NS must match [A-Za-z0-9_]+"; }

lock_of() {
  case "$1" in
    sftp_ingest_poll) echo /tmp/sftp_ingest.lock ;;
    parse_custbill_fixedwidth) echo /tmp/parse_custbill.lock ;;
    finance_excel_report) echo /tmp/finance_report.lock ;;
  esac
}

det_env() {
  env TZ=UTC LC_ALL=C LANG=C CUSTBILL_NOW="$NOW" \
      PATH="$ESTATE/tools/detclock:$PATH" \
      PERL5LIB="$ESTATE/tools/detclock${PERL5LIB:+:$PERL5LIB}" PERL5OPT=-MCustbillDetClock \
      OTTERWORKS_LEGACY_ROOT="$ROOT" "$@"
}

job_cmd() {  # impl job
  case "$1:$2" in
    legacy:sftp_ingest_poll)          echo "ksh $ESTATE/jobs/sftp_ingest_poll.ksh" ;;
    legacy:parse_custbill_fixedwidth) echo "bash $ESTATE/jobs/parse_custbill_fixedwidth.sh" ;;
    legacy:finance_excel_report)      echo "perl $ESTATE/jobs/finance_excel_report.pl" ;;
    python:*)
      [ -f "$ESTATE/pyjobs/$2.py" ] || die "no Python port at pyjobs/$2.py"
      echo "$PYTHON $ESTATE/pyjobs/$2.py" ;;
    *) die "unknown impl '$1'" ;;
  esac
}

snapshot() {  # dest stdout-file stderr-file rc
  local dest=$1
  mkdir -p "$dest"
  cp -a "$ROOT/." "$dest/tree/" 2>/dev/null || mkdir -p "$dest/tree"
  (cd "$ROOT" && find . -mindepth 1 \( -type d -printf '%P d -\n' \) -o \( -type f -printf '%P f %s\n' \) | LC_ALL=C sort) > "$dest/manifest"
  sed "s|$ROOT|\$OTTERWORKS_LEGACY_ROOT|g" "$2" > "$dest/stdout"
  sed "s|$ROOT|\$OTTERWORKS_LEGACY_ROOT|g" "$3" > "$dest/stderr"
  echo "$4" > "$dest/exit_code"
  : > "$dest/locks"
  for l in $LOCKS; do
    if [ -f "$l" ]; then echo "$(basename "$l") present"; else echo "$(basename "$l") absent"; fi >> "$dest/locks"
  done
}

run_into() {  # dest cmd...   (runs under det_env, snapshots afterwards)
  local dest=$1; shift
  local o e rc=0
  o=$(mktemp); e=$(mktemp)
  det_env "$@" > "$o" 2> "$e" || rc=$?
  snapshot "$dest" "$o" "$e" "$rc"
  rm -f "$o" "$e"
}

capture() {  # impl job ns outdir
  local impl=$1 job=$2 ns=$3 out=$4
  valid_job "$job"; valid_ns "$ns"
  [ "$impl" = legacy ] || [ "$impl" = python ] || die "impl must be legacy or python"
  rm -rf "$out"; mkdir -p "$out"
  ROOT=$(mktemp -d /tmp/custbill-parity-root.XXXXXX)
  det_env perl "$ESTATE/tools/gen_sample_data.pl" "$ns" > /dev/null
  if [ "$job" = chain ]; then
    # shellcheck disable=SC2086
    rm -f $LOCKS
    snapshot "$out/before" /dev/null /dev/null 0
    run_into "$out/after" env RUN_ALL_SLEEP=0 CUSTBILL_IMPL="$impl" CUSTBILL_PYTHON="$PYTHON" bash "$ESTATE/run_all.sh"
  else
    local j
    for j in $JOBS; do
      [ "$j" = "$job" ] && break
      # shellcheck disable=SC2046
      det_env $(job_cmd legacy "$j") > /dev/null 2>&1 || true
    done
    rm -f "$(lock_of "$job")"
    snapshot "$out/before" /dev/null /dev/null 0
    # shellcheck disable=SC2046
    run_into "$out/after" $(job_cmd "$impl" "$job")
  fi
  rm -rf "$ROOT"
}

compare() {  # a b ; cmp every file of both captures
  local a=$1 b=$2 n=0 bad=0 f msg
  [ -d "$a" ] && [ -d "$b" ] || die "compare needs two capture dirs"
  while IFS= read -r f; do
    n=$((n + 1))
    if [ ! -f "$a/$f" ] || [ ! -f "$b/$f" ]; then
      echo "MISSING  $f ($( [ -f "$a/$f" ] || echo "absent in $a")$( [ -f "$b/$f" ] || echo "absent in $b"))"
      bad=$((bad + 1))
    elif msg=$(cmp "$a/$f" "$b/$f" 2>&1); then
      echo "IDENTICAL $f"
    else
      echo "DIFFERS  $f: $msg"
      bad=$((bad + 1))
    fi
  done < <( { (cd "$a" && find . -type f -printf '%P\n'); (cd "$b" && find . -type f -printf '%P\n'); } | LC_ALL=C sort -u)
  echo "cmp: $n files compared, $bad differ"
  [ "$bad" -eq 0 ]
}

cmd=${1:-}; shift || true
case "$cmd" in
  capture) [ $# -eq 4 ] || die "usage: capture <legacy|python> <job|chain> <ns> <outdir>"; capture "$@" ;;
  compare) [ $# -eq 2 ] || die "usage: compare <a> <b>"; compare "$@" ;;
  check)
    [ $# -eq 2 ] || die "usage: check <job|chain> <ns>"
    out="$OUT_BASE/$2/$1"
    capture legacy "$1" "$2" "$out/legacy"
    capture python "$1" "$2" "$out/python"
    echo "== cmp legacy vs python: $1 NS=$2 (CUSTBILL_NOW=$NOW)"
    compare "$out/legacy" "$out/python" ;;
  golden)
    [ $# -eq 2 ] || die "usage: golden <job> <ns>"
    [ "$1" != chain ] || die "golden fixtures are per job"
    capture legacy "$1" "$2" "$ESTATE/pyjobs/tests/golden/$1/$2"
    echo "wrote $ESTATE/pyjobs/tests/golden/$1/$2" ;;
  *) sed -n '2,20p' "$0"; exit 2 ;;
esac
