# Recon summary: `U2` - **PASS**


- Mode: fixture
- Mapping `v1.0.1` / tolerances `v1` / seed `714559852` / params `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T04:08:26.160162+00:00
- Counts: 18750 invoices / 149963 embedded lines / 37 quarantined lines = 150000 source lines
- Quarantine rate: 0.197%
- Indexes: `_id_, batch_no_1_status_cd_1, cust_id_1, lines.line_id_1`
- Load idempotency: PASS (run 1 and run 2 reports match)

| Check | Result |
|---|---|
| harness.verdict | PASS |
| harness.mapping_version | PASS |
| harness.tolerance_version | PASS |
| harness.tier1.counts_through_mapping | PASS |
| harness.tier2.per_field_aggregates | PASS |
| harness.tier3.keyed_diffs | PASS |
| harness.tier3.no_embeds_ungraded | PASS |
| target.invoices.count | PASS |
| target.invoices.embedded_lines | PASS |
| target.quarantine.invoice_feed_orphan_lines.count | PASS |
| target.invoices.ns_mismatch | PASS |
| target.quarantine.ns_mismatch | PASS |
| target.indexes | PASS |
| target.embedded_plus_quarantined | PASS |
| target.quarantine_rate | PASS |
| load.source_counts.invoice_header | PASS |
| load.source_counts.invoice_line | PASS |
| load.embedded_lines | PASS |
| load.quarantined_lines | PASS |

## Unverified paths

- Tier 4 app-level parity not in contract; RPT-114 was checked separately by scripts/tp_mongo/rpt114_parity_u2.py (see rpt114_parity.json)
- Harness stratified-sampling path not exercised because 18,750 < full_diff threshold, so full diff was used
- Derived invoice_date, due_date, and lines[].gl_accounts are derived_ungraded per mapping and only loader-unit-tested
- Admin-dashboard UI not exercised
- Live gate is the parent's responsibility

Full evidence: result.json, load_report.json.
