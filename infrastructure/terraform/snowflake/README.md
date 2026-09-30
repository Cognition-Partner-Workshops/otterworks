# infrastructure/terraform/snowflake

External load stage for the Snowflake split target (`s30-after`): the job writes each Parquet batch once to the
tenant's S3 staging prefix and Snowflake reads it from there, so the internal-stage `PUT` (a second upload of
the same bytes) goes away and IAM, not a Snowflake-held copy, is the boundary.

| Resource | Name (defaults) |
| --- | --- |
| `snowflake_storage_integration_aws` | `LDM_S3_INT`, `STORAGE_ALLOWED_LOCATIONS = ('s3://<bucket>/s30-after/')` |
| `aws_iam_role` + inline policy | `otterworks-ldm-s30-after-snowflake`: `s3:ListBucket` on `s30-after/*`, Get/Delete on `s30-after/*`, no Put |
| `snowflake_stage_external_s3` | `OTTERWORKS_LDM_S30_AFTER.STG.LDM_STAGE` (Parquet, `USE_LOGICAL_TYPE`) |
| `snowflake_grant_privileges_to_account_role` | `USAGE` on the stage to `LDM_JOB_S30_AFTER` |

The existing job role `otterworks-ldm-s30-after-job` is not touched: it already writes `s30-after/*`, which is
where the driver puts the batches. The new role is Snowflake's only; it can read and delete (`PURGE`) under the
one prefix and nothing else.

Variables (all defaulted for `s30-after`): `account`, `database`, `bucket`, `prefix`, `region`, plus
`snowflake_user` / `snowflake_role` / `snowflake_warehouse`, `integration_name`, `stage_name`, `job_role`.

## Credentials and state

- Snowflake: `SNOWFLAKE_USER` and `SNOWFLAKE_PAT` from the environment. `tf.sh` exports it as `SNOWFLAKE_TOKEN` (the provider's
  variable) for the terraform process only; it is never a Terraform variable, tfvars entry, argv or backend
  setting. Terraform runs as `LDM_ADMIN`, which needs `CREATE INTEGRATION ON ACCOUNT`
  (`migration/target/snowflake/bootstrap/account.sql`).
- AWS: the ambient demo credentials, account of the tenant bucket.
- State: S3 backend next to demo-aws, `s3://otterworks-terraform-state/otterworks/demo/<token>/snowflake.tfstate`
  (demo-aws uses `.../<token>/terraform.tfstate`). `TF_DATA_DIR` lives under `.demo/<token>/`.

The state holds the integration's `STORAGE_AWS_EXTERNAL_ID`; the `storage_aws_external_id` output is sensitive.

## Apply (two steps)

The IAM trust policy needs `STORAGE_AWS_IAM_USER_ARN` / `STORAGE_AWS_EXTERNAL_ID`, which Snowflake generates when
the integration is created, so the integration goes first:

```sh
cd infrastructure/terraform/snowflake
# 1. integration only (its STORAGE_AWS_ROLE_ARN is the deterministic ARN of the role step 2 creates)
./tf.sh apply -target=snowflake_storage_integration_aws.ldm
./tf.sh output storage_aws_iam_user_arn        # Snowflake's IAM user; the external ID stays in state
# 2. IAM role trusted by that user + external ID, its prefix policy, the external stage and the grant
./tf.sh plan -out=step2.tfplan && ./tf.sh apply step2.tfplan
```

`DESC INTEGRATION LDM_S3_INT` shows the same values. If the integration is ever replaced, re-run step 2 so the trust policy
picks up the new values (the plan shows the trust-policy diff).

If `STG.LDM_STAGE` already exists as the bootstrap's internal stage (`migration/target/snowflake/ddl`), drop it
once before step 2 (`DROP STAGE OTTERWORKS_LDM_S30_AFTER.STG.LDM_STAGE`) - `CREATE STAGE IF NOT EXISTS` in the
bootstrap never converts it, and the stage holds no data between runs.

The manifest opts in with `target.archive.external_stage: true` (`migration/manifests/s30-after.yaml`); without
it the driver keeps the internal-stage `PUT` path.

## Guardrail: exactly one prefix

