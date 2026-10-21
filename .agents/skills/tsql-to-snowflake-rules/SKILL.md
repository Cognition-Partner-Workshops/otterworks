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
| R90 | `DATEPART(weekday, x)` (result depends on `@@DATEFIRST`; legacy runs `us_english`, `DATEFIRST 7`, so Sunday = 1 .. Saturday = 7) | `MOD(DAYOFWEEKISO(x), 7) + 1`, also in `GROUP BY`; plain `DAYOFWEEK` follows the `WEEK_START` session parameter (default 0: Sunday = 0 .. Saturday = 6), so every weekday key shifts by one and rows regroup. `DAYOFWEEKISO` ignores `WEEK_START` | L2 / L3 | dw.v_policy_audit, `warehouse-parity/evidence/dw_v_policy_audit/first-pass.md` |
