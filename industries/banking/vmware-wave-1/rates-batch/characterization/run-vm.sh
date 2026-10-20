#!/bin/sh
# Runs the VM stand-in exactly as root's crontab does: /opt/rates/bin/run-rates.sh
# with the host spools bind-mounted where rates-01 keeps them. The wrapper sends
# the job's output to /var/log/rates/rates.log, so that file is printed after the run.
#   run-vm.sh <in-dir> <out-dir> [yyyy-mm-dd]
in="$1"; out="$2"; shift 2
log="$(mktemp -d)"; chmod 0777 "$log"
docker run --rm -e TZ="${CHAR_TZ:-UTC}" \
  -v "$in":/var/spool/rates/in:ro -v "$out":/var/spool/rates/out -v "$log":/var/log/rates \
  "${RATES_VM_IMAGE:-wave1/rates-batch-vm}" /opt/rates/bin/run-rates.sh "$@"
rc=$?
cat "$log/rates.log" 2>/dev/null
rm -rf "$log" 2>/dev/null
exit $rc
