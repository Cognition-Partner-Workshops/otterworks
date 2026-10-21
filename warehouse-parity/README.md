# warehouse-parity

A harness for proving that a converted warehouse object returns the same data on Snowflake as the legacy object returns on SQL Server, on the same frozen input. SQL Server 2022 Developer runs locally in Docker; Snowflake is reached with key-pair auth.

## Setup

```bash
pip install -r warehouse-parity/requirements.txt
export WP_SF_ACCOUNT=... WP_SF_USER=... WP_SF_ROLE=... WP_SF_WAREHOUSE=... WP_SF_DATABASE=...
export WP_SF_PRIVATE_KEY="$(cat path/to/key.p8)"
export WP_MANIFEST=path/to/estate/manifest.yaml   # optional; otherwise the first */azure-synapse/manifest.yaml in the repo
cd warehouse-parity
python -m wp legacy-up          # SQL Server 2022 in Docker, frozen window loaded
python -m wp objects --wave 1   # what the manifest says is in scope
```

## Commands

| Command | Use |
|---|---|
| `python -m wp load --engine snowflake` | Recreate the first-pass tables and load the frozen window into Snowflake |
| `python -m wp deploy --engine snowflake file.sql` | Compile a converted object |
| `python -m wp parity <object> --label <label>` | Run both engines, compare L1 to L4, write `evidence/<object>/<label>.md` and `.json`, update the board |
| `python -m wp iics --engine snowflake mapping.json` | Run the SQL inside a mapping export (pre-SQL, source override, lookup, target, post-SQL) and export each result set |
| `python -m wp sql --engine sqlserver "select ..."` | One query on one engine |
| `python -m wp board show` / `set` / `rollup` | Read and update the wave board kept in Snowflake (`PARITY.BOARD`) |
| `python -m wp board serve --port 8765` | Board page, plus `/report?engine=sqlserver` and `/report?engine=snowflake` for the load-script dashboard |

## Schema prefix (isolated runs)

Set `WP_SF_SCHEMA_PREFIX` to run every Snowflake action (`load`, `deploy`, `parity`, `iics`, `board`, `sql`) against prefixed schemas, so a second run never touches the unprefixed ones:

```bash
export WP_SF_SCHEMA_PREFIX=MIG_   # DW -> MIG_DW, STG -> MIG_STG, AUDIT -> MIG_AUDIT, PARITY -> MIG_PARITY
```

- Snowflake side only. The connection's default schema becomes `MIG_DW`, the board lives in `MIG_PARITY.BOARD`, and the four schema names are renamed wherever a statement uses them as a schema: a qualifier (`dw.claim_fact`, `DW."ClaimStatusRef"`, `db.dw.t`, any case) or the name after `SCHEMA` (`CREATE SCHEMA IF NOT EXISTS DW`). The same mechanical rename is applied to every statement (DDL files, manifest `run`/`compare` SQL, mapping and load-script SQL, board SQL); nothing else in the statement changes. SQL Server statements are never touched.
- Not renamed: string literals, comments, `column.dw`-style member access, and quoted lower-case names such as `"dw"`. Dynamic SQL that names a schema inside a string literal therefore still points at the unprefixed schema; the engine prints `warning: string literal names unprefixed schema ...` when it sends such a statement (the first-pass `dw.usp_build_producer_scorecard` does this). Converted code should leave schemas out of dynamic SQL or build them from the current schema.
- Unset or empty = today's behaviour. The value must be a plain identifier prefix.

Check what would be sent before touching Snowflake with `--dry-run LOG` (or `WP_DRY_RUN=LOG`): neither engine is contacted, every statement is appended to `LOG` as JSON lines, queries return no rows and `parity` skips the comparison. `python -m wp dry-run-report LOG` lists the harness schemas each engine's statements name and exits non-zero if an unprefixed one was sent to Snowflake while the prefix is set.

```bash
WP_SF_SCHEMA_PREFIX=MIG_ python -m wp --dry-run /tmp/wp.jsonl load --engine snowflake
WP_SF_SCHEMA_PREFIX=MIG_ python -m wp --dry-run /tmp/wp.jsonl parity dw.v_claim_audit
WP_SF_SCHEMA_PREFIX=MIG_ python -m wp dry-run-report /tmp/wp.jsonl
```

Unit tests: `cd warehouse-parity && python -m pytest tests`.

## Parity levels

L1 compares row counts. L2 compares a profile of every column (count, nulls, distinct values, min, max, sum, and min and max length for strings). L3 hashes each row by business key and reports the match percentage. L4 samples up to 25 differing rows and shows the column values from each engine. Values are canonicalized before hashing (numbers without trailing zeros, timestamps to milliseconds, NULL as `\N`), and strings keep trailing blanks unless the manifest sets `rtrim: true` for that object.

Conversion rules and the completion standard live in `.agents/skills/tsql-to-snowflake-rules/SKILL.md`.
