# Users accounts and teams

The Snowflake SQL is ordered from table DDL through FastLoad, BTEQ, PowerCenter and
consumer interfaces. For a live run, render the run database and business date,
upload the date's headerless PSV files to the existing landing stage, and use
the run database and `USERS` as the current schema. Stop on an error and roll
back any open load transaction. Run the team-member PowerCenter SQL separately
when its standalone session is needed.

The group board uses the seeded Teradata emulator as the source. The hook
rebuilds the DuckDB tables from the converted DDL and the original PSV files
using the projections in the Snowflake `COPY INTO` statements. It then executes
the BTEQ replacements and the compatibility view. Both BTEQ rows cover every
table written by their scripts.

The four PowerCenter mappings and sessions use separate parity relations. The
legacy mapping engine runs each exported session with its original writer mode
against the local emulator, then rolls back. DuckDB executes the converted
PowerCenter SQL against its own BTEQ output and also rolls back after taking
the measurements' snapshots. The board calls the legacy team-count macro and
the DuckDB table-macro equivalent of the Snowflake SQL function with the same
date. The legacy date parameter is accepted and unused.

The PowerCenter SQL consumes typed FastLoad stages. The local proof covers the
seeded business date and the resulting relation contents. Malformed raw-record
handling and file-order-dependent duplicate writes require a separate raw
landing contract. The typed load rejects parse errors, and the PowerCenter SQL
fails on duplicate non-null keys rather than choosing an arbitrary row.
