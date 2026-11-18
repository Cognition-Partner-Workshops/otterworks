# Compliance kit

Reusable database primitives that answer three examiner questions with
evidence: who changed a row and when, who can see personal data, and
whether data is kept past its retention period. The kit is generic: it
names no business table. A module installs it, then applies it to its own
tables.

## Oracle (`oracle/`)

| File | Gives you |
|---|---|
| `audit_kit.sql` | `audit_row_change` (one row per INSERT / UPDATE / DELETE: actor, DB user, OS user, host, program, `via_program`, transaction id, old/new JSON), `audit_kit.install_row_audit(table, key_column)` to generate `TRG_AUD_<table>`, `audit_kit.set_actor` / `clear_actor` so a package can name the business user, `audit_kit.protect_append_only(table)` (UPDATE and DELETE refused, ORA-20901), `audit_purge_gate` |
| `retention_kit.sql` | `retention_run` and `retention_kit.purge(policy, table, predicate, as_of, dry_run DEFAULT TRUE, p_commit DEFAULT TRUE)`: counts, deletes through the purge gate only when `dry_run` is false, and logs every call. It commits the caller's transaction unless `p_commit => FALSE`, so a module can make several purges atomic. Grant EXECUTE on it to nobody: it can open the gate |

A direct statement is attributed to the authenticated session (DB user,
OS user, host) with `via_program = 'SQL'`. A change made inside a package
that called `set_actor(p_actor)` is attributed to `p_actor`, and
`via_program` names the package procedure. The package must clear the
actor on both the success path and the exception path.

Applied in: `services/industry-solutions/insurance/db/oltp/04_rate_audit.sql`
(`commission_rates`, `v_rate_change_history`) and `05_rate_retention.sql`.

## PostgreSQL (`postgres/`)

| File | Gives you |
|---|---|
| `01_masking.sql` | `compliance.mask_keep_last(value, visible)`, `mask_name`, `mask_tax_id`, `mask_phone`, `mask_account`, `mask_date`, `mask_street`. They keep separators and the last *n* letters or digits, matching the claims hub's `PiiMaskingComponent.Mask` |
| `02_audit.sql` | `compliance.audit_row_change` and the trigger function `compliance.audit_row_change_trg(key_column, redacted_column...)`. The actor comes from `SET LOCAL compliance.actor = '...'` and is asserted by the application; `session_user`, client address and application name come from the connection and are the authoritative identity; redacted columns are stored as `[redacted]`; `compliance.append_only_trg()` |
| `03_retention.sql` | `compliance.retention_run` and `compliance.purge(policy, target, predicate, as_of, dry_run DEFAULT true, action 'DELETE' or 'NULLIFY', columns, key_column)` |

Applied in: `industries/insurance/claims-privacy/` on the `demo-insurance`
branch.

## Tests

```sh
shared/compliance-kit/run-pg-tests.sh      # throwaway postgres:16 container, 13 cases, removed on exit
make insurance-test NS=<ns>                # Oracle kit as applied to Commission Pay (audit + retention suites)
```

## Regulatory mapping

| Control | 23 NYCRR Part 500 | Kit piece |
|---|---|---|
| Audit trail that rebuilds material financial transactions, kept ≥ 5 years | 500.6(a)(1), 500.6(b) | `audit_kit`, append-only guard |
| Secure periodic disposal of nonpublic information no longer needed | 500.13(b) (section 500.13, "Asset management and data retention requirements") | `retention_kit.purge`, `compliance.purge` |
| Limit who sees nonpublic information | 500.7 (access privileges) | `compliance.mask_*` behind role-checked views |

Part 500 binds New York-licensed entities. Elsewhere the state laws
modelled on the NAIC Insurance Data Security Model Law (#668) apply, with
GLBA 501(b) as the federal floor. The kit's controls are the same under
each; only the periods differ, which is why every purge takes them as
parameters.
