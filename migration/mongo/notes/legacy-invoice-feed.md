# Unit notes: legacy-invoice-feed (w1-b03)

Collections: `legacyInvoices` (INVOICE_HEADER, keyed invoiceId),
`legacyInvoiceLines` (INVOICE_LINE, keyed lineId). Lines stay a separate
collection referenced by `invoiceId` — no FK; orphan lines are legitimate
rows and load normally (billing-report-contract.md:30-31).

## Orphan report

`migration/mongo/tools/orphan_report.py` counts lines whose `invoiceId` has
no matching header on both sides. Fixture run after load:

```
oracle_orphan_lines=40 mongo_orphan_lines=40
```

40 of the 4000 seeded lines reference `SYNTH-INV-GHOST-*` headers that do
not exist — the RPT-114 inner join drops these on the Oracle side and the
separate-collection target preserves them, matching both sides.

## Traps seeded

500 headers / 4000 lines: `invoice_dt`/`due_dt` DD-MON-YY text incl. NULL,
`posted_yn` CHAR(1) Y/N/NULL, `gl_acct_csv` NULL / single / multi-item
well-formed lists, `service_period` MMYYYY-MMYYYY, `line_type_cd` numeric
incl. out-of-CODES value, status_cd out-of-set value, qty/unit_price/amount
at declared NUMBER scale edges, copied `cust_*` fields that deliberately
disagree with the customers unit (unenforced pointers — counted as refs,
not checked for equality), 40 orphan lines.

Baseline is recon-safe: no unparseable dates, no malformed CSVs — canon
`unparseable: keep` would make either a legitimate FAIL, not quarantine.
Fault leg: `fault_inject.py --collection legacyInvoiceLines --mode
drop-one` → Tier 1 root_count FAIL → reload → PASS.