- `check "single_tenant_prefix"` (plus a `precondition` on the policy) in `main.tf` fails the plan unless the policy's object resources are
  exactly `["arn:aws:s3:::<bucket>/<prefix>*"]`, the `s3:prefix` list condition is exactly `["<prefix>*"]`, and
  the integration's allowed locations are exactly `["s3://<bucket>/<prefix>"]`.
- `terraform test` (`tests/guardrail.tftest.hcl`, mocked providers, no credentials) asserts the same plus: no
  `s3:PutObject`, trust principal is only Snowflake's IAM user, the trust requires the external ID, and a nested
  or empty prefix is rejected by variable validation.

  ```sh
  terraform init -backend=false && terraform test
  ```

- Live proof, `guardrail.sh`: assume the role the way Snowflake does (`sts:ExternalId`), list the own prefix
  (allowed) and `s3://<bucket>/s29-after/` (expects `AccessDenied`). The caller must be trusted for the duration:

  ```sh
  ./tf.sh apply -var "guardrail_principal_arns=[\"$(aws sts get-caller-identity --query Arn --output text)\"]"
  ./guardrail.sh                     # or ./guardrail.sh <other-prefix>/
  ./tf.sh apply                      # drop the extra principal again
  ```

  Snowflake enforces the same boundary on its side: a stage on `LDM_S3_INT` with any URL outside the allowed
  location fails with `003127 ... is not allowed by integration LDM_S3_INT`.

## Live lifecycle test on the external stage

`migration/job/tests/test_snowflake.py` runs the external-stage case only when `LDM_TEST_SNOWFLAKE_EXTERNAL_STAGE`
names an external stage in the scratch database. It is never pointed at `OTTERWORKS_LDM_S30_AFTER`; create a
throwaway one under the tenant prefix as `LDM_ADMIN`, run, drop it:

```sql
CREATE STAGE OTTERWORKS_LDM_LDM_CI.STG.LDM_EXT_STAGE
  URL = 's3://otterworks-ldm-s30-after-<account>/s30-after/_ci/' STORAGE_INTEGRATION = LDM_S3_INT
  FILE_FORMAT = (TYPE = PARQUET USE_LOGICAL_TYPE = TRUE BINARY_AS_TEXT = FALSE);
GRANT USAGE ON STAGE OTTERWORKS_LDM_LDM_CI.STG.LDM_EXT_STAGE TO ROLE LDM_JOB_LDM_CI;
-- LDM_TEST_SNOWFLAKE_EXTERNAL_STAGE=STG.LDM_EXT_STAGE AWS_REGION=us-east-1 pytest tests/test_snowflake.py
DROP STAGE OTTERWORKS_LDM_LDM_CI.STG.LDM_EXT_STAGE;
```

## Cost note: us-east-1 bucket -> us-east-2 warehouse

The bucket is in `us-east-1`, the Snowflake account (and `LDM_WH`) in AWS `us-east-2`, so every `COPY INTO`
reads the batch across regions.

- Rate: AWS bills inter-region transfer at the source only; `USE1-USE2-AWS-Out-Bytes` is **$0.01/GB** (AWS
  price list, `AWSDataTransfer`, N. Virginia -> Ohio; inbound to Ohio is $0.00). Snowflake charges no ingress;
  its own egress fee applies only to unloads/replication out of `us-east-2`, which the load does not do.
- Volume: a full-fixture run selects 800,040 rows (RETNPLCY 40, DOCARCH 180,000, FILEAUD 620,000;
  `migration/source/seed/SEED-SPEC.md`). The live scratch run's `COPY INTO` scanned about 460 B/row (DOCARCH)
  and 200 B/row (FILEAUD) of Parquet at 30-row batches, where the footer dominates; at that upper bound a run is
  about 0.21 GB, i.e. **~$0.002 per run**. Reject bisection re-reads only the failing batch's rows; even ten
  full reruns stay under $0.03. S3 GET requests (one per batch file, $0.0004 per 1,000) are noise.
- Compared with the internal stage: `PUT` already moved the same bytes from the job pod in `us-east-1` to the
  `us-east-2` internal stage (the same $0.01/GB inter-region rate on the EC2 side) on top of the S3 staging
  write; the external stage removes that second upload rather than adding a transfer. Snowflake-side compute is
  unchanged (`COPY INTO` on `LDM_WH` either way).
- Co-locating the bucket in `us-east-2` would make the transfer free but moves it out of the tenant's region;
  at this volume it is not worth it.
