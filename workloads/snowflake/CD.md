# Snowflake continuous delivery

The `snowflake-cd` workflow deploys `doc_usage_dashboard`, `doc_search_api`, and
`churn_model` on pushes to `demo-stack-snowflake`. Same-repository pull requests
run a dry plan only; manual dispatch supports `dry-run`, `deploy`, and
`rollback`. The runner invokes `cd_deploy.sh`, which is also the shared entry
point for a controlled session run.

## Credentials and phases

The workflow expects `SFNFR_ACCOUNT`, `SFNFR_USER`, `SFNFR_ROLE`,
`SFNFR_PRIVATE_KEY`, and `SFNFR_SVC_DOC_USAGE_PRIVATE_KEY`. Keys are written to
restrictive temporary files and removed in an always-run cleanup step. Builder
and service-user keys are used separately. CI sets `SF_PHASE=runtime`; runtime
query tags include the deployed commit and run ID, never a session URL. Local
development defaults to `SF_PHASE=dev`, where `SESSION_URL` is required by the
attribution contract (the pipeline retains its existing default unless
`SESSION_URL` is overridden).

## Dry-run and audit

`cd_deploy.sh --dry-run` runs both migration passes in schemachange dry-run
mode, compiles (never builds) dbt, renders task and Streamlit DDL without
executing it, calculates the rollback target, and prints a provenance diff
without writing provenance. It skips bootstrap DDL. Finally it checks query
history for every run ID and fails if any query type is not read-only. The
machine-readable `query_ids.json` result groups query IDs by step and includes
the commit and run IDs; the full workflow uploads it as an artifact.

## Deploy, rollback, and provenance

Deploy runs attribution lint/tests, forward-only migrations, dbt build/tests,
task and Streamlit deployment, then updates and validates provenance. Failed
dbt data tests stay failures. Rollback redeploys dbt, task, and Streamlit
artifacts from the selected earlier source commit; it does not reverse
migrations. Automatic rollback is attempted only after migrations succeed and
the deployment reaches dbt.

Provenance records the source commit and inventory of supported Snowflake
objects. Objects deployed by the run get a UTC timestamp and commit;
unrecorded inventory objects are added, and previously deployed objects
missing from Snowflake are marked `dropped` with a warning. Resource-monitor
records and usage fields are left untouched; usage stays `pending` until
reported by Snowflake.

The workflow needs Actions secrets with the names above to deploy. Without
them, its fail-fast check stops before any Snowflake operation. A local
`cd_deploy.sh --dry-run` uses the same plan logic but never performs a deploy.
