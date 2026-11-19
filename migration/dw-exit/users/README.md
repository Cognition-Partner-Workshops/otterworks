# Users Teradata-chain conversion

Stages execute `10_load.sql` → `20_routines.sql` → `30_views.sql`.
`00_tables.sql` declares the kept core and staging tables. The macro's returned
resultset is measured as `SFX_USERS.M_TEAM_COUNTS_OUTPUT`; `10_activity_daily`
also declares `SFX_USERS.USER_ACTIVITY_DAILY`. PowerCenter rows are measured on
their declared output relations, not by executing PowerCenter. Spark conversion
and the four retirement decisions remain deferred.

## Stopped object: APP_USER implicit truncation

The local source chain silently truncates long display names. The BTEQ selects
`DISPLAY_NAME` unchanged (`warehouse/teradata/scripts/users/01_load_users.bteq:6–8`),
but staging declares `VARCHAR(200)` and core declares `VARCHAR(60)`
(`warehouse/teradata/ddl/users/00_tables.sql:7,16`). The emulator executes that
INSERT through `Runner.execute` (`warehouse/teradata/bteq/runner.py:158–169`);
`Runner.translate` inserts a destination-width character cast
(`warehouse/teradata/bteq/runner.py:336–355`). PostgreSQL's explicit cast truncates.

On the sfx1119 local dataset, 100 APP_USER display names differ from staging;
all 100 exactly equal the first 60 characters. For example, user 9000000001 has
78 staging characters and 60 source core characters. The converted SELECT
retains the full display name in DuckDB, whose VARCHAR length is not enforced.
No live Snowflake behavior was measured: preflight remains denied with 002003.

No substring, cast-based truncation, widened destination, or comparison
normalization has been added to hide this discrepancy. APP_USER and its three
declared-output dependents (`01_load_users`, `m_SFX_APP_USER`,
`s_m_SFX_APP_USER`) remain red with measured differences. The source emulator
and target behavior are preserved pending a decision on this newly discovered
side effect; native Teradata behavior has not independently been tested.
