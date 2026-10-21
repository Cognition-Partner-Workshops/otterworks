---
name: tsql-to-snowflake-rules
description: Conversion rules for moving T-SQL from a dedicated SQL pool (or SQL Server) to Snowflake, and how to prove each object with the warehouse-parity harness. Read before converting a procedure, function, view, mapping override or load-script block, and append a rule whenever a parity run teaches you something the list does not already say.
---

# T-SQL to Snowflake conversion rules

Each rule has an ID, the T-SQL pattern, the Snowflake form, and the parity level that catches a mistake. Cite rules by ID in commit messages and on the wave board (`python -m wp board set <object> --rules-cited R2,R7`).

## Proving an object

Run everything from `warehouse-parity/` with the manifest the estate ships (`--manifest` or `WP_MANIFEST`).

1. `python -m wp legacy-up` starts SQL Server 2022 in Docker and loads the frozen window.
2. `python -m wp deploy --engine snowflake <converted file>` compiles the converted object.
3. `python -m wp parity <object> --label first-run` runs the legacy object and the converted one on the same frozen input and writes `evidence/<object>/first-run.md`.
4. Fix, rerun with a new label, and keep every report. An object is green only when L1 counts, L2 profiles, L3 row hashes and L4 samples all match. A difference you will not fix is amber: write the business question on the board (`--decision-question`) and leave `--readiness not_ready`.

Never change the frozen input, the legacy object or the comparison query to get a match.

## Base rules

| ID | T-SQL | Snowflake | Caught at |
|---|---|---|---|
| R1 | `SELECT TOP n ... ORDER BY` | `LIMIT n`, or `QUALIFY ROW_NUMBER() OVER (...) = 1` inside a join; correlated `TOP 1` subqueries are not supported | compile |
| R2 | `#temp` tables | `CREATE OR REPLACE TEMPORARY TABLE`, dropped at the end of the procedure | compile |
| R3 | `BEGIN TRY ... END TRY BEGIN CATCH ... THROW` | `EXCEPTION WHEN OTHER THEN ... RAISE;` with `SQLERRM` for the message | runtime |
| R4 | `sp_executesql @sql, N'@p ...', @p = ...` | `EXECUTE IMMEDIATE :sql USING (var, ...)` with `?` placeholders | runtime |
| R5 | `DECLARE c CURSOR ... FETCH NEXT ... @@FETCH_STATUS` | `FOR rec IN c DO ... END FOR;` | compile |
| R6 | `GETDATE()` / `SYSUTCDATETIME()` in defaults | `SYSDATE()` on a `TIMESTAMP_NTZ` column (session time zone does not apply) | L2 |

## Rules learned in parity runs

Append below, newest last, in the same table shape. Give the object and evidence report that taught the rule.

| ID | T-SQL | Snowflake | Caught at | Learned from |
|---|---|---|---|---|
| R10 | `=` joins, `WHERE` filters and `MERGE ... ON` on code columns (producer, policy, region codes) under the default case-insensitive collation | Compare `UPPER(a) = UPPER(b)` on both sides and keep the source value in the output; Snowflake string comparison is case-sensitive, so mixed-case feed codes silently miss their dimension rows (34 of 82 feed rows matched without it) | L3 | dw.usp_build_producer_scorecard (`evidence/dw_usp_build_producer_scorecard/run-1.md`) |
| R11 | `ORDER BY col DESC` on a nullable column inside `TOP 1` or `ROW_NUMBER()` | Add `NULLS LAST`: SQL Server sorts NULL lowest, Snowflake puts NULL first on `DESC`, so the NULL-dated row wins (12 producers picked the `Provisional` tier without it) | L3 | dw.usp_build_producer_scorecard (`evidence/dw_usp_build_producer_scorecard/run-1.md`) |
| R12 | `SET @rc = @@ROWCOUNT` after `sp_executesql` or `MERGE` | Assign `rc := SQLROWCOUNT;` as the very next statement after the DML or `EXECUTE IMMEDIATE`, then use `:rc`; any later INSERT (for example the log row) resets `SQLROWCOUNT` | L3 | dw.usp_build_producer_scorecard (`evidence/dw_usp_build_producer_scorecard/run-1.md`) |
| R13 | Dedicated pool table options `WITH (DISTRIBUTION = ..., HEAP / CLUSTERED COLUMNSTORE INDEX)`, including on `#temp` tables | Drop the clause entirely; Snowflake rejects it at compile | compile | dw.usp_build_producer_scorecard (`evidence/dw_usp_build_producer_scorecard/run-1.md`) |
| R14 | Cursor whose query reads procedure parameters (`WHERE @p IS NULL OR ...`) | Assign the query to a `RESULTSET` (`rs := (SELECT ... :p ...)`) and loop `LET c CURSOR FOR rs; FOR rec IN c DO`; a `FOR` loop cannot `OPEN ... USING` binds | compile | dw.usp_build_producer_scorecard (`evidence/dw_usp_build_producer_scorecard/run-1.md`) |
| R15 | `GROUP BY` on a code column under the default case-insensitive collation (p1003 and P1003 in the same group) | Group by `UPPER(col)` and emit one source spelling with `MIN_BY(col, <load-order id>)`. SQL Server does not define which spelling it returns for such a group, so the lowest-id spelling is a deliberate, deterministic choice rather than a copy of legacy; check that the frozen window has no such group, or get the choice agreed. Grouping the raw value splits the group and a case-insensitive `MERGE ... ON` then matches two source rows to one target | L3 | dw.usp_build_producer_scorecard (`evidence/dw_usp_build_producer_scorecard/fixture-mixed-case-after.md`) |
| R30 | `CAST(varchar_col AS DATE)` where the column holds `''` (SQL Server silently returns `1900-01-01`) | `NULLIF(col, '')::DATE` (not `TRY_CAST`, which also hides malformed dates); plain `CAST('' AS DATE)` fails with `Date '' is not recognized`. Do not reproduce the `1900-01-01` sentinel; raise it as a business decision | runtime, then L2/L3 | m_load_claim_feed, `evidence/m_load_claim_feed/run-1.md` |
| R31 | Mixed-case table name such as `dw.ClaimStatusRef` (case-insensitive on SQL Server) | Quote it exactly as the Snowflake DDL created it, `DW."ClaimStatusRef"`, in every override; unquoted resolves to `DW.CLAIMSTATUSREF` and fails | compile | m_load_claim_feed, `evidence/m_load_claim_feed/run-1.md` |
