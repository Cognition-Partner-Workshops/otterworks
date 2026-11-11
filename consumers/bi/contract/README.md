# Finance contract targets

Replay and emulator targets execute frozen Teradata SQL and retain exact seed
assertions. Snowflake executes regenerated production SQL with read-only SELECTs.
Its dataset is about 250x the 800-row seed: counts/sums for 2026-11, GL periods,
and overdue account membership differ. CURRENT_DATE is the Snowflake UTC date
rather than the emulator business date.

Live checks require identical result columns and invoice/revenue/payment label
keys; invoice and revenue amounts must agree for each label. GL seed periods
must exist and every live period must balance to zero. Overdue results must be
1..100 positive balances ordered descending then account, with ACC- identifiers.
A separate account grouping check rejects case-only duplicates because the
legacy NOT CASESPECIFIC grouping would merge them. Query IDs are printed.
