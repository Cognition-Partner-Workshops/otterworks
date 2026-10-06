# The presenter guide for Devin on AWS

This guide is for the person who opens the partner demo organization in front of an AWS audience and talks for twenty to forty minutes. Every item you show is a Devin session that the AWS, Databricks or MongoDB persona started. You sign in through the Field Kit SSO page, pick the area and the identity, and the sidebar of that persona is the demo. The AWS console stays closed on your side, because every session recorded the console as a read-only user while it worked and attached the recording.

## The one idea

Devin is an AI software engineer you delegate to, the way you delegate to a colleague on the team. You hand Devin a request in plain language, and Devin goes to the systems the work needs (the repository, the AWS account, the documentation, the alarm history), does the work, proves the result and leaves the evidence where the team can audit it. The demo works when the audience recognizes work from their own week in each session and sees that the work finished without anyone hovering.

## The delegation tests

Before you open a session, say which of these the work passes. Most of the sessions pass several.

1. The judgment is easy and the volume is the hard part.
2. The same job comes back every week, every month, every alarm.
3. The job is tedious, and nobody on the team wants to be the one who does it.
4. A person cannot hold the context: logs, docs, deployment history, cost reports, all from different systems.
5. A corpus, a gate, an alarm state or a clean-state check says done, so the agent keeps going until the check passes.
6. The job blocks someone more expensive, or has to run at three in the morning.

The on-demand worker shape runs through the whole portfolio. Something happens (an alarm, a schedule, a webhook, a merged change), a session starts from the event, pulls what the job needs, does one bounded piece of work, checks the result and leaves an artifact. Say that sentence once, early, and point at the shape every time a session starts without a person.

## Migrate, modernize, operate

| Stage | What the audience worries about | Sessions |
|---|---|---|
| Migrate | Getting off the box, the old database and the stored procedures without breaking anything | Billing off the legacy DB (Migrations page), Databricks and MongoDB readiness runs |
| Modernize | Serverless, event-driven, modern API shape, one module at a time and then the rest | Announcements to API Gateway and Lambda, playbook and fan-out over the other modules, iOS latency, code scans |
| Operate | Alarms at night, cost nobody looks at, leftovers in the account | Tester and responder pair, Well-Architected and Lambda tuning with canary CD, the TCO dashboard, the monthly reaper |

## The sessions in presenting order

### 1. Announcements to API Gateway, Lambda and Aurora Serverless

Session: https://partner-workshops.devinenterprise.com/sessions/3639548fd1664246a0c896bcdd3c5c03. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1819 (run token lp-ann-20261006-a1, cleanup `make lp-ann-down RUN=lp-ann-20261006-a1 && make lp-ann-verify-clean RUN=lp-ann-20261006-a1`).

Say first: "The legacy portal is a Java 11 Spring Boot app on one EC2 box with Postgres on the same disk. Every deploy is an scp and a restart. We asked Devin to move one module."

Tests: 4 (the Lambda runtime, the payload format and the EventBridge rule shape came from the AWS docs through the MCP server), 5 (the 95-case parity corpus is the contract), 6 (nobody on the team had a free week for the move).

What to open: the prompt (one paragraph, written like a person), the MCP documentation calls and what Devin read, the Terraform under `infrastructure/terraform/legacy-portal-serverless`, the parity table (95 of 95 on both the EC2 ALB and the new API), and the console recording as the read-only user showing the EC2 instance still serving the other modules, the new Lambda, the HTTP API, the EventBridge rule, the Aurora cluster and the CloudWatch logs for a real request. Close on the run token and the one command that removes the stack.

Open #1819 in the Review tab as well. Show the flags and the security findings on the Lambda handlers and the IAM policy, and say that the review runs on every pull request the team opens, including the ones people write.

### 1b. The playbook and the fan-out

