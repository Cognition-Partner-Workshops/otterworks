# Finance account status workbook

The nightly warehouse chain writes a headerless pipe-delimited file at
`warehouse/exports/account_status_YYYYMMDD.psv`. It has an ISO business date,
an account status code, a currency code and an account count per group.

In Excel, define a one-cell named range `AccountStatusExtract` with the full
path to the dated file. Make a blank Power Query and paste
[`account_status.pq`](account_status.pq) into the Advanced Editor. Load the
result to a table, then use a PivotTable with status on rows, currency on
columns, and the sum of AccountCount as values. Change the named cell and
refresh for a different business date. The workbook has no database login;
rows with empty status or currency are unknown, not zero.
