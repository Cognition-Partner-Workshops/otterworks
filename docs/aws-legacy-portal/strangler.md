# Strangler carve-out: one legacy-portal module at a time off the EC2 box

One bounded context of `services/legacy-portal` (announcements, preferences or feedback) runs on API Gateway,
Lambda and Aurora Serverless v2, with the Lambda code main already carries in `services/legacy-portal-lambda/<module>`.
Everything else (the other modules, `/health`, `/actuator/*`) stays on an `lp-ec2` run, reached through the
same HTTP API. Announcements was the first module: every create or publish puts an `announcement.published`
event on EventBridge, the contract `legacy-portal-serverless` uses too.

```
client -> HTTP API  --ANY <prefix>, ANY <prefix>/{proxy+}-->  Lambda <run>-<module> (java21, alias live, SnapStart)
             |                                                  |-- RDS Data API --> Aurora Serverless v2 <run> (0-1 ACU)
             |                                                  '-- PutEvents (announcements only) --> bus otterworks-<run>
             |                                                        rule <run>-announcement-published
             |                                                          |--> SQS <run>-announcement-published (notification side, DLQ)
             |                                                          '--> log group /aws/events/<run>-announcement-published
             '--$default (HTTP_PROXY, full path + query)--> ALB of the lp-ec2 run (Spring Boot monolith + local Postgres)
```

| Module | Run token | Prefix on Lambda | Aurora table | Events |
|---|---|---|---|---|
| announcements | `lp-ann-<yyyymmdd>-<xx>` | `/api/announcements` | `announcements.announcement` | `announcement.published` |
| preferences | `lp-pref-<yyyymmdd>-<xx>` | `/api/preferences` | `user_preferences.user_preference` | none |
| feedback | `lp-fb-<yyyymmdd>-<xx>` | `/api/feedback` | `feedback.feedback` | none |

The abbreviation in the run token picks the module; `MODULE=` is optional and must agree with it.

| Piece | Where |
|---|---|
| Lambda code | `services/legacy-portal-lambda/<module>` (Java 21, AWS SDK v2, no Spring), unchanged from main |
| Terraform root | `infrastructure/terraform/legacy-portal-strangler`, state `otterworks/legacy-portal-strangler/<run>/terraform.tfstate`; schema DDL from `legacy-portal-serverless/schema.sql` |
| Harness | `scripts/lp-strangler.sh`, `make lp-mod-*` |
| Tags on every resource | `demo=legacy-portal-strangler`, `run_token`/`RunToken=<run>`, `Expires`, `ManagedBy=terraform`, `strangles=<lp-ec2 run>`, `bounded_ctx=<module>` |

The EC2 stack is only read (`data "aws_lb"`), never managed, so `lp-mod-down` cannot touch it.

## Commands

