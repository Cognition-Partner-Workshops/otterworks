# u-02-customers recon re-run under tol-2 (D-011)

Mode `fixture`, target_class `local`: NOT merge evidence. Live recon: not possible (offline). merge_eligible=false.

Inputs (from run branch `tp-run/mongodb-20260926T164803Z-rt-offline`): `.migration/02_tolerances.json` (tol-2),
`.migration/profiles/oracle.md` (engagement overlay), mapping subset `specs/u-02-customers.mapping.json` (map-draft-2, verbatim
subset of `.migration/03_mapping_spec.json`). Harness mongo-recon-harness 0.3.2. Loader re-run first (drop+recreate own two collections).

Run log (cap 3):
- Refused (exit 2, nothing written): recon 0.3.2 rejects the tol-2 file's annotation keys `canonicalization_profile`,
  `grading_of_quarantined_values`. Re-invoked with a copy carrying only the harness keys (version tol-2, threshold 100000,
  sample 1000, abs_tol 0, rel_tol 0, concurrency 1); no tolerance value changed.
- Run 1 (evidence, this folder): T1 PASS (3), T2 PASS (30), **T3 FAIL (63)** = 50 `SIGNUP_DT->signupDt` + 13 `RELATED_ACCT_IDS->relatedAcctIds`.
  Verdict FAIL. Identical count to tol-1.
- Run 2 (diagnostic only, scratch overlay, not evidence): overlay copy that also declares the spec alias
  `date_string_to_date:dby-b3d57e` with `unparseable=null` -> T3 FAIL (13), only the `relatedAcctIds` malformed_csv diffs remain.

Why the 50 bad_date diffs did not disappear: the spec field `SIGNUP_DT` references the `date_format`-decision alias
`date_string_to_date:dby-b3d57e`, whose params live in the spec's `canonicalization.rules` (format only). The overlay changes the
base rule name `date_string_to_date`, which this field does not reference; `merge_canon_rules` only overrides on an exact name
collision, so the alias never receives `unparseable=null` (findings show `date_string_to_date:dby-b3d57e!unconverted`).
Fix belongs to the orchestrator (overlay declares the alias name with the tol-2 param, or the harness propagates base-rule param
overrides to aliases). Not applied here: no tolerance, profile, spec, or loader change was made.

Remaining 13 `relatedAcctIds` diffs: `csv_to_array` has no `unparseable` param in recon 0.3.2 (recorded harness gap, D-011).

Quarantine counts (loader, unchanged): bad_date 50, malformed_csv 13, eav_orphan 0.