Session: the second request in the act 1 session above. Playbook `03e3dd5a04174073b8d7690c3dc6ceb0` in the persona's organization. Children: preferences https://partner-workshops.devinenterprise.com/sessions/5aca9a5de8b7420a96ca552bcb9f3adf (PR https://github.com/Cognition-Partner-Workshops/otterworks/pull/1824, 95/95 on both sides, no retries) and feedback https://partner-workshops.devinenterprise.com/sessions/c967f2c6a4ba492b8ba8b1d6802e8b81 (PR https://github.com/Cognition-Partner-Workshops/otterworks/pull/1825, 95/95 on both sides, one retry of the startup check). Each child recorded its own console pass as the read-only user, and both children found the same SnapStart timing bug, so the parent folded the fix back into #1819.

Say first: "That worked once, and now we want it to work for the other modules without anyone re-learning it."

Tests 1, 2 and 3 apply: the second module is the same work as the first, the playbook captures prerequisites, inputs, steps, validation, reset and cleanup, and Devin fans the playbook out from the same session over preferences and feedback in parallel with a bounded number of retries each.

What to open: the playbook Devin wrote, the two child sessions, one child's own evidence, and the final table (module, parity result, PR, console evidence, cleanup command). Nothing merges.

### 2. A tester plants a bad rollout and an automation answers the page

Tester session: https://partner-workshops.devinenterprise.com/sessions/10e63f0d9cf74432849a8aa1208ba8c9. Responder session: https://partner-workshops.devinenterprise.com/sessions/fac144423e654d2c9ab4f3f7578124d5. Automation: https://partner-workshops.devinenterprise.com/org/partner-demo-viewonly/automations/auto-98aa3455ecf54a8a94e138dde67ddf60 (run as AWS, webhook from an EventBridge API destination).

Say first: "Nobody trusts an on-call automation until someone has tried to break it. We asked one Devin session to be that someone."

Tests: 2 (every alarm), 4 (metrics, logs, deployment history and CloudTrail in one place), 5 (the alarm has to be OK again and the corpus has to pass), 6 (three in the morning).

What to open: in the tester, the CodeDeploy canary from the broken build, the console recording of the 5xx alarm going red, the EventBridge rule firing at the webhook and the responder session appearing. In the responder, the plain-language instructions on the automation page, the root cause in plain words, the rollback or the fix PR, and the alarm back to OK. Then back in the tester, the independent check of alarm, canary, parity and whether the responder's root cause was right.

### 3. Billing off the legacy database, phase by phase, in order

Session: https://partner-workshops.devinenterprise.com/sessions/cf61e0a07aea4c21aa74496195d025c9. Board: Billing off legacy DB. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1822.

Say first: "Some migrations cannot be parallelized, because rating logic has to leave the stored procedures before the tables can move, and the nightly summary can only be rebuilt on what moved."

