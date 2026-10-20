#!/bin/sh
# Runs the replatformed image the way the platform CronJob does: uid 10001,
# read-only root filesystem, /tmp as the only scratch space, zone from RATES_TZ.
# The spools are mounted at the same paths as on rates-01 so messages compare 1:1.
#   run-container.sh <in-dir> <out-dir> [yyyy-mm-dd]
in="$1"; out="$2"; shift 2
exec docker run --rm --read-only --user 10001:10001 --tmpfs /tmp -e RATES_TZ="${CHAR_TZ:-UTC}" \
  -v "$in":/var/spool/rates/in:ro -v "$out":/var/spool/rates/out \
  "${RATES_IMAGE:-bank-rates-batch:local}" /var/spool/rates/in /var/spool/rates/out "$@" 2>&1
