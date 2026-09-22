# Unit notes: tenancy-plans (w1-b01)

Collections: `tenants`, `plans`, `subscriptions`, `subscriptionVersions`.
Sources: TENANTS, PLANS, SUBSCRIPTIONS, SUBSCRIPTIONS_HIST.

## Trigger port: `trg_sub_no_uncancel` (application guard)

`services/legacy-billing/db/oracle/schema/01_tables.sql:224-236` defines a
BEFORE UPDATE OF status_cd trigger: once `status_cd = 30` (cancelled), any
UPDATE forces `:NEW.status_cd := 30` — a cancelled subscription can never
leave the cancelled state.

There is no trigger layer in MongoDB. The rule is ported as an application
guard on every path that writes `subscriptions.statusCd`:

> A write that would set `statusCd` on a document whose current
> `statusCd = 30` must leave it `30` — i.e. filter updates with
> `{_id: ..., statusCd: {$ne: 30}}` or read-check-refuse in the service.

No data effect at load time: history and the cancelled state migrate as
data; only future writers must uphold the guard. `pkg_plans.sp_change_plan`
already returns an error on cancelled subs in Oracle; the Mongo code path
must implement the same refusal.

## Notes

- `subscriptionVersions.histDt` is parsed from the string form
  `DD-MON-YY HH24:MI:SS` (spec `date_format: "%d-%b-%y %H:%M:%S"`), matching
  what `trg_subscriptions_hist` writes via `TO_CHAR(SYSDATE, ...)`.
- One fixture hist row carries `hist_dt='NOT-A-DATE'` to prove the
  unparseable-date path: field omitted, row quarantined to
  `migration/mongo/quarantine/subscriptionVersions.jsonl` (never the db).
- Fixture seeds `status_cd = 42` on SYNTH-SUB-UNKNOWN and `status_cd = 999`
  on SYNTH-TEN-3: codes resolve to labels at read time (facade.py:110-128)
  with the UNKNOWN(<cd>) contract; no code lookups are denormalised.
