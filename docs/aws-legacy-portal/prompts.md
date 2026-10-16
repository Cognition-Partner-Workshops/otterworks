# Legacy portal session prompts

This file holds the session prompts for the `aws-legacy-portal` demo. Replace `<token>` with the run token (`lp-<yyyymmdd>-<two letters>`, for example `lp-20261005-rh`) and `<session id>` with the Devin session id. The operator applies the Terraform for the token with `make lp-up RUN=<token>` before the call, because the builder role can deploy into a run but cannot create one.

## Rules every session follows

Every session works in the GitHub repository Cognition-Partner-Workshops/otterworks. The orchestrator works on branch `migration/legacy-portal-<token>` cut from `main`, and each child works on `migration/legacy-portal-<context>-<token>` cut from the orchestrator branch. No session pushes to `main` or merges a pull request.

Every AWS call runs under the Devin builder role, assumed with `source <(cloudworker/assume.sh builder devin-<session id>)`, so CloudTrail shows the calls under role session `devin-<session id>`. The run's Terraform attaches policy `<token>-builder` to that role. It allows `lambda:UpdateFunctionCode`, `lambda:UpdateFunctionConfiguration`, `lambda:InvokeFunction` and `lambda:PublishVersion` on functions tagged `run_token=<token>`, the RDS Data API on the run's Aurora cluster, `secretsmanager:GetSecretValue` on the run's database secret, writes to the run's HTTP API, and reads of the run's log groups. Reads elsewhere come from `ReadOnlyAccess`.

A session leaves these files as they are on `main`: everything under `services/legacy-portal/parity/` (`requests.json`, `java-reference.json`, `SHA256SUMS`, `replay.py`), the Terraform root `infrastructure/terraform/legacy-portal-serverless/` with its variables and values, `scripts/lp-serverless.sh`, the `lp-*` targets in the `Makefile`, the Java source in `services/legacy-portal/`, and everything under `cloudworker/`. If the recorded corpus and the port disagree, the port changes.

Each session posts its evidence in the session itself: the replay table printed by `make lp-replay`, the API URL from `make lp-status RUN=<token>`, and the CloudTrail rows for its role session.

## Parent prompt

Run as the architect persona in Fusion mode.

```text
Act as the orchestrator for moving services/legacy-portal in Cognition-Partner-Workshops/otterworks onto managed AWS as run token <token>. Work on branch migration/legacy-portal-<token> cut from main and never push to main or merge anything. Use the builder role for every AWS call: source <(cloudworker/assume.sh builder devin-<session id>). Do not edit services/legacy-portal/parity/, the Terraform root infrastructure/terraform/legacy-portal-serverless/ or its values, scripts/lp-serverless.sh, the lp-* Makefile targets, the Java source in services/legacy-portal/ or anything under cloudworker/.

First run make lp-status RUN=<token> and post the API URL, the three function names and the Aurora capacity. The operator has already applied the Terraform for the token; if lp-status shows no outputs, stop and tell me.

Then start one child session per bounded context in Fusion mode, announcements, user_preferences and feedback, each with the child prompt in docs/aws-legacy-portal/prompts.md and its context filled in. The announcements child also owns the common cases (health, actuator and unknown paths), because the HTTP API sends every route outside the three prefixes to the announcements function.

Each child ports its context to the Lambda function Terraform created for it, deploys it, resets its table, runs the first-stage replay, posts the result and pauses before fixing anything. When all three have reported, post one table with the first divergence and the different case count per context, and wait for my instruction.

When I tell a child to fix its adapter, let it fix and run its full replay. After every child shows its context identical, merge the three branches into migration/legacy-portal-<token>, run make lp-reset RUN=<token> CTX=all and make lp-replay RUN=<token> CTX=all STAGE=full, and post the replay table, the API URL and the CloudTrail rows for each role session (aws cloudtrail lookup-events --lookup-attributes AttributeKey=Username,AttributeValue=devin-<session id> for this session and each child). Then open one integration pull request against main with the table in the body and the account number replaced by <account>, and do not merge it.
```

## Child prompt

Run as a child of the orchestrator in Fusion mode, once per context. Replace `<context>` with `announcements`, `preferences` (the `user_preferences` schema) or `feedback`.

```text
You are the <context> child of the legacy-portal orchestrator for run token <token> in Cognition-Partner-Workshops/otterworks. Cut branch migration/legacy-portal-<context>-<token> from migration/legacy-portal-<token> and never push to main or merge anything. Use the builder role for every AWS call: source <(cloudworker/assume.sh builder devin-<session id>). Do not edit services/legacy-portal/parity/, the Terraform root infrastructure/terraform/legacy-portal-serverless/ or its values, scripts/lp-serverless.sh, the lp-* Makefile targets, the Java source in services/legacy-portal/ or anything under cloudworker/.

Port the <context> bounded context of services/legacy-portal (its controller, service, entity and repository, with the routes in services/legacy-portal/README.md) to a Java handler for the existing function <token>-<context>, in a new directory under services/legacy-portal-lambda/<context>/. Read the database through the RDS Data API with the CLUSTER_ARN, SECRET_ARN, DB_NAME and DB_SCHEMA environment variables already set on the function. Deploy with aws lambda update-function-configuration (Java runtime and handler) and aws lambda update-function-code on <token>-<context>, and leave the function's role, environment and tags alone.

Then run make lp-reset RUN=<token> CTX=<context> and make lp-replay RUN=<token> CTX=<context> STAGE=first. If you are the announcements child, also run make lp-replay RUN=<token> CTX=common STAGE=first. Post the replay table and the printed diff of the first divergence, then stop and wait for an instruction. Do not fix anything before the instruction arrives.

After the instruction, change the handler until make lp-reset RUN=<token> CTX=<context> followed by make lp-replay RUN=<token> CTX=<context> STAGE=full shows every case identical. Never change requests.json, java-reference.json or SHA256SUMS; the replay refuses to run if their checksums change. Commit the handler and the replay's SUMMARY.md under services/legacy-portal-lambda/<context>/REPORT.md, push the branch, and post the final replay table, the API URL and your CloudTrail rows (aws cloudtrail lookup-events --lookup-attributes AttributeKey=Username,AttributeValue=devin-<session id>).
```

## Architect steer line

The architect says this live in the Feedback child after it has posted its first replay. The first sentence is the line from the demo record; the second is the full instruction the session receives.

```text
Fix the adapter so the recorded responses pass, and do not change the recording.
Fix the Feedback adapter until every case in the recorded corpus passes against the deployed function, do not change requests.json or java-reference.json, commit the replay report, and open the pull request.
```

## Verify prompt

Run as the cloud engineer persona in a fresh session after the integration pull request is open.

```text
Verify the legacy-portal migration for run token <token> in Cognition-Partner-Workshops/otterworks on branch migration/legacy-portal-<token>. Use the builder role: source <(cloudworker/assume.sh builder devin-<session id>). Change no files and push nothing.

Check that the recordings are the ones on main: git diff origin/main -- services/legacy-portal/parity services/legacy-portal/src infrastructure/terraform/legacy-portal-serverless must print nothing, and (cd services/legacy-portal/parity && sha256sum -c SHA256SUMS) must print OK for both files. Then run make lp-reset RUN=<token> CTX=all and make lp-replay RUN=<token> CTX=all STAGE=full.

Post the replay table, the API URL from make lp-status RUN=<token>, the result of both checks, and the CloudTrail rows for the orchestrator, the three children and this session, by role session name devin-<session id>, with the account number replaced by <account>. Say plainly whether all 95 cases are identical, and list the case ids of any that are not.
```
