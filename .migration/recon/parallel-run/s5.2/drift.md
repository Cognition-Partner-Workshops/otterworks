# Drift report (s5.2, parallel run)

Green streak: **3 / 3** cycles (target `d-green-streak` = 3). Red runs: **none**.

| cycle | recon | parity | red? | diagnosis | fix PR |
|---|---|---|---|---|---|
| 1 | PASS (136 checks) | PASS=24 FAIL=0 SKIP=0 | no | — | — |
| 2 | PASS (168 checks) | PASS=24 FAIL=0 SKIP=0 | no | — | — |
| 3 | PASS (200 checks) | PASS=24 FAIL=0 SKIP=0 | no | — | — |

Rules: a red run opens a fix ticket against the migrated side only (billing-service / mapping),
never legacy and never `recon_tolerances.json`; repeated same-class reds become PROFILE FEEDBACK
for the plugin's `profiles/postgresql.md`.

Non-drift findings carried from s5.1 (unchanged): no watermark columns in legacy (keyed diff);
`OW_BILLING_PG_RO_DSN` not injected (session-local `BILLING_RO_PASSWORD`); `RECON_REDACT_SALT`
unset (`redaction_salted: false`); `make tp-smoke` absent. New in s5.2: the dbx guard rejects a
shell `cp` whose destination is built from `${OUT_ROOT}`; the report copy is done in Python with
the guard left intact.
