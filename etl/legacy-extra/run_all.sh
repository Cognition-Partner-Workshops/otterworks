#!/bin/bash
#############################################################
# run_all.sh — "orchestration"
#
# Runs the whole CUSTBILL chain end to end. Dependency
# management is a sleep: we assume each stage is done after
# 10 minutes. If it isn't, the next stage runs on partial
# data. This has been "good enough" since 2014.
#
# Set RUN_ALL_SLEEP=0 for demo/dev runs (added 2022 so the
# new hire could demo it without waiting 20 minutes).
#
# CUSTBILL_IMPL=python runs the byte-identical Python ports in
# pyjobs/ instead of the legacy scripts (added 2026, same sleeps).
#############################################################

DIR=`dirname $0`
SLEEP=${RUN_ALL_SLEEP:-600}

stage() {
    if [ "${CUSTBILL_IMPL:-legacy}" = python ]; then
        ${CUSTBILL_PYTHON:-python3} $DIR/pyjobs/$1.py
    else
        $DIR/jobs/$2
    fi
}

echo "`date` run_all starting (sleep=$SLEEP between stages)"

stage sftp_ingest_poll sftp_ingest_poll.ksh 2>/dev/null || true
sleep $SLEEP   # "wait for ingest to finish"

stage parse_custbill_fixedwidth parse_custbill_fixedwidth.sh 2>/dev/null || true
sleep $SLEEP   # "wait for parse to finish"

stage finance_excel_report finance_excel_report.pl 2>/dev/null || true

echo "`date` run_all done (probably)"
exit 0
