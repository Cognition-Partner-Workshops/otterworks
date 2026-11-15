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

## Run

```bash
./mvnw verify                       # unit tests
make insurance-up NS=<name>         # builds the jar, starts Oracle + this service
make insurance-down NS=<name>
```

If Maven Central rate-limits you, set `MVNW_REPOURL` and a mirror in your own
`~/.m2/settings.xml`; do not commit either.
