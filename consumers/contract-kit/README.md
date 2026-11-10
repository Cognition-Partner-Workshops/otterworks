# Contract kit
Shared Python bridge for consumers. Uses the Teradata worktree's own
`bteq.Runner` without modifying that worktree. Python 3.10+ is supported.

## Emulator
From the repository root (or an optional separate Teradata worktree):
```sh
make sfx-teradata-up NS=sfx-d1110-consumers ROWS_PER_TABLE=800
```
The seeded business date defaults to 20261109. For this namespace the default
loopback PostgreSQL port is 54902. Startup plus seed/load/chain took about
31 seconds for the initial 400-row setup in the development environment.
A fresh 800-row database took 11.91 seconds with cached dependencies and database image
(daily chain itself 6.513 seconds). The chart of accounts has ten fixed entries;
all other billing entities have at least forty rows.
Use the port calculated for your own NS; do not assume another namespace's port.

From the consumers repository root:
```sh
python3 -m venv /path/to/contract-venv
/path/to/contract-venv/bin/pip install -r consumers/contract-kit/requirements-dev.txt
export TD_EMULATOR_HOME=/home/ubuntu/sfx/td
export TD_PG_PORT=54902
export CONTRACT_KIT_PYTHON=/path/to/contract-venv/bin/python
echo "SEL CUSTOMER_ID FROM SFX_BILLING.CUSTOMER_ACCOUNT" | "$CONTRACT_KIT_PYTHON" consumers/contract-kit/bridge.py
"$CONTRACT_KIT_PYTHON" -m pytest consumers/contract-kit
```
Connection settings are the Runner's TD_PG_DSN or TD_PG_HOST/PORT/DB/USER/PASSWORD
variables; defaults are localhost, 5432, teradata, postgres, empty password.
By default, the runtime is warehouse/teradata in the repository containing this
bridge. TD_EMULATOR_HOME overrides that root, for example for a separate worktree.
If neither location contains the runtime, execution fails. No silent replay fallback.

The bridge reads SQL from stdin or --sql-file and prints only JSON to stdout:
columns are uppercase labels; rows contain decimals as strings and ISO dates.
Runner diagnostics are captured and emitted on stderr on failure.
Bind parameters to SQL literals in each client before invoking this process:
validate integers, and double embedded single quotes in string literals.
Do not interpolate untrusted identifiers. Each client may implement replay
locally, so replay requires neither Python nor PostgreSQL.

## Targets and recording
--target teradata-emulator is the live default.
--target snowflake-semantics uses the same translation and database, with
text column expressions collated C and case-insensitive LIKE translation
disabled. This changes comparison semantics only within this bridge, not the
database's schema, data or the upstream emulator. This is a comparison probe,
not a general Snowflake SQL engine.

Add --query NAME --record path/to/contract/recorded/teradata/NAME.json to save
the exact live output in the shared fixture format. Review and update expected
counts/sums/keys independently after an intentional data/query change.
Consumer targets replay and snowflake are dispatched by each consumer; the
latter remains an explicit placeholder.
