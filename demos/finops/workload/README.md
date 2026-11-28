# Local settings comparison

Run from the repository root, with the dev values under test in the environment:

```sh
docker compose -f demos/finops/compose.yaml run --rm workload \
  --root-volume-gib "$ROOT_GIB" --app-retention-days "$APP_DAYS" --audit-retention-days "$AUDIT_DAYS"
```

For a direct Python run, use `python3 demos/finops/workload/compare.py` with the same arguments. Each run starts and stops a loopback-only HTTP server and uses the same 100 request bodies. Match the workload hash before comparing results.

The disk model reserves 27 GiB for the system, with a varying scratch allocation per request. An allocation above the configured capacity returns HTTP 507. The JSON reports measured loopback p95 for reference and modeled p95 for the gate. The workload does not benchmark a real node, mount an EBS volume or exercise CloudWatch's expiry delay.

The provider-free Terraform module under `workload/plan/` compares settings without talking to AWS. Use an external temporary state file for the disposable baseline:

```sh
PLAN=demos/finops/workload/plan
terraform -chdir="$PLAN" init -backend=false
terraform -chdir="$PLAN" apply -auto-approve -state="$FINOPS_LOCAL_STATE" \
  -var="root_volume_gib=$BASE_ROOT_GIB" -var="app_retention_days=$BASE_APP_DAYS"
terraform -chdir="$PLAN" plan -state="$FINOPS_LOCAL_STATE" \
  -var="root_volume_gib=$CANDIDATE_ROOT_GIB" -var="app_retention_days=$CANDIDATE_APP_DAYS"
```

The apply records the baseline in local test state only. Audit retention is fixed and unavailable as a candidate input. Remove the local state and backup after the comparison.