Tests: 4 (stored procedures, routes, the Oracle fixture, RDS, S3 and Athena), 5 (parity and row counts), 6 (a quarter of someone's calendar).

What to open: the Migrations page with one request and a short brief, the plan with its ordered phases, one ticket per step, the rating rules ledger with the eight parity-sensitive rules and the presenter's decision (port the behaviour exactly, double rounding included, finance fix as a follow-up), the before and after row counts, the Athena comparison, the console recording, and the single PR.

The session stops once, to ask a business question (3.06 or 3.05), and your answer is the only human step in the run. Give the answer live if you want a live moment.

### 4. Well-Architected, cost, and one optimization done end to end

Session: https://partner-workshops.devinenterprise.com/sessions/12dfaaa41ab346aba47df46e7b1e0379. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1823 (stacked on the branch of #1819).

Say first: "Everyone has a Well-Architected review they have not done and a Lambda on the default memory size."

Tests: 2, 3, 4 (Cost Explorer, Trusted Advisor, EKS, RDS, EC2 and the new stack), 5 (the numbers pick the memory size).

What to open: the ranked list with a monthly number next to each item, the memory sweep with the parity corpus as load, latency against cost per million requests, x86 against arm64, the Terraform change, the continuous deployment workflow with the CodeDeploy canary and the alarm as the gate, and the console recording of Cost Explorer, Lambda configuration and the CloudWatch duration graphs before and after.

### 5. The slow iOS client

Session: https://partner-workshops.devinenterprise.com/sessions/9cb235651eaf494c839798ecbd9b1313. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1820.

Say first: "A bug report says the iPhone app's document list is slow and the web app is fine. Someone has to build the native app, reproduce the slowness and find out whether the client or the gateway is at fault."

Tests: 3, 4 (simulator, ingress logs in CloudWatch Logs Insights, both clients), 5 (p95 before and after).

What to open: the macOS session building the Capacitor app and running the simulator, the Logs Insights comparison between the two clients, the cause, the fix PR, the p95 before and after, and the tenant teardown at the end.

### 6. Code scans before the customer release

Session: https://partner-workshops.devinenterprise.com/sessions/8da691bbadc04145bbf1a07656cbd354. PR: https://github.com/Cognition-Partner-Workshops/otterworks/pull/1821 (security scan 8c17da56, performance scan fadac18a).

Say first: "Before this goes in front of customers we want a security and a performance pass over the handlers and the Terraform."

Tests: 1, 2, 3.

What to open: the two scans started from the session, the findings list with severities, the one PR that fixes what matters, the findings Devin chose to leave and the reason for each, and the Devin Review of the PR.

### 7. The monthly reaper

Automation: Monthly AWS reaper, https://partner-workshops.devinenterprise.com/org/partner-demo-viewonly/automations/auto-8b968df2de64412cbe93ad3251eeb140 (first Tuesday 06:40 UTC, run as AWS, AWS MCP, one run at a time). Test session: https://partner-workshops.devinenterprise.com/sessions/bc778dd63f3c42c293cee7dd39d3affc. Run: https://partner-workshops.devinenterprise.com/sessions/23aa2aa57bd94e15a6b1f5b2c98539a0.

Say first: "Every account has leftovers, and ours are tagged with a run token and an expiry, so cleaning up is simple, recurring, tedious and self-verifying. We scheduled it."

Tests: 1, 2, 3, 5.

What to open: the automation page with instructions a person can read, the schedule (first Tuesday, 06:40 UTC), the test session that planted an expired stack and a stale log group and then ran the automation, the run's table of what was removed and what was kept with the reason, and the estimated monthly saving.

### 8. The TCO decision dashboard and its Pricing Calculator estimates

Session: https://partner-workshops.devinenterprise.com/sessions/2cfae20440af4a28b831ade4f691efbf. No PR, and nothing was created in AWS.

Say first: "Every architecture review has a slide with numbers nobody can trace. This dashboard has a footnote on every figure and a Pricing Calculator estimate the reviewers can open themselves."

Tests: 3 (thirty Cost Explorer lines, Pricing API rates, two request counters and a PR's measurements, by hand), 4 (Cost Explorer, CloudWatch, the Pricing API, PR #1823 and the on-call test, in one place), 5 (the "today" column has to reconcile to Cost Explorer to the cent before Devin stops).

The request was one message: finish the strangler or stay on EC2, Graviton or not, give me one HTML file for the review with three-year TCO per option and the source of every number, and build the same options in calculator.aws so the reviewers see them in a tool they trust.

What to open: the dashboard attached to the session (the options side by side, sliders for 1x, 3x and 10x traffic and for a one- or three-year Savings Plan, the break-even month, the assumptions table you can edit live, and the provenance footnotes), the reconciliation block (September 2026 is $411.51 across 30 service lines, and the lines add up to the total), the Pricing Calculator estimates (A https://calculator.aws/#/estimate?id=887075261b639cb7c8b4c2865638fe88c9246190, B https://calculator.aws/#/estimate?id=d125e51fe5e2b49897fef8e76580e3f0853826e7, C https://calculator.aws/#/estimate?id=326cf1fb39a3c82d529c351d3592e11a60df53b7) next to the model's own figure with each gap explained, and the read-only console recording of Cost Explorer and the pricing pages.

Dwell on the answer, because staying on EC2 is cheapest at every traffic level ($40.93 a month against $97.50 serverless and $81.51 on EKS Spot) and Devin says why: the one-a-minute Synthetics probe costs $52.56 a month and keeps Aurora awake at 0.5 ACU for another $43.80. Drop the probe and let Aurora pause, and serverless is cheaper from month one. Devin reported a number that argued against the migration it had just built, and an argument of that kind is what an architecture review is for.

For a live moment, change an assumption in the table (Aurora awake hours, the migration effort, the no-responder recovery time) and watch the three-year totals and the break-even month move, or send "what if traffic triples and we commit to a one-year Savings Plan" as a follow-up and let Devin answer from the same file.

If someone asks about the assumptions, the dashboard labels four. Cost allocation tags are inactive, so the "today" column is modelled from the portal's resources at reconciled rates, and the dashboard says so instead of calling the column attributed spend. Recovery without the responder (30 minutes) and Graviton energy (AWS's "up to 60%" claim applied to the measured GB-s per million requests) were never measured. The EKS option charges the portal a quarter of a c6g.xlarge node, and the calculator prices whole nodes, so the calculator estimate for C is higher than the model. The share links expire on 2027-10-06.

### Databricks and MongoDB

Databricks sessions: https://partner-workshops.devinenterprise.com/sessions/cf5822ffaa724b798f867f67ab1cf3b0 (readiness check) and https://partner-workshops.devinenterprise.com/sessions/2c6033940ae940e3b801321ed8197c86 (runbook re-run). Both stop at the credential gate, waiting for a working DATABRICKS_HOST, DATABRICKS_TOKEN and DATABRICKS_WAREHOUSE_ID. MongoDB sessions: https://partner-workshops.devinenterprise.com/sessions/5b01fbf33ade48908b565d74bbabbd27 (migration plan), https://partner-workshops.devinenterprise.com/sessions/9e56cebaf84040ba9f1ed6affdbc05ab (U2 rehearsal against the local Oracle fixture and mongo:7, planted document-shape mismatch preserved), https://partner-workshops.devinenterprise.com/sessions/910ac7c80059469284ff63affd4a87fa and https://partner-workshops.devinenterprise.com/sessions/d4665ccb32cf43279c5897b298ff7834 (readiness and gates). Atlas itself waits for MONGODB_ATLAS_URI.

Both personas stop at readiness: the migration plan, the code and the parity harness exist, and the live run starts once the workspace token and the Atlas URI arrive. Say so plainly if asked.

## Before you present

1. Sign in through Field Kit with the area and identity for the persona you want. Area `ISV and platform` with identity `AWS` is the one you will use most.
2. The sidebar shows only sessions that persona owns. If a session is missing, you are signed in as the wrong persona.
3. The recordings and screenshots are attachments on each session. Open them from the session, and keep the AWS console itself closed during the demo.
4. Nothing in the portfolio merges to `main` during a demo. The pull requests are the artifact.

## Cleanup

Everything in the table carries a `run_token` tag and an `Expires` date, and the monthly reaper removes each stack once the date has passed. Run the commands from the repository root with the engineer role (`source <(cloudworker/assume.sh engineer <name>)`), in table order, after the recordings you want are attached to their sessions.

| Run token | What it is | Expires | Remove it |
|---|---|---|---|
| `lp-20261006-oc` | Live serverless portal the tester and responder worked on (3 Lambdas, HTTP API, Aurora, alarms, EventBridge rule and API destination, CodeDeploy app) | 2026-10-09 | `make lp-down RUN=lp-20261006-oc && make lp-verify-clean RUN=lp-20261006-oc` |
| `lp-ann-20261006-a1` | Announcements on the strangler root (PR #1819, #1823 planned against it) | 2026-10-08 | `make lp-mod-down RUN=lp-ann-20261006-a1 && make lp-mod-verify-clean RUN=lp-ann-20261006-a1` |
| `lp-pref-20261006-a1` | Preferences on the strangler root (PR #1824) | 2026-10-08 | `make lp-mod-down RUN=lp-pref-20261006-a1 && make lp-mod-verify-clean RUN=lp-pref-20261006-a1` |
| `lp-fb-20261006-a1` | Feedback on the strangler root (PR #1825) | 2026-10-08 | `make lp-mod-down RUN=lp-fb-20261006-a1 && make lp-mod-verify-clean RUN=lp-fb-20261006-a1` |
| `lp-ec2-20261006-b1` | The Java 11 monolith on EC2 with its ALB, the "before" state every module run strangles. Remove the monolith last, after the module runs above. | 2026-10-09 | `make lp-ec2-down RUN=lp-ec2-20261006-b1 && make lp-ec2-verify-clean RUN=lp-ec2-20261006-b1` |
| `lp-20261006-bd` | Billing data on RDS, the S3 usage export, Glue and Athena (PR #1822) | 2026-10-10 | The teardown block in PR #1822: `cd infrastructure/terraform/billing-data`, `terraform init -reconfigure -backend-config="key=otterworks/billing-data/lp-20261006-bd/terraform.tfstate"`, `terraform destroy -var run_token=lp-20261006-bd -var expires=2026-10-10T00:00:00Z`, then `make lp-verify-clean RUN=lp-20261006-bd` |
| `lp-20261005-mp`, `lp-20261005-vo` | Two earlier serverless portal runs from the first round of this work | 2026-10-08, 2026-10-07 | `make lp-down RUN=lp-20261005-mp && make lp-verify-clean RUN=lp-20261005-mp`, then the same for `lp-20261005-vo` |
| `cw` | The cloud-worker page estate (queues, DLQ, alarm, EventBridge rule, DynamoDB tables). Keep the estate while the on-call act is shown, since the responder automation triggers from it. | none | `make cw-teardown` |

The reaper never sees untagged resources, so remove this list by hand when the portfolio retires:

- IAM roles `devin-cw-observer`, `devin-cw-builder`, `devin-aws-engineer` and the console user `devin-aws-console` (the org secrets hold its password).
- IAM user `devin-cw-reader` (read-only, used by one tester session for the console).
- Devin automations in the persona's organization: the on-call responder and `Monthly AWS reaper` (`8b968df2de64412cbe93ad3251eeb140`). Disable the reaper if you want the schedule to stop, and delete the automation when the account is gone.
- Branches `review-base-lp-strangler`, `migrate/billing-off-legacy` and the `devin/…` branches behind PRs #1819 to #1825, once the PRs are closed.
- The temporary tuning function `lp-ann-a1-tune` was already deleted by the Well-Architected session, and the iOS tenant `mob-9cb235` was torn down by its session.

## Known limits

- The account is on Basic support, so Trusted Advisor, Cost Optimization Hub and Compute Optimizer returned nothing. The Well-Architected session worked from Cost Explorer, CloudWatch and the resource inventory instead and says so in its ranked list.
- The replatform console recording was made on Lambda version 1, before PR #1819 was rebased on `main`. The parity table and the event proof in the PR are from version 4. Same resources, same routes, one rename (`*-announcement-published`).
- In the incident test the fault returned HTTP 500 without throwing. The API 5xx alarm and the composite page alarm fired, the Lambda errors alarm stayed quiet, and CodeDeploy left the canary running. The responder's rollback brought the alarm back to OK, and the act sets out to show that recovery.
- The tester session used an IAM user for the bad deploy. The responder used the scoped builder role, so the role is what CloudTrail shows.
- The iOS session tested the iPhone simulator in one orientation only. Android and portrait were left out, and a 403 on the mobile notification endpoint, which has a different cause, was noted and left for a later session.
- Databricks and MongoDB stop at the credential gate (a working `DATABRICKS_HOST`, `DATABRICKS_TOKEN` and `DATABRICKS_WAREHOUSE_ID`; a `MONGODB_ATLAS_URI`). The Databricks and MongoDB sessions show the plan, the harness and the local rehearsal, and the live run waits for the credentials.
- The TCO dashboard models the portal's "today" column from its resources at rates reconciled to Cost Explorer, because the cost allocation tags are inactive and the EC2 before-state had not yet reached a billed month. Recovery time without the responder, Graviton energy and the EKS node share are labelled assumptions, and the Pricing Calculator share links expire on 2027-10-06.
- The monthly reaper has run once, against a planted expired run, and the schedule has not yet fired on its own. The first scheduled run is the first Tuesday of the month at 06:40 UTC.
- Pull requests #1819, #1820, #1821 and #1822 stay open on purpose. Merging #1819 or #1822 would start a real cutover, and merging #1820 would remove the planted mobile-latency scenario.
