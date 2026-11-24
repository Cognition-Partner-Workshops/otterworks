# Examiner report: rate changes, claimant PII, retention

This report answers three questions from the examiner's letter. Each answer
points to the object that gives it and to the test that proves it. Names
are fixed in [ESTATE.md](ESTATE.md).

## 1. Who changed a commission rate, and when?

`v_rate_change_history` in Oracle `COMMISSION_PAY` returns one row per change
to `commission_rates`. The rows come from trigger `TRG_AUD_COMMISSION_RATES`,
so they are written whether the change went through `commission_pkg` or
through a direct `UPDATE`, `INSERT` or `DELETE` run outside the package.
Changes made through the package are credited to the package's `p_actor`,
with the procedure named in `via_program`. Direct statements are credited to
the authenticated database user, OS user and host, with `via_program = SQL`.
The trail, `rate_audit_log` and `retention_run` refuse UPDATE and DELETE
(ORA-20901). Rows leave them only through the retention purge.

```sql
SELECT change_id, operation, changed_at, actor, via_program, old_rate_pct, new_rate_pct
  FROM v_rate_change_history WHERE rate_id = :x ORDER BY change_id;
```

Proof: `run_audit_tests.sql`. It was committed before the trigger existed
and failed 7 of 8 cases on `main`; after the change it passes 8 of 8.

## 2. Can people who only read claims see claimant PII?

No. `claims_reader` has no privilege on schema `claims` and reads only the
`claims_api` views. In those views, claimant name, tax id, date of birth,
phone, address and bank account are masked unless the caller is a member
of `claims_adjuster`. The same query run as both roles shows the
difference cell by cell (`./run.sh compare`): 16 rows per role, 6 PII
columns, 90 cells differ. The other 6 cells are phones the corpus does not
have. The row audit stores PII columns as `[redacted]`.

Proof: `tests/test_access.sql` (S1–S3, P1–P7).

## 3. Do we keep data longer than we are allowed to?

Not in the two databases, once the purges in
[RETENTION-POLICY.md](RETENTION-POLICY.md) run on a schedule. Rule RA-1 keeps
rate audit rows seven years after the later of the rate's end date and the
last ledger period that used it, and never purges a rate that is still
open. Rule CP-1 clears claimant PII once every claim the claimant has is
closed, with no legal hold, and `retention_years` (default 7, set per state
with `loss_state`) have passed since the later of closure and the last
payment. Both purges run as dry runs by default and log every run.

One store remains open: the BizTalk assignment archive on `\\CLAIMS-FS01`
keeps full assignment requests, with claimant names, for seven years from
the request date. Neither purge reaches it, and the policy names it with
an owner action.

Proof: `run_retention_tests.sql` (R1–R5) and `tests/test_retention.sql` (C1–C15).

## Regulatory frame

We use 23 NYCRR Part 500 as the frame because it is the only one of the
three that names both controls the examiner is asking about. Section 500.6(a)
requires audit trails that can reconstruct material financial
transactions, and 500.6(b) requires those records to be kept for at least
five years. Rate changes drive commission payments, and RA-1's seven
years, counted from the last payment period, is longer than that minimum.
Section 500.13, now titled "Asset management and data retention
requirements", requires in 500.13(b) policies and procedures for the
secure, periodic disposal of nonpublic information that is no longer
needed for business operations. That subsection carries exceptions for
information the law requires to be kept and for information that cannot
reasonably be disposed of. CP-1 is that procedure, and its legal-hold skip
covers the first exception. Part 500 binds the carrier only if it holds a
New York licence, and nothing in the estate shows one: losses are in RI,
NH, CT and ME, and the agents hold TX licences. Without a New York licence,
the binding rules are the state insurance data security laws modelled on
the NAIC Insurance Data Security Model Law (#668). That model law was built
on Part 500 and asks for an information security program that covers
retention and disposal of nonpublic information. Its statutory wording and
adoption differ by state, which is one more reason CP-1 takes the period
and the state as parameters. GLBA is the floor under both. Section 501(b)
(15 U.S.C. 6801(b)) requires safeguards for customer information, and
section 505(a)(6) leaves their enforcement for insurers to state insurance
authorities. GLBA sets no audit-trail content and no retention schedule
of its own, so it cannot answer the examiner's first and third questions
by itself.

What this report does not claim: that the carrier is licensed in New York,
or which states have adopted #668 and in what form. Compliance counsel
should confirm both before the frame is cited to an examiner.

## Evidence index

| Evidence | Where |
|---|---|
| Rate audit, pinned before the trigger (7/8 FAIL on `main`) | compliance-kit PR body, `run_audit_tests.sql` |
| Commission Pay full suite: 22 existing + 10 audit + 11 retention cases | `make insurance-test NS=<ns>` |
| PostgreSQL kit self-test, 13 cases | `shared/compliance-kit/run-pg-tests.sh` |
| Claims access (11) and retention (15) tests | `./run.sh test` |
| Corpus reconciliation, 40 messages, one row each | `seed/RECONCILIATION.md` |
| Side-by-side, same query as both roles | `./run.sh compare`, PR body |
