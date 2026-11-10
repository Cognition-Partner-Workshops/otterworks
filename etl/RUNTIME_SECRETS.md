# ETL runtime secrets

`config.ini` contains non-secret settings only. AWS SDK clients use the default
credential chain: attach the existing data-access role through an EC2 instance
profile or IRSA. Do not provision static AWS keys for these jobs.

Apply the standalone stack in `infrastructure/terraform/etl-runtime` with
`runtime_role_name`, `kms_key_arn` (an existing customer-managed key), and optionally
`aws_region` and `secret_name`. The key policy must authorize the runtime role;
the generated role policy restricts decrypt to Secrets Manager and this secret's
encryption context. Keep the existing data-access permissions on that role.
This stack creates only the secret container and read policy, not a secret version:
no credential value enters Terraform code or state.

Using an authorized operator identity, populate one Secrets Manager JSON secret
with nonempty `ETL_DB_PASSWORD` and `ETL_MEILISEARCH_API_KEY` properties. Use the
Secrets Manager console or a secure provisioning process; do not commit values,
pass them on command lines, or create a plaintext `.env` file on the ETL host.
The default secret name is `otterworks/etl/runtime`; export `ETL_SECRET_ID` to
override it. `ETL_CONFIG_PATH` optionally overrides the non-secret config path.

Run `etl/run.sh analytics_daily.py` (likewise for the other four jobs). The wrapper
fetches the JSON via boto3, validates both fields, populates only those environment
variables, then starts the selected job in the same process. Missing fields, invalid
JSON, or AWS access errors stop execution before the job runs. No shell evaluation
of secret contents occurs. Direct job invocation requires the appropriate secret
environment variables to be supplied by the caller.

Revoke the old committed AWS keys and rotate the database password and MeiliSearch
key. Update Secrets Manager and any other consumers together. Removing plaintext
from this branch does not remove it from Git history.
