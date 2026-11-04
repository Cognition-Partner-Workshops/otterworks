# Document usage refresh drill

`OPS.WORKLOAD_FRESHNESS` reports each configured source and output table. A refresh is recorded only after the RAW load and dbt build both succeed. The hourly task allows 90 minutes of age before a row is stale; a never-refreshed table is stale.

The CLI connects as the endpoint service user with the workload's runtime OPS role and a `phase=runtime` query tag. Set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_PRIVATE_KEY_FILE` (the service-user key from `SFNFR_SVC_DOC_USAGE_PRIVATE_KEY`), and `SESSION_URL` (for drill notes and switch changes). `deploy_usage_task.py` deployments continue to use the builder credentials.

```bash
python workloads/snowflake/ops.py freshness
python workloads/snowflake/ops.py task-history [--limit 24]
python workloads/snowflake/ops.py fault status
python workloads/snowflake/ops.py fault arm --note "incident drill"
python workloads/snowflake/ops.py run-task --wait
python workloads/snowflake/ops.py fault disarm
python workloads/snowflake/ops.py run-task --wait
```

To reset a drill, disarm `REFRESH_DOC_USAGE_DASHBOARD` and make sure the task is resumed. The fault switch is sticky: every run fails before `LOAD_RAW` until it is disarmed.

## Responder runbook

Check `freshness`, inspect `task-history`, and capture the failed run and error. Fix the cause on a branch, deploy and rerun the task, then check `freshness` again. Do not leave the fault switch armed after a drill.
