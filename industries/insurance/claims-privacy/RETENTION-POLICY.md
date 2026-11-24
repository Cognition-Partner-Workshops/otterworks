# Retention policy: commission rate audit trail and claimant PII

Status: written policy for the stores named in [ESTATE.md](ESTATE.md). The
two purge procedures below carry it out. Each runs as a dry run unless
the caller passes `dry_run => false`. Every call, dry or real, writes one
`retention_run` row per table it touches, so the purge leaves its own
record.

## RA-1  Commission rate audit rows: seven years after the rate stops mattering

| | |
|---|---|
| Store | Oracle `COMMISSION_PAY`: `audit_row_change` rows for `COMMISSION_RATES`; `rate_audit_log` rows with action `RATE_UPSERT` / `RATE_END` |
| Period | `p_retention_years`, default **7**, minimum 7 (lower values are refused, ORA-20910) |
| Clock starts | the **later** of the rate's `effective_to` and the end of the last `commission_ledger.period_month` that used the rate. For a rate deleted outright, the clock starts at its `DELETE` audit row |
| Never purged | while the rate is open (`effective_to IS NULL`); and no audit row is purged until it is itself at least the full period old |
| Procedure | `rate_retention_pkg.purge(p_as_of, p_retention_years, p_dry_run)` → `retention_kit.purge` (policy name `rate-audit-7y`) |
| Test | `services/industry-solutions/insurance/db/tests/run_retention_tests.sql` (R1–R5) |

Why the clock does not start at `logged_at`: rates 1–4 in the seed have been
open since 2024 and `commission_ledger.rate_id` still points at them. A
purge counted from `logged_at` would delete the only record of who set a
rate that is still being paid on. 23 NYCRR 500.6(b) sets a five-year
minimum for records that rebuild financial transactions; seven years
counted from the last payment period stays above that minimum.

`rate_audit_log` has no `rate_id`, so its rows are kept as long as **any**
rate in the same product/agent scope is still within its period. The
`SPLIT_SET` and `COMMISSION_CALC` actions are records about policies, not
rates, and RA-1 does not cover them.

## CP-1  Claimant PII of closed claims: a parameter, default seven years

| | |
|---|---|
| Store | PostgreSQL `claims`: `claims.claimant` PII columns; `claims.payment.payee_name` / `bank_account_masked` where `payee_type = 'CL'`; `claims.assignment.claimant_name` |
| Period | `retention_years`, default **7**, minimum 1. The carrier's own period varies by state, so the purge accepts `loss_state` and can run once per state with that state's period |
| Clock starts | the **later** of `claims.claim.closed_at` and the last `claims.payment.value_date` on the claim (salvage and subrogation credits can be paid after closure) |
| Eligible | a claimant whose claims are **all** `CLOSED`, none on `legal_hold`, and each past its clock plus the period |
| Never purged | `OPEN` and `REOPENED` claims and anything on legal hold |
| Action | NULLIFY: given name, surname, tax id, date of birth, phone, email, street, city, postal code, bank account; payee name and masked account on claimant payees; claimant name on assignments. The claim, payment lines, amounts, dates and causes stay, and so does the loss state. `pii_purged_at` is stamped |
| Procedure | `claims.purge_closed_claim_pii(as_of, retention_years, dry_run, loss_state)` → `compliance.purge` (policy name `claims-pii-closed`) |
| Test | `industries/insurance/claims-privacy/tests/test_retention.sql` (C1–C15) |

The row audit on the claims tables stores PII columns as `[redacted]`, so
the audit trail of the purge is not a second copy of what the purge removed
(test C14).

## Outside these procedures

| Store | Holds | Why not purged here | Owner action |
|---|---|---|---|
| `\\CLAIMS-FS01\compliance\assignments\%Year%\%MessageID%.xml` (BizTalk send port `sp_Compliance_AssignmentArchive_FILE`) | Full assignment requests, including `ClaimantName`, kept seven years from the request date | It is a file share, not part of either database | Purge it by its own seven-year schedule. Note that this schedule can delete a claimant's assignment file while the claim is still open, or keep it after the database has purged that claimant's PII |
| BizTalk tracking database and message archives | Message bodies in transit | Outside this estate's databases | Out of scope; check the BizTalk tracking purge job |
| Backups of either database | Everything | Restores bring purged PII back | Restore procedure must re-run CP-1 before use |

## Running it

```sql
-- Oracle, as COMMISSION_PAY: dry run as of today, then for real
VARIABLE n NUMBER
EXEC :n := rate_retention_pkg.purge(p_as_of => TRUNC(SYSDATE));
EXEC :n := rate_retention_pkg.purge(p_as_of => TRUNC(SYSDATE), p_dry_run => FALSE);

-- PostgreSQL, as claims_owner: dry run with the default, then a state with a longer period
SELECT claims.purge_closed_claim_pii();
SELECT claims.purge_closed_claim_pii(current_date, 10, false, 'CT');
SELECT * FROM compliance.retention_run ORDER BY run_id DESC;
```
