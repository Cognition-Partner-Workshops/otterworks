# AWS legacy portal demo harness

This folder holds the prompts, the run of show and the rehearsal record for the `aws-legacy-portal` demo. In the demo, Devin moves `services/legacy-portal`, a Java 11 and Spring Boot 2.7 monolith, onto one API Gateway HTTP API, one Lambda function per bounded context and Aurora Serverless v2 PostgreSQL, and proves each port against responses recorded from the Java service. The Java service never runs in AWS.

## Contents

| File | Purpose |
|---|---|
| `prompts.md` | Parent, child, steer line and verify prompts |
| `run-of-show.md` | Presenter steps for the AWS persona in Partner Demo - ViewOnly |
| `rehearsal.md` | Measured rehearsal with timings, capacity and cost |
| `rehearsal/<token>/` | The four transcripts of the rehearsal |

## Recorded corpus

`services/legacy-portal/parity/` holds `requests.json` (95 ordered, stateful cases in the contexts `common`, `announcements`, `preferences` and `feedback`) and `java-reference.json` (the Java responses), copied byte for byte from the branch of pull request 1761. `SHA256SUMS` carries their checksums, and `replay.py` checks them before every replay and refuses to run on a mismatch.

```bash
cd services/legacy-portal/parity && sha256sum -c SHA256SUMS
python3 replay.py --base <api url> --context feedback --stage first --out /tmp/replay
```

`replay.py` is adapted from `run_parity.py` on that branch. The Java side is always the recording. It compares status code, media type and body, replaces wall-clock timestamps with a placeholder naming their format, and writes `<context>.json` per context and a `SUMMARY.md` table. Stage `first` stops each context at its first divergence and prints the diff. Stage `full` runs every case.

## Terraform root

`infrastructure/terraform/legacy-portal-serverless/` takes `run_token` as its one required variable and keeps one state object per token under `otterworks/legacy-portal-serverless/<token>/terraform.tfstate` in bucket `otterworks-terraform-state`. Every resource carries the tags `demo=legacy-portal-serverless`, `run_token=<token>`, `RunToken=<token>`, `Expires=<date>` and `ManagedBy=terraform`, and every name starts with the token.

| Resource | Notes |
|---|---|
| `aws_apigatewayv2_api` | One HTTP API, stage `$default` with JSON access logs and throttling at 100 requests per second, burst 200 |
| `aws_apigatewayv2_route` | `ANY <prefix>` and `ANY <prefix>/{proxy+}` per context, and `$default` to the announcements function for the common cases |
| `aws_lambda_function` | `<token>-announcements`, `<token>-preferences`, `<token>-feedback`, placeholder handler answering 501 |
| `aws_rds_cluster` | Aurora PostgreSQL 16.13, Serverless v2 at 0.5 to 4 ACU (set `aurora_min_acu = 0` to let it pause after 600 idle seconds), Data API on |
| `aws_db_subnet_group` | The two private subnets of VPC `otterworks-dev` |
| `aws_security_group` | No inbound rules, because the functions use the Data API |
| Master secret | Created and rotated by RDS (`manage_master_user_password`), so the password is never in Terraform state; RDS deletes it with the cluster |
| `aws_cloudwatch_log_group` | One per function and one for the API access logs |
| `aws_iam_role` | `<token>-lambda`, execution role limited to its log groups, the cluster and the secret |
| `aws_iam_policy` | `<token>-builder`, attached to `devin-cw-builder` |
| `terraform_data.schema` | Runs `apply-schema.sh`, which sends `schema.sql` through the Data API |

`schema.sql` is what Hibernate creates for the Java service. It was taken from `pg_dump --schema-only` of the Java service running locally in Docker against PostgreSQL 15 with the `postgres` profile, and a second database built from `schema.sql` produced an identical dump. The sequence names (`announcement_id_seq`, `feedback_id_seq`) are the ones Hibernate uses, so the sequential ids in the corpus hold.

The functions are created with a Python placeholder so the stack can be applied before any port exists. Terraform ignores later changes to code, runtime, handler and memory, so a child session can deploy its Java handler with `update-function-code` and `update-function-configuration` and a later `lp-up` leaves it in place.

## Builder policy

The policy `<token>-builder` is the diff the run makes to `devin-cw-builder`: one new managed policy attached next to `ReadOnlyAccess` and the existing inline policy. The rehearsal transcript `rehearsal/lp-20261005-rh/up.log` shows it in the Terraform plan.

| Statement | Actions | Scope |
|---|---|---|
| `LambdaRunFunctions` | Get, invoke, update code and configuration, publish versions | Functions named `<token>-*` and tagged `run_token=<token>` |
| `HttpApiOfRun` | `apigateway:GET`, `PATCH`, `POST`, `PUT` | The run's API id and its routes, integrations and stages |
| `DataApiOnRunCluster` | `rds-data` statements and transactions | The run's cluster, tagged `run_token=<token>` |
| `ReadRunDbSecret` | `GetSecretValue`, `DescribeSecret` | The run's secret, tagged `run_token=<token>` |
| `ReadRunLogs` | Filter, get, describe, query and live tail | The run's log groups, tagged `run_token=<token>` |

The policy grants no `iam:PassRole`, so a session cannot change a function's role. The HTTP API statement is scoped by API id, because API Gateway does not evaluate the parent API's tags on requests to its routes and integrations.

## Make targets

