# 02 Tolerances — correctness contract (version `tol-v1`)

Source family `mongodb-atlas`: relational tolerance rows are skipped (setup playbook step 7). Tolerances are count and checksum parity per collection plus index and shard-key equivalence. All values exact (intake FACT). Machine copy: `02_tolerances.json`.

| Check | Rule | Mark |
|---|---|---|
| Document count per collection | exact (after declared quarantine; quarantined docs counted separately and reconciled to `_quarantine_<collection>`) | FACT |
| Document checksum per collection | exact on canonicalized BSON (profile `recon_canonicalization` rules) | FACT |
| Keyed diff | full keyed diff on `_id` at or below `full_diff_row_threshold` = 100000 rows; keyed sample (`sample_size` 1000) plus full aggregates above | FACT |
| Numeric values | `numeric_abs_tol` = 0 (Int32/Int64/Double/Decimal128 identity-preserved) | FACT |
| Aggregates | `aggregate_rel_tol` = 0 | FACT |
| Dates | exact; BSON date to BSON date. Any string->date conversion (audit_events string timestamps) is a mapping decision recorded in `05_decisions.md`, verified by the harness against the declared canonical form | FACT |
| Strings | byte-exact; no case folding. Case-variant duplicate emails are a data decision, not a tolerance | FACT |
| NULL vs missing field | `null_missing_equiv` (setup default) | PROPOSED |
| Indexes | equivalent key spec, uniqueness, partial/TTL options per collection | FACT (profile) |
| Shard keys | n/a (unsharded M0); recorded as equivalence check = not applicable | DISCOVERED |
| Source query concurrency cap | 2 | FACT |
| Re-run cap | a child re-runs the full pipeline at most 3 times, then escalates | FACT (rule 7) |

## Connectivity
- Policy `online`: probe both sides, block on any failure, never fall back (intake FACT).
- Resolved axes (from `08_connectivity.json`): `source_access: live`, `target_access: migration_cluster`.
- Merge evidence requires `live`/`snapshot` AND `migration_cluster`; fixture or local-target recon is rehearsal only.

## Amendment rule
A tolerance value changes only by explicit human approval, recorded as a new dated row in `05_decisions.md` (old row kept) with a new `version` in both files and a list of merged units to re-verify. Exception (pre-approved at STOP A): grading-only fixes — a canonicalization rule or harness bug with no data or tolerance value change — are applied, logged, and mentioned at wave close.
