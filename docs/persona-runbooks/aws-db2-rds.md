# AWS migration: Db2 retention history to RDS

Devin runs a staged data migration of the document-retention history (`RETNPLCY`, `DOCARCH`, `FILEAUD`) from a Db2 container into PostgreSQL on the shared RDS instance, through a harness that extracts, loads, validates, purges and reconciles as Kubernetes Jobs. Db2 stays the system of record for every row the validation did not prove.

| Field | Value |
|---|---|
| `runAs` | AWS (`user-094334530455473bb8c587d207307833`) |
| Field Kit | Area `ISV and platform`, Identity `AWS` |
| Delegation shape | Well defined. Five stages, one gate, one report; the human reads the report. |
| Repository | `Cognition-Partner-Workshops/otterworks`, branch `demo-cloud-worker` |
| Tenants | `d24-before` (Db2 serves the history) and `d24-after` (same seed, target `otterworks_d24_after` on RDS, staging under `s3://otterworks-ldm-d24-after-<account>/d24-after/`) |
| Roles | `devin-cw-observer` reads both namespaces; `devin-cw-builder` edits `otterworks-d24-after` only |
| Mode | Normal (the recorded run used Normal mode on request; Fusion works the same) |
| Live time | 13 minutes for the five stages on 2026-10-05, after the tenants were up |

## Preflight, the day before

From a checkout of `demo-cloud-worker` with operator AWS credentials and `kubectl` pointed at `otterworks-dev`.

1. `make demo-verify-clean NS=d24-before` and `make demo-verify-clean NS=d24-after` both exit 0, or `make demo-destroy NS=<token>` first.
2. `make demo-up NS=d24-before TTL=72h` and `make demo-up NS=d24-after TTL=72h`. The Db2 seed of 5.3 million rows takes 20 to 35 minutes per tenant; start both the evening before. Both web tenants answer at `https://t-<token>.otterworks.app`.
3. The shared RDS instance must be `db.t3.small` or larger. On `db.t3.micro` the load stage exhausted connection slots and the instance restarted (RDS events 09:08 to 09:13 UTC on 2026-10-05). Pull request 1811 records the size in Terraform; check `aws rds describe-db-instances --db-instance-identifier otterworks-postgres-dev --query 'DBInstances[0].DBInstanceClass'`.
4. Read `docs/demos/legacy-data-migration.md` sections 1 to 4 and `migration/CONTRACTS.md` for the stage names and exit codes you will see in the session.

## Live

1. Sign in as the AWS persona and start a session on `otterworks` with the prompt in `/home/ubuntu/prompts/aws-native/prompts/aws-migration.md`. It names the two tenants, the two roles and the harness, and asks for the before state, the run, the report and an independent check.
2. Before state, under the observer role: Db2 row counts for the three tables in both tenants, the empty target schema, the empty S3 prefix, both web tenants answering over https.
3. The run, under the builder role: `make demo-migrate NS=d24-after RUN_ID=r$(date -u +%Y%m%d%H%M%S)`. Devin streams the five jobs. Measured durations on 2026-10-05: extract 56 s, load 52 s, validate 3 min 48 s, purge 6 min 58 s, reconcile 12 s.
4. The report, under the observer role: the per-table table of extracted, loaded, validated, purged and failed rows, the reconciliation verdict, and the rows that stay in Db2 with the reason each failed validation.
5. Close on the independent check Devin runs itself: `kubectl get jobs -n otterworks-d24-after` showing every stage `Complete`, the admin dashboard of `d24-after` serving history from PostgreSQL with the deep link to the same document in `d24-before`.

## Expected state after

| Check | Expected |
|---|---|
| Jobs in `otterworks-d24-after` | `ldm-extract`, `ldm-load`, `ldm-validate`, `ldm-purge`, `ldm-reconcile` all `Complete 1/1` |
| Rows left in Db2 after purge | the rows that failed validation, by design 42 on the planted seed; they stay until a human decides |
| Report | copied to `.demo/d24-after/<run id>/` and pasted in the session |
| `main` and `demo-cloud-worker` | untouched; the run writes to the tenant and the report only |

## Reset

The purge stage deletes validated rows from Db2, so running the demo again means rebuilding the after tenant:

```bash
make demo-destroy NS=d24-after
make demo-verify-clean NS=d24-after
make demo-up NS=d24-after TTL=72h       # 20 to 35 minutes for the seed
```

`d24-before` can stay up between runs.

## Fallback

- Load stage fails with connection errors: check the RDS instance class and `FreeableMemory` in CloudWatch; resize to `db.t3.small` and rerun with a new `RUN_ID`. The harness is idempotent per stage.
- Karpenter evicts the Db2 pod during the run: the StatefulSet reschedules it on the static volume; wait for `db2-archive-0` to be ready and rerun the failed stage.
- No time for the live run: open the recorded session and walk the report. It carries every number above.

## Talk track

Devin runs the same five stages a data engineer would, under a role that can only touch the after tenant, and the output is a row-level reconciliation that says which source rows are safe to delete. The 42 rows that stay in Db2 show the rule: a row leaves the source only after validation proves its copy.

## Evidence from the recorded run

| Item | Where |
|---|---|
| Session, AWS, Normal mode | https://partner-workshops.devinenterprise.com/sessions/3be933fc2a404afa9d155ff5f27ea4a0 |
| Jobs, RDS events, memory after resize | `evidence/aws/final-audit-d24-after-migration.txt` |
| RDS resize | `evidence/aws/rds-modify-t3small.json`, pull request https://github.com/Cognition-Partner-Workshops/otterworks/pull/1811 |

## Rerun log

| Date | Who | Session | What the runbook had not said |
|---|---|---|---|
| 2026-10-05 | AWS persona | `3be933fc` | RDS needs `db.t3.small`; added to preflight. The purge cannot be undone, so the reset is a tenant rebuild; added. |
