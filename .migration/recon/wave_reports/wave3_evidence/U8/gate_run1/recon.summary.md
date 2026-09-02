# Recon summary: `U8` - **FAIL**

- Mode: `live`
- Mapping `v1.0.1` / tolerances `v1` / seed `714559852` / params `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T03:24:37.315752+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 8 | FAIL (4) |

Top findings (4 of 4; full list in result.json):
- T1 `replay_u8_rating_periods` root_count: rows(RATING_PERIODS)=3 vs docs=6
- T1 `replay_u8_rating_periods` embed_cardinality: rows(RATING_RESULTS)=3 vs sum(len(results))=6
- T1 `replay_u8_billing_invoices` root_count: rows(INVOICES)=3 vs docs=6
- T1 `replay_u8_billing_invoices` embed_cardinality: rows(INVOICE_LINES)=2 vs sum(len(lines))=17

Full evidence: result.json, report.md (linked from the PR, not pasted).