Each target writes a transcript to `.demo/legacy-portal/<token>/<target>-<UTC time>.log`, with the account number replaced by `<account>`. `lp-up` and `lp-down` need credentials that can create IAM, RDS and Lambda resources. The other targets run under the builder role.

| Target | Effect |
|---|---|
| `make lp-up RUN=<token>` | `terraform plan` and `apply` for the token, then the outputs and the wall-clock time |
| `make lp-replay RUN=<token> CTX=<context or all> STAGE=first` | Checksum check, then `replay.py` against the run's API URL, with evidence in `.demo/legacy-portal/<token>/replay-*` |
| `make lp-status` | Resources tagged `demo=legacy-portal-serverless` counted by run token and service, and with `RUN=<token>` the outputs, cluster capacity and function runtimes |
| `make lp-reset RUN=<token> CTX=<context or all>` | Truncates the context tables and restarts their id sequences, which is the seeded state the corpus expects |
| `make lp-down RUN=<token>` | `terraform destroy` for the token and the wall-clock time |
| `make lp-verify-clean RUN=<token>` | Resource Groups Tagging API in every region for `run_token` and `RunToken`, then direct lookups of the IAM role and policy, cluster, API, functions, secret and log groups; exits 1 unless everything is gone |

The corpus is stateful within a context, so run `lp-reset` for a context before each replay of it. A reset of one context leaves the other two alone, so the three children can replay at the same time.

## EC2 before state

`infrastructure/terraform/legacy-portal-ec2/` runs the Java monolith on one EC2 host, so a later session can move it to Lambda while the Java service answers live traffic. The root follows the same conventions as the serverless one: `run_token` is the one required variable (`lp-ec2-<yyyymmdd>-<xx>`), one state object per token under `otterworks/legacy-portal-ec2/<token>/terraform.tfstate` in the same bucket, and the tags `demo=legacy-portal-ec2`, `run_token`, `RunToken`, `Expires` and `ManagedBy=terraform` on every resource.

| Resource | Notes |
|---|---|
| `aws_instance` | One `t3.small` Amazon Linux 2023 host in a public subnet (the VPC has no NAT gateway), IMDSv2 required, replaced when user data changes |
| `aws_security_group` (instance) | Admits only the ALB on port 8095, egress open for dnf, SSM, S3 and CloudWatch; no SSH key pair, so access is `aws ssm start-session --target <id>` |
| `aws_security_group` (alb) | HTTP 80 from anywhere |
| `aws_iam_role` and instance profile | AmazonSSMManagedInstanceCore and CloudWatchAgentServerPolicy, plus read on the artifact bucket |
| `aws_s3_bucket` and object | `<token>-artifacts`, public access blocked, holds the fat jar that `lp-ec2-up` builds with `mvn -q -DskipTests package` |
| `aws_lb` with target group and listener | Internet-facing, HTTP only, health check on `/health` |
| `aws_cloudwatch_log_group` | `/otterworks/legacy-portal-ec2/<token>/app`, 7-day retention |

User data installs Amazon Corretto 11 and PostgreSQL 15, creates the database, the login and the three context schemas, downloads the jar, writes the systemd unit with the `postgres` datasource and starts the service. The database lives on the instance on purpose. The before state runs its own PostgreSQL next to the app, with no RDS, no alarms and no autoscaling.

The targets mirror the serverless ones and run `scripts/lp-ec2.sh`, with transcripts in the same `.demo/legacy-portal/<token>/` folder. `Expires` defaults to 72 hours from apply.

| Target | Effect |
|---|---|
| `make lp-ec2-up RUN=<token>` | Build the jar, `terraform plan` and `apply`, then poll target health until healthy |
| `make lp-ec2-status` | EC2 runs by tag; with `RUN=<token>` also the outputs, the instance, the target health and `GET /health` |
| `make lp-ec2-replay RUN=<token>` | Checksum check, then `replay.py` at stage `full` against the ALB URL |
| `make lp-ec2-down RUN=<token>` | `terraform destroy` |
| `make lp-ec2-verify-clean RUN=<token>` | Tagging API in every region for `run_token` and `RunToken`, then lookups of the IAM role and profile, the ALB and target group, the bucket and the log group; exits 1 unless everything is gone |

The recorded corpus is stateful, so one `lp-ec2-replay` fills the tables; a fresh run's database is the seeded state. The live run `lp-ec2-20261006-b1` (Expires `2026-10-09`) is the demo's starting point: instance `i-071dd05b8b26d8f4f` behind `http://lp-ec2-20261006-b1-2053486169.us-east-1.elb.amazonaws.com`, replayed at 95 of 95 identical.

## Known limits

The placeholder handlers run on Python 3.12 while the demo record asks for Java functions, so each child sets the Java runtime when it deploys its port.

The demo record also asks for a budget alarm by run token. This root does not create one, because a budget filtered by tag needs the `RunToken` cost allocation tag activated in the billing account first.

CloudTrail event history shows the management calls, such as `UpdateFunctionCode` and `UpdateFunctionConfiguration`. Lambda invocations and Data API statements are data events and appear only in a trail that records data events.

The log groups, the secret and the function environment use AWS-managed encryption keys, and X-Ray tracing is off. The run lives for hours and holds no customer data, so the Terraform marks those Semgrep rules with `nosemgrep` instead of adding a KMS key and a tracing policy to every run.
