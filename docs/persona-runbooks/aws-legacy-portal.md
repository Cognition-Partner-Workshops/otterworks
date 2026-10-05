# AWS modernization: legacy portal to Lambda

Devin moves a Java 11 Spring Boot monolith with three bounded contexts onto API Gateway, one Java 21 Lambda per context and Aurora PostgreSQL Serverless v2, and proves parity by replaying a recorded corpus of 95 HTTP cases until every case matches the Java recording. The work fans out to one worker per context.

| Field | Value |
|---|---|
| `runAs` | AWS (`user-094334530455473bb8c587d207307833`) |
| Field Kit | Area `ISV and platform`, Identity `AWS` |
| Delegation shape | Scalable. Each bounded context is the same job with a different table set; the orchestrator runs one worker per context at the same time. |
| Repository | `Cognition-Partner-Workshops/otterworks` |
| Harness branch | `devin/1791186826-legacy-portal-serverless` (pull request 1807, Make targets `lp-*`, `scripts/lp-serverless.sh`, `infrastructure/terraform/legacy-portal-serverless/`, `services/legacy-portal/parity/`) |
| Source | `services/legacy-portal`: announcements, user preferences, feedback; announcements also owns the common routes |
| Contract | `services/legacy-portal/parity/requests.json`, `java-reference.json` and `SHA256SUMS`. Nobody edits them. |
| Mode | Fusion |
| Way A | An orchestrator session that spawns one child per context |
| Way B | The Migrations page with the brief attached: a plan to approve, one board ticket per step, worker sessions |

## Preflight, the day before

From a checkout of the harness branch with operator AWS credentials. Pick a run token of the form `lp-<yyyymmdd>-<two letters>`.

1. `make lp-up RUN=<token> EXPIRES_DAYS=3`. Terraform creates the API, three placeholder functions, the Aurora cluster and a builder policy scoped to the token. The Aurora writer takes most of the time: 476 seconds end to end on the 2026-10-05 rehearsal. Keep the `api_url` it prints.
2. `make lp-status RUN=<token>`. Expect 16 tagged resources, the cluster `available` with the Data API on at 0 to 1 ACU, and three functions in state `Active`.
3. `make lp-reset RUN=<token> CTX=all` then `make lp-replay RUN=<token> CTX=all STAGE=first`. Every context stops at its first case with a 501 from the placeholder. That is the start state the workers inherit.
4. The AWS calls the workers make use the builder role through `cloudworker/assume.sh builder devin-<session id>`, with the org secrets `CW_AWS_ACCESS_KEY_ID`, `CW_AWS_SECRET_ACCESS_KEY` and `CW_BUILDER_ROLE_ARN` already in place. No new secret is needed.

## Live, way A: orchestrator with children

1. Sign in as the AWS persona, start a session on `otterworks` in Fusion mode and paste the orchestrator prompt from `docs/aws-legacy-portal/prompts.md` with the token filled in. The prompt tells the orchestrator to branch from the harness branch, to spawn one child per context, and to have each child port its context, deploy with `aws lambda update-function-code`, reset its tables and run the first-stage replay.
2. Each child stops at its first divergence and asks. On 2026-10-05 the four divergences were the health groups on `/actuator/health`, the error body for an invalid announcement id, and the 404 body for an uppercase route in preferences and in feedback. Answer in the child: fix the adapter, the recording is the contract.
3. When all three children report their context identical, the orchestrator merges the three branches, runs `make lp-replay RUN=<token> CTX=all STAGE=full` and opens one integration pull request against the harness branch.
4. Close on the orchestrator's summary: 95 of 95 identical, the pull request link and the CloudTrail events per role session.

## Live, way B: the Migrations page

1. Sign in as the AWS persona, open the Migrations page of `Partner Demo - ViewOnly`, type the one-sentence request and attach the brief from `/home/ubuntu/prompts/aws-native/migrations/legacy-portal-brief-<token>.md`.
2. The migration agent drafts a four-phase plan in the Plan view: program branch and harness check, one step per context, integration and full replay, hand-off and verification. Each step carries exit criteria measured by the replay.
3. Resolve the open decisions it marks. Expect two: whether workers port fresh from the Java source or read an earlier branch (answer: fresh port, earlier branch read only), and the first-divergence policy (answer: stop and ask, as the brief says).
4. Approve the plan. Approval creates one board ticket per step with the dependencies carried over; worker sessions take the tickets and the board moves them across.
5. The live decision: when the announcements worker reports its first divergence, answer it in the plan or the ticket so the room sees the plan change hands.
6. Close on the board with every ticket done, two or three worker sessions open, and the exit criteria ticked on the replay evidence and the pull request.

