# Unit notes: invoicing (w2-b02)

Collections: `invoices` (INVOICES, embeds INVOICE_LINES as `lines[]` keyed
`lineNo`, `parent_key INVOICE_ID` → `parent_ref ID`), `creditNotes`
(CREDIT_NOTES).

## FK reality

INVOICE_LINES.invoice_id is a real FK (`01_tables.sql:132`, ON DELETE
CASCADE) — orphan lines cannot exist here, unlike the legacy feed.
`pkg_invoicing` rebuilds all lines with the invoice
(04_pkg_invoicing.sql:150-157), so the embed is 1:few and derived; T1
counts `sum(len(lines))` = count(INVOICE_LINES).

## Traps seeded

40 invoices with 0..6 lines each (84 lines): amounts at NUMBER(12,2)
scale edges (0.01, 9999999999.99), `status_cd` values incl. 55 outside
CODES, issued_at at ms precision. 15 credit notes: fully burned
(remaining=0), half burned, untouched. `period_id` points at
RATING_PERIODS rows seeded by the usage-rating unit (FK satisfied).

Baseline is recon-safe: no unparseable/malformed values — canon
`unparseable: keep` would make them legitimate T3 diffs, not quarantine.
