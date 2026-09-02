# Recon report: unit `U8`

- **Verdict: FAIL**
- Mode: `live`
- Mapping version: `v1.0.1`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-02T03:24:37.315752+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 8 | FAIL (4 findings) |

## Tier 1 findings (4)
- `replay_u8_rating_periods` root_count: rows(RATING_PERIODS)=3 vs docs=6
- `replay_u8_rating_periods` embed_cardinality: rows(RATING_RESULTS)=3 vs sum(len(results))=6
- `replay_u8_billing_invoices` root_count: rows(INVOICES)=3 vs docs=6
- `replay_u8_billing_invoices` embed_cardinality: rows(INVOICE_LINES)=2 vs sum(len(lines))=17
