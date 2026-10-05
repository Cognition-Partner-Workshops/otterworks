# Oracle billing census (plan step `s2.1-census`)

`census.py` runs plain read-only dictionary queries (python-oracledb thin,
`SET TRANSACTION READ ONLY`) against `OW_BILLING` as the `OW_TP_ORACLE_RO_DSN`
principal and writes `../census.json`. It aborts unless the principal's
`USER_SYS_PRIVS` / `USER_TAB_PRIVS` / `USER_ROLE_PRIVS` / `SESSION_PRIVS` are all
on the read-only allowlist, so the census itself is the evidence that the
principal cannot INSERT/UPDATE/DELETE or run DDL.

`buckets.json` is the hand-authored disposition of every non-index object
(indexes inherit their table's bucket); each entry carries a cite into
`services/legacy-billing/db/oracle/`. The script fails if any live object is
unbucketed or any bucket entry has no live object, so `census.json` always
covers the estate exactly once.

```sh
~/.venvs/ow-billing/bin/python migration/billing/census/census.py --ns demo
```

Row counts are exact `COUNT(*)` at capture time; `TENANTS` is shared across
namespaces and is additionally counted with `name LIKE '<ns>::%'`. `ALL_*`
views only list objects the principal has object privileges on (tables and
indexes via `SELECT ANY TABLE`), so packages, triggers, sequences, dependencies
and scheduler jobs come from the matching `DBA_*` view (`SELECT ANY DICTIONARY`);
`census.json#dictionary_views.queries` records which view supplied each class.
No Atlas access is used.
