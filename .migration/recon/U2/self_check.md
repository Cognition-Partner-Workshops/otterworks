# U2 pre-PR self-check

Evidence was collected for the U2 migration unit on branch
`tp-run/mongodb-20260901T205236Z--u2`, including the merged-head load and
second official recon. Secret values are not recorded.

| Check | Status | Evidence |
|---|---|---|
| NULL and missing attribution cannot fail open | [x] | Official recon PASS; orphan lines, including NULL `invoice_id`, are quarantined by the loader and counted in `load_report.json`. |
| Every catalog, schema, collection, and table reference is scoped to the unit namespace and uses the `ow_tp` / `ow-tp-` prefix | [x] | `result.json`, `u2.recon.json`, and `load_report.json` show target databases `ow_tp_mongodb_205236` and `ow_tp_mongodb_205236_quarantine`, with `ns=mongo_205236`; target namespace checks PASS. |
| No DDL drops, replaces, or alters a shared table | [x] | `scripts/tp_mongo/load_u2.py` drops only the owned `invoices` and `invoice_feed_orphan_lines` collections; sibling snapshots in `idempotency.md` are unchanged. |
| Retention and cleanup logic is safe on a rerun and does not remove a newer run's data | [x] | Two live loader runs completed; both reports show the same U2 counts and IDs, and only the two U2-owned collections were recreated. |
| Cleanup paths retain run evidence and recon artifacts | [x] | `load_run1.log`, `load_run2.log`, `load_run3.log`, both load reports, `result.json`, `report.md`, `u2.recon.json`, and `recon.summary.md` are retained under this directory. |
| No secrets, tokens, or real distribution-list/email addresses occur in source, evidence, or commit history | [~] | Automated scan of all 13 files under `.migration/recon/U2/` found no MongoDB SRV URI, credential token, fixture credential string, or echoed fixture host. Commit history was not exhaustively audited in this evidence pass. |
| The parity-versus-tolerance decision matches the contract; it was not invented during implementation | [x] | Official recon used `.migration/02_tolerances.json` version `v1` and `.migration/canonicalization.json`; `result.json` verdict is PASS. |
| Idempotency was proven by an actual rerun, not inferred from code | [x] | `idempotency.md` records the original two loader runs; `load_run3.log` and `load_report.json` record the merged-head rerun, with matching U2 counts and identical quarantined IDs. |
| Recon values were recomputed from the target platform, not copied from migration memory or a previous report | [x] | The merged-head `u2.recon.json` records Atlas `count_documents`, `$unwind` line counts, namespace checks, and `list_indexes`; all target checks PASS. |
| Every unverified or untested path is listed in the recon report | [x] | `recon.summary.md` and `u2.recon.json` list Tier 4 app parity scope, full-diff versus stratified sampling, derived fields, admin UI, and the parent-owned live gate. |
| The recon report declares `"kind": "recon-report"` and is stored as a `*.recon.json` artifact | [x] | `.migration/recon/U2/u2.recon.json` contains `"kind": "recon-report"` and passed `make tp-validate-recon`. |
| Capability preflight passed for every required path before live work | [~] | No standalone U2 capability-preflight manifest was available. Atlas and Oracle connectivity were exercised successfully by the two live loader runs, official live recon, and RPT-114 parity; this checklist item remains a documented gap. |
| `make tp-smoke` is green | [x] | `make tp-smoke 2>&1 | tail -30` completed with `tp-smoke: all checks passed`. |

## Additional verification

- Official harness: PASS; tier 1, tier 2, and tier 3 all passed.
- The official live recon was rerun on merged head `09fe0852` using the U2-scoped mapping; the second recon passed.
- Three loader runs are represented by `load_run1.log`, `load_run2.log`, and merged-head `load_run3.log`.
- Tier 3: `embeds_graded` contains `invoices.lines: 149963`; no `embeds_ungraded` entry is present.
- Counts: `18750` invoices, `149963` embedded lines, `37` quarantined lines, totaling `150000`.
- RPT-114 parity: `status_rows_match=True`, `line_rows_match=True`, `diffs=0`.
- Recon schema validation: `u2.recon.json` PASS. The separate validation of harness `result.json` is not applicable to the report schema and returned the expected missing report-envelope fields.
