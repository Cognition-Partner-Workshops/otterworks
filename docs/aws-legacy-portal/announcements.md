# Announcements carve-out: the first module off the EC2 box

The announcements context of `services/legacy-portal` runs on API Gateway, Lambda and Aurora Serverless v2,
and every create puts an `AnnouncementCreated` event on EventBridge. Everything else (preferences, feedback,
`/health`, `/actuator/*`) stays on an `lp-ec2` run, reached through the same HTTP API.

```
client -> HTTP API  --ANY /api/announcements, ANY /api/announcements/{proxy+}-->  Lambda <run>-announcements (java21, alias live, SnapStart)
             |                                                                     |-- RDS Data API --> Aurora Serverless v2 <run> (0-1 ACU)
             |                                                                     '-- PutEvents ----> bus otterworks-<run>
             |                                                                           rule <run>-announcement-created
             |                                                                             |--> SQS <run>-announcement-created (notification side, DLQ)
             |                                                                             '--> log group /aws/events/<run>-announcement-created
             '--$default (HTTP_PROXY, full path + query)--> ALB of the lp-ec2 run (Spring Boot monolith + local Postgres)
```

| Piece | Where |
|---|---|
| Lambda code | `services/legacy-portal-lambda/announcements` (Java 21, AWS SDK v2, no Spring) |
| Terraform root | `infrastructure/terraform/legacy-portal-announcements`, state `otterworks/legacy-portal-announcements/<run>/terraform.tfstate` |
| Harness | `scripts/lp-announcements.sh`, `make lp-ann-*` |
| Tags on every resource | `demo=legacy-portal-announcements`, `run_token`/`RunToken=<run>`, `Expires`, `ManagedBy=terraform`, `strangles=<lp-ec2 run>`, `bounded_ctx=announcements` |

The EC2 stack is only read (`data "aws_lb"`), never managed, so `lp-ann-down` cannot touch it.

## Commands

| Command | What it does |
|---|---|
| `make lp-ann-up RUN=lp-ann-<yyyymmdd>-<xx> EC2_RUN=lp-ec2-<yyyymmdd>-<xx>` | Builds the shaded jar with Maven (JDK 21), plans and applies the root |
| `make lp-ann-status RUN=<run>` | Outputs, Lambda version and SnapStart status, cluster, rule pattern, three probe requests through the API |
| `make lp-ann-reset RUN=<run>` | Truncates `announcements.announcement` on Aurora and the three context tables on the EC2 box (SSM Run Command) |
| `make lp-ann-replay RUN=<run> TARGET=both` | Resets, replays the 95-case corpus against the EC2 ALB, resets again, replays against the HTTP API, prints the parity table |
| `make lp-ann-events RUN=<run>` | Creates one announcement through the API and shows the event in the queue and in the audit log group |
| `make lp-ann-down RUN=<run>` then `make lp-ann-verify-clean RUN=<run>` | Destroys the run and proves nothing tagged or named with it remains |

## Event contract

```json
{
  "source": "otterworks.legacy-portal.announcements",
  "detail-type": "AnnouncementCreated",
  "detail": {"id": 1, "title": "Release", "published": true, "createdAt": "2026-10-06T09:11:32.087411Z"}
}
```

Published once per successful `POST /api/announcements`, after the row is committed. Rejected creates (400,
415, 405, 406) and `POST /{id}/publish` publish nothing. Publishing is best effort: a `PutEvents` failure is
logged as `AnnouncementCreated not published` and the HTTP response stays exactly what the monolith returns.

## Choices and the AWS documentation behind them

Read through the AWS Documentation MCP server (`aws___search_documentation`, `aws___read_documentation`).

| Choice | Decision | Documentation |
|---|---|---|
| Lambda runtime | `java21` (Amazon Linux 2023, deprecation 2029-06-30), x86_64, SnapStart on published versions behind the `live` alias | [Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html): java21 is a supported AL2023 runtime; the java11 runtime of the monolith runs on Amazon Linux 2 and AWS recommends AL2023 runtimes for new work |
| Payload format | HTTP API, `AWS_PROXY`, `payload_format_version = "2.0"`; the handler returns the full `statusCode`/`headers`/`body`/`isBase64Encoded` shape | [HTTP API Lambda integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html): 2.0 carries `rawPath` and `rawQueryString` (the dispatcher needs the undecoded path for Spring's case-sensitive and trailing-slash matching), lowercases header names, and only guesses the response when `statusCode` is missing, which would break the 406/415 parity cases |
| Routing the rest | `$default` route on an `HTTP_PROXY` integration to the lp-ec2 ALB | [HTTP API routes](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-routes.html): `$default` catches every request no other route matches and passes the full path; `{proxy+}` must be the last path segment |
| Event entry | `PutEvents` with `EventBusName`, `Source`, `DetailType`, `Detail` (JSON string) | [PutEventsRequestEntry](https://docs.aws.amazon.com/eventbridge/latest/APIReference/API_PutEventsRequestEntry.html): `Source` is free form but `aws.` is reserved, `DetailType` up to 128 characters, `Detail` must be valid JSON |
| Rule shape | Custom bus, pattern `{"source": [...], "detail-type": ["AnnouncementCreated"]}` | [Event patterns](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-event-patterns.html): patterns have the structure of the events they match, arrays of exact values, match on `source`, `detail-type` and `detail`; narrow patterns avoid unwanted matches |
| Rule targets | SQS queue (+ DLQ) with a queue policy scoped to the rule ARN; CloudWatch Logs group with a log resource policy for `events.amazonaws.com` and `delivery.logs.amazonaws.com` | [EventBridge resource-based policies](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-use-resource-based.html): the console adds the CloudWatch Logs policy itself, the API/Terraform must create it |

## Parity, run `lp-ann-20261006-a1` in front of `lp-ec2-20261006-b1`

`make lp-ann-replay RUN=lp-ann-20261006-a1 TARGET=both`, 2026-10-06. The corpus checksums matched `SHA256SUMS`, and every replay started from empty tables with ids restarting at 1.

| Context | Cases | Served by (new) | EC2 ALB identical | HTTP API identical |
|---|---|---|---|---|
| common | 10 | EC2 | 10/10 | 10/10 |
| announcements | 36 | Lambda + Aurora | 36/36 | 36/36 |
| preferences | 20 | EC2 | 20/20 | 20/20 |
| feedback | 29 | EC2 | 29/29 | 29/29 |
| **total** | **95** | | **95/95** | **95/95** |
