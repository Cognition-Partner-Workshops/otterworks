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

## Parity levels

L1 compares row counts. L2 compares a profile of every column (nulls, distinct values, min, max, sum). L3 hashes each row by business key and reports the match percentage. L4 samples up to 25 differing rows and shows the column values from each engine. Values are canonicalized before hashing (numbers without trailing zeros, timestamps to milliseconds, NULL as `\N`), and strings keep trailing blanks unless the manifest sets `rtrim: true` for that object.

Conversion rules and the completion standard live in `.agents/skills/tsql-to-snowflake-rules/SKILL.md`.
