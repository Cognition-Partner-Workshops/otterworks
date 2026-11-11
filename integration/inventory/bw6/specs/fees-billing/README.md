# fees-billing — BW6 process inventory (round 1)

Source: `integration/legacy-bw6/Processes/fees-billing/` at commit `5c2ba511babbfacaba94c93a10d3e6b0542a7c4c`.

| Process | Trigger → outputs | Proposed classification | Spec |
|---|---|---|---|
| `halvergate.fees-billing.daily-fee` | `bw.jms.Timer` on `HB.DAILY.FEES` → Java `dailyFee` (static rate cache) → `fee_assessments` + `HB.FEE.CALCULATED` [`integration/legacy-bw6/Processes/fees-billing/daily-fee.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/daily-fee.bwp#L14) | needs-human-decision | [daily-fee.md](daily-fee.md) |
| `halvergate.fees-billing.fee-posting` | JMS queue `HB.FEE.POSTING` → HTTP POST `${billing.url}` → `fee_postings` + `HB.FEE.POSTED` [`integration/legacy-bw6/Processes/fees-billing/fee-posting.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-posting.bwp#L14) | needs-human-decision | [fee-posting.md](fee-posting.md) |
| `halvergate.fees-billing.fee-reversal` | JMS queue `HB.FEE.REVERSAL` → `fee_reversals` + `HB.FEE.REVERSED` [`integration/legacy-bw6/Processes/fees-billing/fee-reversal.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/fee-reversal.bwp#L14) | needs-human-decision (round 2: was straight-conversion) | [fee-reversal.md](fee-reversal.md) |
| `halvergate.fees-billing.month-end-summary` | `bw.internal.start` (never called) on `HB.MONTH.END.SUMMARY` → channel-dependent rounding → `fee_summaries` + `HB.FEE.SUMMARY` [`integration/legacy-bw6/Processes/fees-billing/month-end-summary.bwp:L14`](../../../../legacy-bw6/Processes/fees-billing/month-end-summary.bwp#L14) | needs-human-decision | [month-end-summary.md](month-end-summary.md) |

Common to all four: same `catchAll` → `JMSConfirm acknowledge=false, maxRedelivery 3, HB.UNDLV`; `AUTO_COMMIT` insert with no XA scope; no in-project producer for their input destinations and no in-project consumer for their outputs; no call-process edges in or out.

Round 2 cross-check: no cross-domain call-process or message edges; shared `HB.UNDLV`, `EmsConnection`, `LedgerJdbc`, `ServiceHttp` (fee-posting) and `Transforms/common/receipt.xsl`; `billing.url` identical in dev and prod. See the "Cross-domain check" section of each spec.
