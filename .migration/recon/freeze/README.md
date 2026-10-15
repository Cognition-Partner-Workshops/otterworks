# s6.2 freeze watermark gate

`watermark.py` declares/checks the frozen legacy state (read-only, SELECT-only role); `run_freeze.sh` runs
parity on Atlas → final keyed-diff delta → full live recon → delta re-run (no-op) → watermark re-check.
Committed artifacts: `watermark.json`, `watermark-check-before.json`, `parity/`, `delta.json`, `recon/`,
`delta-rerun.json`, `watermark-check-after.json`. Verdict: PASS, merge_eligible, freeze held. The watermark
is declared, not a schema column (none exists); table content hashes prove the gate ran at it. The WAL LSN is
recorded for context only — an idle PostgreSQL still advances it. Secrets by name: the source came from a
session-local `billing_ro` password standing in for `OW_BILLING_PG_RO_DSN`, and `RECON_REDACT_SALT` was
session-local; both remain open issues for production (runbook §2).
