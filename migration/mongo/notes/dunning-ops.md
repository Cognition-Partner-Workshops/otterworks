# Unit notes: dunning-ops (w2-b03)

Collections: `dunningAttempts`, `notifications`, `billingAuditLog`
(numeric `logId` stays the `_id`).

## TTL replaces JOB_PURGE_AUDIT_LOG

`JOB_PURGE_AUDIT_LOG` (04_jobs.sql:19-27) deletes audit rows older than 90
days. Migrated replacement: TTL index `loggedAt expireAfterSeconds=7776000`
(90 days), created by `loaders/dunning_ops.py` after the load. Fixture
`logged_at` values are within 90 days so recon counts match before any
expiry.

## Indexes mirroring Oracle constraints

`dunningAttempts (invoiceId, attemptNo)` is a unique compound index
mirroring UQ_DUNNING_ATTEMPTS (integer keys, lossless).
`notifications (tenantId, kindCd, sentAt)` indexes the UQ_NOTIFICATIONS
dedupe key but is **not unique on the target**: T4 truncates `sentAt` to
milliseconds, so a unique index could reject two legal Oracle rows that
differ only below 1 ms. Enforcing the dedupe needs a target dedupe
contract decision — open item, logged as a coverage gap.

## Open: JOB_NIGHTLY_DUNNING owner

STOP B U-5 leaves the owner of the nightly dunning job open — it becomes a
billing-service scheduled job, but **which service owns it is undecided**.
Noted here per the unit brief; nothing invented.

## Traps seeded

60 attempts over 30 invoices (1-3 attempts each, statuses spread), 20
notifications exercising the natural dedupe key `(tenant_id, kind_cd,
sent_at)` UQ, 15 audit rows with 4000-char messages and NULL `module`.
Baseline recon-safe: no unparseable values.
