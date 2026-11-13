# Frozen warehouse input

Requires Python 3.12. Install with `pip install -e '.[dev,snowflake]'`.
Run `pytest` and `ruff check .` locally. Snowflake tests use mocks only.

Set `ORACLE_DSN`, `ORACLE_USER` and `ORACLE_PASSWORD`, then run:

```sh
python -m loader extract --token run42 --tables LEDGER ACCOUNTS --out frozen/run42
python -m loader load --token run42 --manifest frozen/run42/manifest.json --target duckdb --out loaded
python -m loader teardown --token run42 --target duckdb --out loaded
```

Extraction uses one Oracle read-only transaction, writes Parquet plus a versioned
manifest, and refuses to overwrite an existing input directory. The manifest records
row counts, SHA-256 file checksums, column types and expiry. Load validates the files,
row counts and schemas before creating target objects. Freeze the manifest alongside
the files; checksums detect accidental changes. An altered manifest can bypass checksums.
An extraction failure leaves an incomplete directory for inspection. Re-extract to a
new directory. Source objects must stay unchanged during later live-source parity runs.

Numbers retain decimal precision, Oracle DATE retains time, and NULL differs from
empty strings. Unconstrained NUMBER columns derive a decimal type from all source
values. Values needing more than 38 decimal digits and unsupported Oracle types fail
explicitly. Extraction reads one source table into memory. Frozen files need the same
access controls as source data.

Snowflake loads use `--target snowflake` with `SNOWFLAKE_ACCOUNT`,
`SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH`, optional
`SNOWFLAKE_PRIVATE_KEY_PASSPHRASE`, and optionally `SNOWFLAKE_ROLE`.
Set `SNOWFLAKE_RUN_PUBLIC_KEY` to the base64 DER public key for the new service user.
Authentication uses key-pair JWT. The operator role needs account-level privileges
to create databases, warehouses, monitors, roles and users, and sufficient visibility
for account-wide SHOW commands during cleanup.

The default database name is `MIGRATION_<TOKEN>_AFTER`; `--prefix` changes its prefix.
Tokens contain 2-12 lowercase letters/digits and cannot be `main`. Objects carry the
token and expiry in comments; resource monitors carry expiry in their names.
The loader creates an XS warehouse with 60-second auto-suspend and a one-credit
daily monitor with immediate suspension at quota. PUT and COPY use Parquet logical
types. DDL is not transactional: after a failed load, run teardown before retrying.
Teardown suspends active token warehouses, drops the database, warehouse, monitor,
user and role, then reports matching names or token comments. Residue or cleanup
errors produce a nonzero exit. Expiry metadata needs an external cleanup schedule.

The reusable loader has separate CLI and manifest interfaces and performs no source
deletes, preserving the existing Db2 demo's `migration/CONTRACTS.md` interfaces.
