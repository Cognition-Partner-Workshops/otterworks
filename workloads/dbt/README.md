# dbt pipeline

`run.py` builds the three workloads on their separate attributed Snowflake
connections. `../snowflake/deploy_usage_task.py` deploys the usage workload from a
pushed commit and verifies its hourly native task with a manual execution.

Runtime verification reports both strict query-tag mismatches and mismatches
after a narrow native dbt bootstrap exception. A query is compliant only if its
tag equals the runtime JSON tag, or it is the first statement of its session,
has type `ALTER_SESSION`, and its complete SQL text sets `query_tag` to that
exact runtime tag. Additional statements, different tags, and later tag setters
are not exempt. Session order is checked against session history, including
statements outside the task window or on other warehouses, not just the
warehouse-window result. Missing or truncated history fails closed. Verification
failure suspends the task; successful verification leaves the hourly task active.
The warehouse proof keeps Snowflake's default exclusion of client-generated
statements (such as unrelated Snowsight notification polling); the session-order
lookup includes client-generated statements so they cannot make a later setter
appear to be first.
