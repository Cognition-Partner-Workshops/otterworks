# Strangler carve-out: feedback

Second module through the [strangler flow](strangler.md), after announcements. `/api/feedback` and
`/api/feedback/{proxy+}` run on main's `services/legacy-portal-lambda/feedback` (unchanged) behind an HTTP API,
with Aurora Serverless v2 holding `feedback.feedback`. Every other route (`/health`, announcements, preferences,
`/actuator/*`) goes through the API's `$default` route to the ALB of `lp-ec2-20261006-b1`, which is only read.
Feedback publishes no events, so the run has no EventBridge bus, rule or queue.

| Item | Value |
|---|---|
| Run token | `lp-fb-20261006-a1` |
| Expires | `2026-10-08` |
| Strangles | `lp-ec2-20261006-b1` (Expires 2026-10-09) |
| Lambda | `lp-fb-20261006-a1-feedback`, `java21`, SnapStart, alias `live` -> version 1 |
| HTTP API | `lp-fb-20261006-a1`: `ANY /api/feedback`, `ANY /api/feedback/{proxy+}` (Lambda, payload 2.0), `$default` (HTTP proxy to the EC2 ALB) |
| Aurora | `lp-fb-20261006-a1`, aurora-postgresql 16.13, 0-1 ACU, Data API |
| Log groups | `/aws/lambda/lp-fb-20261006-a1-feedback`, `/aws/apigateway/lp-fb-20261006-a1` |
| State | `otterworks/legacy-portal-strangler/lp-fb-20261006-a1/terraform.tfstate` |

## Parity

`make lp-mod-replay RUN=lp-fb-20261006-a1`, 2026-10-06, Lambda version 1. Under the EC2 lock, each replay
started from empty tables with ids from 1, corpus checksums OK (`SHA256SUMS`), compared with `java-reference.json`.

| Context | Cases | Served by (new) | EC2 (lp-ec2-20261006-b1) identical | API GW (lp-fb-20261006-a1) identical |
|---|---|---|---|---|
| common | 10 | EC2 | 10/10 | 10/10 |
| announcements | 36 | EC2 | 36/36 | 36/36 |
| preferences | 20 | EC2 | 20/20 | 20/20 |
| feedback | 29 | Lambda + Aurora | 29/29 | 29/29 |
| **total** | **95** | | **95/95** | **95/95** |

## Gap fixed in the harness

The first `make lp-mod-status` after `up` answered `GET /api/feedback/average-rating` with 500: the API access
log showed integration status 409, because the freshly published SnapStart version was still `Pending` while
Lambda took its snapshot. `lp-mod-up` now runs `aws lambda wait function-active-v2 --qualifier live` after the
apply (commit f9808c12 on the base branch), so the run is only reported up once the alias can be invoked. After the version became `Active` all
four probes returned 200 without any change to Terraform or the Lambda.

## AWS documentation behind the choices

Read through the AWS Documentation MCP server (`aws___read_documentation`).

| Choice | Quote |
|---|---|
| `java21` | [Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html): "Java 21 \| `java21` \| Amazon Linux 2023 \| Jun 30, 2029"; "Amazon Linux 2 is scheduled for end of life on June 30, 2026" |
| Payload format 2.0 | [HTTP API Lambda integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html): "Format `2.0` has `rawPath`"; "All headernames are lowercased." `FeedbackHandler` routes on `rawPath` and reads `content-type` |
| `$default` and `{proxy+}` | [HTTP API routes](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-routes.html): "API Gateway selects the route with the most-specific match ... 1. Full match for a route and method. 2. Match for a route and method with a greedy path variable (`{proxy+}`). 3. The `$default` route."; "When the `$default` route receives a request, API Gateway sends the full request path to the integration." |

## Cleanup

```
make lp-mod-down RUN=lp-fb-20261006-a1 && make lp-mod-verify-clean RUN=lp-fb-20261006-a1
```

The stack is left running until its `Expires` date for review; the EC2 run is not touched by `lp-mod-down`.
