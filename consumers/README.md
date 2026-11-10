# Finance warehouse consumer estate

Each consumer is treated as a separate repository owned by its team, even
though these projects share this monorepo. The estate spans JVM services,
Python and Ruby applications, a LookML semantic model, a finance notebook,
and a BTEQ partner extract. Each reads TDPROD / FIN_DW today.

[registry.yaml](registry.yaml) is the inventory: ownership, service accounts,
entrypoints, cadence, referenced tables and Teradata constructs, root-relative
test commands, workflow paths, and the eventual Snowflake destination/session
tag. Install each consumer's toolchain/dependencies before its test commands;
its README provides setup details. Each consumer workflow installs those
prerequisites and runs the same listed commands.

Contract suites are separate from default unit runs. Set
`WAREHOUSE_CONTRACT_TARGET=teradata-emulator` (the default) to replay the
synthetic recorded Teradata result sets. `TD_EMULATOR_URL` selects an explicit
unsupported endpoint placeholder until the protocol is implemented.
`WAREHOUSE_CONTRACT_TARGET=snowflake` selects a placeholder using
SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE and
SNOWFLAKE_PRIVATE_KEY. Missing credentials skip or fail clearly per stack;
configured remote execution is not implemented yet. Destination is
SFX_D1110_AFTER.COMPAT with a consumer-specific JSON QUERY_TAG.

Unit jobs never require warehouse secrets. Contract jobs are gated on the
presence of SNOWFLAKE_ACCOUNT and SNOWFLAKE_PRIVATE_KEY; once available, the
repository variable CONSUMER_CONTRACT_TARGET chooses the target (default
teradata-emulator). No live warehouse success is implied by replay tests.