| Command | What it does |
|---|---|
| `make lp-mod-up RUN=lp-<ann\|pref\|fb>-<yyyymmdd>-<xx> EC2_RUN=lp-ec2-<yyyymmdd>-<xx>` | Builds the module's shaded jar with Maven (JDK 21), plans and applies the root |
| `make lp-mod-deploy RUN=<run>` | Builds the jar and applies the root, which publishes a new version when code or configuration changed. Then creates a CodeDeploy deployment that moves `live` from the current version to the new one with `CodeDeployDefault.LambdaCanary10Percent5Minutes` (10% for 5 minutes, then 100%). CodeDeploy rolls `live` back if `<run>-<module>-5xx-rate` (5xx share of the module's routes, from HTTP API detailed metrics) or `<run>-<module>-errors` (Lambda `Errors`) goes to ALARM. The command exits non-zero unless the deployment succeeds. `.github/workflows/cd-lp-strangler.yml` runs it on every merge to main that touches this root, the Lambda code or the harness, for each run in the `LP_STRANGLER_CD_RUNS` repository variable |
| `make lp-mod-status RUN=<run>` | Outputs, Lambda version and SnapStart status, cluster, rule pattern (announcements), four probe requests through the API |
| `make lp-mod-reset RUN=<run>` | Truncates the module's table on Aurora and, under the EC2 lock, the three context tables on the EC2 box (SSM Run Command) |
| `make lp-mod-replay RUN=<run> TARGET=both` | Under the EC2 lock: resets, replays the 95-case corpus against the EC2 ALB, resets again, replays against the HTTP API, prints the parity table |
| `make lp-mod-events RUN=<lp-ann run>` | Creates one announcement through the API and shows the event in the queue and in the audit log group |
| `make lp-mod-down RUN=<run>` then `make lp-mod-verify-clean RUN=<run>` | Destroys the run and proves nothing tagged or named with it remains |

## Shared EC2 box: the replay lock

Every replay needs empty tables on the EC2 box, and all runs in front of one `lp-ec2` run share its Postgres.
`reset` and `replay` therefore hold `s3://otterworks-terraform-state/otterworks/legacy-portal-strangler/locks/<lp-ec2 run>.lock`.
It is created with `put-object --if-none-match '*'`, which fails with `PreconditionFailed` while another run holds it.
While it is held, a background heartbeat rewrites it every `LOCK_HEARTBEAT_SECONDS` (60) with `--if-match` on
its own ETag. If that conditional write fails, the lock is no longer this run's, and the heartbeat stops the
command so its results are not used. A waiting run polls every 20 s for up to `LOCK_WAIT_SECONDS` (2700).
Only a lock that has not been refreshed for `LOCK_STALE_SECONDS` (900) belongs to a crashed run, however long a
replay takes. Breaking a stale lock and releasing one are both `delete-object --if-match <ETag>`, so a run never
deletes a lock that someone else has taken or refreshed in the meantime
([conditional deletes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-deletes.html)).
`reset` takes the lock before it truncates the Aurora table too. `up`, `status`, `events` and `down` take no
lock, so builds and applies of different modules run in parallel.

## Deploys and the EC2 binding

- **New Lambda versions:** `live` keeps the previous version until `terraform_data.live_ready` has seen the new
  SnapStart version Active (`aws lambda wait function-active-v2`). Requests never reach a Pending version,
  neither on an update nor on the first deploy.
- **The EC2 run is fixed at the first `up`.** Later `up`s read it from the Terraform state. A different
  `EC2_RUN` on an existing run is refused, because it would move every `$default` route. To do that on
  purpose, use `RETARGET_EC2=1`.
- **Traffic to the EC2 ALB is still plain HTTP** to the ALB's public DNS name, the same as clients that call
  the ALB directly today. The lp-ec2 ALB has only a port-80 listener, and this root does not change the EC2
  stack. A VPC link to that listener was tried and does not work here: with the link `AVAILABLE`, every `$default`
  request returned 503 after 9 s, so it was rolled back. Encrypting the hop needs a change to `legacy-portal-ec2`:
  either an HTTPS listener with an ACM certificate on a domain we own (then `https://` in `integration_uri`),
  or an internal ALB that a VPC link can reach
  ([private integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-private.html)).

## Event contract (announcements)

```json
{
  "source": "otterworks.legacy-portal",
  "detail-type": "announcement.published",
  "detail": {"id": 1, "title": "Release", "body": "...", "published": true, "createdAt": "2026-10-06T09:11:32.087411Z"}
}
```

Put once per successful `POST /api/announcements` and once per successful `POST /api/announcements/{id}/publish`,
after the row is committed; `detail.published` tells the two apart for a draft. Rejected writes (400, 404, 405,
406, 415) put nothing. Publishing is best effort: a `PutEvents` failure is logged and the HTTP response stays
exactly what the monolith returns. The rule's `source` (variable `event_source`) must equal
`EventBridgeAnnouncementEvents.SOURCE`.

## Choices and the AWS documentation behind them

Read through the AWS Documentation MCP server (`aws___search_documentation`, `aws___read_documentation`).

| Choice | Decision | Documentation |
|---|---|---|
| Lambda runtime | `java21` (Amazon Linux 2023, deprecation 2029-06-30), 1024 MB; arm64 for announcements ([power tuning](announcements-power-tuning.md)), x86_64 for the modules not measured yet; SnapStart on published versions behind the `live` alias, which CodeDeploy moves with a canary | [Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html): java21 is a supported AL2023 runtime; the java11 runtime of the monolith runs on Amazon Linux 2 and AWS recommends AL2023 runtimes for new work |
| Payload format | HTTP API, `AWS_PROXY`, `payload_format_version = "2.0"`; the handler returns the full `statusCode`/`headers`/`body`/`isBase64Encoded` shape | [HTTP API Lambda integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html): 2.0 carries `rawPath` and `rawQueryString` (the dispatcher needs the undecoded path for Spring's case-sensitive and trailing-slash matching), lowercases header names, and only guesses the response when `statusCode` is missing, which would break the 406/415 parity cases |
| Routing the rest | `$default` route on an `HTTP_PROXY` integration to the lp-ec2 ALB | [HTTP API routes](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-routes.html): `$default` catches every request no other route matches and passes the full path; `{proxy+}` must be the last path segment |
| Event entry | `PutEvents` with `EventBusName`, `Source`, `DetailType`, `Detail` (JSON string) | [PutEventsRequestEntry](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutEventsRequestEntry.html): `Source` is free form but `aws.` is reserved, `DetailType` up to 128 characters, `Detail` must be valid JSON |
| Rule shape | Custom bus (announcements runs only), pattern `{"source": [...], "detail-type": ["announcement.published"]}` | [Event patterns](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html): patterns have the structure of the events they match, arrays of exact values, match on `source`, `detail-type` and `detail`; narrow patterns avoid unwanted matches |
| Rule targets | SQS queue (+ DLQ) with a queue policy scoped to the rule ARN; CloudWatch Logs group with a log resource policy for `events.amazonaws.com` and `delivery.logs.amazonaws.com` | [EventBridge resource-based policies](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-use-resource-based.html): the console adds the CloudWatch Logs policy itself, the API/Terraform must create it |

## Known limits

- Like `legacy-portal-serverless`, the function has X-Ray tracing off and its environment
  uses the AWS-managed Lambda key; both are marked `nosemgrep` in `lambda.tf`. The
  environment holds ARNs and names only; the DB password stays in Secrets Manager.
- EventBridge publication is best effort: a failed `PutEvents` is logged and the write
  still returns its usual status.

## Parity per module

Each module's run replays the whole corpus twice from empty tables with ids restarting at 1: against the
`lp-ec2` ALB (the Java monolith) and against the run's HTTP API (the module on Lambda + Aurora, the rest on
EC2), both compared with `java-reference.json` after the checksums matched `SHA256SUMS`.

### announcements, run `lp-ann-20261006-a1` in front of `lp-ec2-20261006-b1`

`make lp-mod-replay RUN=lp-ann-20261006-a1`, 2026-10-06, Lambda version 4 (main's `services/legacy-portal-lambda/announcements`).

| Context | Cases | Served by (new) | EC2 ALB identical | HTTP API identical |
|---|---|---|---|---|
| common | 10 | EC2 | 10/10 | 10/10 |
| announcements | 36 | Lambda + Aurora | 36/36 | 36/36 |
| preferences | 20 | EC2 | 20/20 | 20/20 |
| feedback | 29 | EC2 | 29/29 | 29/29 |
| **total** | **95** | | **95/95** | **95/95** |

`make lp-mod-events RUN=lp-ann-20261006-a1` then showed `announcement.published` (source `otterworks.legacy-portal`)
for the create in the SQS queue and in `/aws/events/lp-ann-20261006-a1-announcement-published`, and the corpus's
own create and `/publish` events in the queue.

Cleanup: `make lp-mod-down RUN=lp-ann-20261006-a1 && make lp-mod-verify-clean RUN=lp-ann-20261006-a1`