## Expected state after

| Check | Expected |
|---|---|
| `make lp-replay RUN=<token> CTX=all STAGE=full` | `95/95 identical` (common 10, announcements 36, preferences 20, feedback 29) |
| Integration pull request | open against `devin/1791186826-legacy-portal-serverless` and left open; CI skips it because the base is a `devin/` branch |
| Corpus | `sha256sum -c services/legacy-portal/parity/SHA256SUMS` passes |
| `make lp-status RUN=<token>` | three functions updated, cluster available |

## Reset and teardown

```bash
make lp-reset RUN=<token> CTX=all       # tables back to the seeded state, 6 seconds
make lp-down RUN=<token>                # destroys the stack, 727 seconds on the rehearsal
make lp-verify-clean RUN=<token>        # prints CLEAN when nothing tagged with the token remains
```

Each run token has its own Terraform state key, so two tokens can be up at once. Transcripts land in `.demo/legacy-portal/<token>/` with the account number already redacted.

## Fallback

- `lp-up` fails while the writer is creating: run it again; the second apply is a no-op on what already exists.
- A worker's first replay returns 502 from the API: the function is still on the placeholder or the handler name is wrong; read `aws lambda get-function-configuration` for the function the token names.
- Aurora paused after 600 idle seconds: the first request wakes it in about 15 seconds and the replay tolerates that.
- The Migration Agent reports `Unknown board ticket ids` right after approval: the board is still indexing; it retries on its own within a minute.
- The stack-check worker says Aurora shows no Serverless v2 scaling settings: answer in the session with the operator's `make lp-status RUN=<token>` output, which reads `ServerlessV2ScalingConfiguration` with operator credentials.
- Every session stops with `Devin went to sleep because your per-user ACU limit was exceeded`: the persona is in the enterprise default tier (100 ACU a cycle). Put it in the uncapped `FieldKit` tier under Enterprise Settings, Usage policies, or `PUT /v3beta1/enterprise/usage-policies/tiers/<FieldKit tier id>/users/<user id>`, then send the manager one message and it wakes the workers. Check the tier the day before; a program with five sessions spends 100 ACU in about 40 minutes.
- The Migrations page is unavailable: run way A. The audience sees the same children and the same pull request.

## Talk track

Three workers, one job each, one recording as the contract. Devin does the port the same way for every context and the replay says when it is done; the human decides only what to do at the first divergence. For a room that wants to change the plan live, way B puts that decision on the plan itself.

## Evidence from the recorded runs

| Item | Where |
|---|---|
| Orchestrator session, AWS, Fusion, three children | https://partner-workshops.devinenterprise.com/sessions/e2d39853122644afb9741467c8b4dc66 |
| Children | `6768f0f6` announcements and common, `fbc00b47` preferences, `fc5b7463` feedback |
| Integration pull request, run `lp-20261005-vo` | https://github.com/Cognition-Partner-Workshops/otterworks/pull/1810 |
| Stack status, function versions, live responses | `evidence/aws/final-audit-lp-20261005-vo.txt` |
| Rehearsal timings and cost | `docs/aws-legacy-portal/rehearsal.md` on the harness branch |
| Migrations-page session, run `lp-20261005-mp` | https://partner-workshops.devinenterprise.com/sessions/509a30c2af9b4e0f8f55d4e07f728ef0 |

## Rerun log

| Date | Who | Session | What the runbook had not said |
|---|---|---|---|
| 2026-10-05 | AWS persona, way A, token `lp-20261005-vo` | `e2d39853` | Announcements must land before preferences and feedback because it owns the common routes; added to the prompt file. |
| 2026-10-05 | AWS persona, way B, token `lp-20261005-mp` | `509a30c2` | The Migration Agent's first dispatch failed with `Unknown board ticket ids` while the board was still indexing and retried on its own a minute later; added to Fallback. The stack-check worker reads Aurora under the observer role and may not see the Serverless v2 scaling block; added to Fallback. |
