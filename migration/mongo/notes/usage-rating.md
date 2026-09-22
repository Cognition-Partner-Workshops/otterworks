# Unit notes: usage-rating (w2-b01)

Collections: `usageEvents` (USAGE_EVENTS, keyed id), `ratingPeriods`
(RATING_PERIODS, embeds RATING_RESULTS as `results[]` keyed id,
`parent_key PERIOD_ID` → `parent_ref ID`).

## Trigger port: trg_usage_events_check (01_tables.sql:238-252)

The Oracle trigger enforces `UNITS > 0` on insert/update of USAGE_EVENTS.
Migrated replacement: JSON-schema validation `units > 0` on `usageEvents`
plus a billing-service application check at write time. **Not created in
this unit** — the validator lands with the application cutover; noted here
per the unit brief so the port is tracked.

## Fixture note

`trg_usage_events_check` is real in the fixture DDL and enforces BOTH
`units > 0` AND `kind_cd in CODES('USAGE_KIND')` (ORA-20002 on unknown
kind). Coverage gap: the brief's "kind_cd unknown to CODES" trap is
unseedable on this unit's table — the trigger rejects it at insert. Only
valid kinds (1/2/3) are seeded; unknown-kind handling is covered by the
codes unit's unknown-value traps instead.

## Traps seeded

120 usage events: TIMESTAMP at ms precision (microsecond component
multiples of 1000 so `datetime_utc_truncate_ms` is lossless), `kind_cd`
values 77/88 outside CODES, all UNITS > 0. 30 rating periods with 0, 1, 2,
3 or 4 embedded results (60 result rows total) — T1 counts
`sum(len(results))` against `count(RATING_RESULTS)`.

Baseline is recon-safe: no unparseable values (canon `unparseable: keep`
would make them legitimate T3 diffs, not quarantine).
