# commission-service

Java 21 / Spring Boot 3.3 owner of the Commission Pay rules that used to live in
`COMMISSION_PKG` (`services/industry-solutions/insurance/db/oltp/03_commission_pkg.sql`).

## Strangler route

Callers keep calling `COMMISSION_PKG` with the same signatures. One rule group at a
time, the package body is switched from its PL/SQL rules to a `call_service`
delegate that calls this service over `UTL_HTTP` at `http://commission-service:8000`
(network ACE in `db/setup/02_service_acl.sql`). Groups not yet moved keep running in
Oracle.

| Group | Package members | Endpoint(s) |
|---|---|---|
| rates | `upsert_commission_rate`, `end_commission_rate`, `resolve_rate` | `POST /rates/upsert`, `POST /rates/end`, `GET /rates/resolve` |
| splits | `set_commission_splits` | `POST /policies/{policyId}/splits` |
| calculation | `calculate_policy_commission` | `POST /policies/{policyId}/commission` |

## Wire contract

- DATE values travel as `TO_CHAR(d, 'YYYY-MM-DD HH24:MI:SS')`; NUMBER values travel
  as JSON strings produced by `TO_CHAR(n)` so no precision is lost.
- Success is HTTP 200 with a JSON body. Any rejection is HTTP 422 with
  `{"ora_code": -NNNNN, "message": "..."}` (`common/OraErrorAdvice`); the delegate
  re-raises `-20001..-20999` unchanged with `RAISE_APPLICATION_ERROR`.
- The service owns the transaction of the rule it runs (commit on success, roll back
  on rejection). The delegate mirrors the package's own `COMMIT` / `ROLLBACK` on the
  caller's session for the write procedures; `resolve_rate` never ends a transaction.

## Shared pieces (`common/`)

- `Money` — money is `BigDecimal` scale 2; Oracle `ROUND` is `RoundingMode.HALF_UP`
  (`Money.ORACLE_ROUND`). Every call site names its rounding mode.
- `OracleText` — Oracle's default `TO_CHAR` for numbers and dates, used in messages
  and audit detail.
- `Guards` — `assert_product` (-20004) and `assert_active_agent` (-20002 / -20003).
- `AuditLog` — `log_action` into `rate_audit_log`.
- `RateResolver` — `resolve_rate` for the calculation group. `LegacyPackageRateResolver`
  calls the package until the rates group replaces it.

## Backend switch

`COMMISSION_BACKEND` picks the database and is the only switch: `oracle` (default,
`application-oracle.yml`) or `postgres` (`application-postgres.yml`, PostgreSQL 16 from
`make insurance-pg-up`). It is a Spring profile; exactly one must be active or the
service refuses to start (`common/Backend`). `COMMISSION_DB_URL` and `COMMISSION_DB_USER`
override the profile's datasource. `COMMISSION_DB_PASSWORD` is required and has no
default: it comes from the secret store (Helm `secrets:`, the compose file for the local
fixture), and the service refuses to start without it (`common/DatasourceCredential`).

On `postgres` there is no `COMMISSION_PKG`, so `PostgresRateResolver` runs the
`resolve_rate` query itself (same order, same ORA-20007 text) and the period end is
computed with PostgreSQL date arithmetic. The rest of the calculation group runs
unchanged: `POST /policies/{policyId}/commission` calculates the policy for the period
in Java and writes `commission_ledger` and `rate_audit_log` on PostgreSQL.

## Commission Pay screens (read-only)

| Screen | Path |
|---|---|
| Agent commission statement: policy rows with premium, rate, split, commission and the period total | `/screens/statement?agent=<id>&period=YYYY-MM` |
| Rate history: product, agent, rate, effective from and to; rates used by the period are highlighted | `/screens/rates?agent=<id>&period=YYYY-MM` |

The banner names the backend and the JDBC URL. Each statement row shows the
`rate_audit_log` actor of the calculation that wrote it, so the page says who computed the
number: `COMMISSION_PKG` on Oracle (for example `ledger-run`), or the Java service on
PostgreSQL (the actor passed to `POST /policies/{id}/commission`). The period total is the
exact sum of the rows, added by the page. The pages only read.

```bash
make insurance-up NS=<name> && make insurance-ledger-run NS=<name>
COMMISSION_BACKEND=oracle COMMISSION_DB_URL=jdbc:oracle:thin:@//localhost:<oracle port>/FREEPDB1 \
  java -jar target/commission-service.jar
make insurance-pg-up NS=<name>
COMMISSION_BACKEND=postgres COMMISSION_DB_URL=jdbc:postgresql://localhost:<pg port>/commission \
  java -jar target/commission-service.jar
curl -X POST localhost:8000/policies/1/commission -H 'Content-Type: application/json' \
  -d '{"period_month":"2026-03","actor":"commission-service"}'
```

The ports are per namespace (`INSURANCE_DB_PORT` / `INSURANCE_PG_PORT` in the Makefile).

## Run

```bash
./mvnw verify                       # unit tests
make insurance-up NS=<name>         # builds the jar, starts Oracle + this service
make insurance-down NS=<name>
```

If Maven Central rate-limits you, set `MVNW_REPOURL` and a mirror in your own
`~/.m2/settings.xml`; do not commit either.
